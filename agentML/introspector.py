import inspect
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, List, Optional, Type, Union
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

@dataclass
class FieldInfo:
    """Metadata details extracted from Pydantic fields.

    Attributes:
        name (str): Field identifier name.
        type (str): Unified type descriptor (e.g., 'string', 'integer', 'enum', 'date').
        required (bool): True if the field is mandatory, False otherwise.
        default (Any): Default value if not specified.
        constraints (dict): Dictionary of parameter validation constraints (e.g., ge, le, enum).
        description (str): Explanatory documentation of the field's purpose.
    """
    name: str
    type: str
    required: bool
    default: Any
    constraints: dict = dc_field(default_factory=dict)
    description: str = ""

@dataclass
class RouteInfo:
    """Metadata representing a parsed FastAPI route for AgentML introspection.

    Attributes:
        path (str): The routing path (e.g. '/patients/{id}').
        methods (List[str]): List of HTTP methods supported by the route.
        body_model (Type[BaseModel], optional): The Pydantic model representing request body inputs.
        response_model (Type[BaseModel], optional): The Pydantic model representing route outputs/responses.
        path_params (List[str]): Names of path parameters embedded in the route.
        handler_name (str): Name of the endpoint function handler.
        query_params (List[FieldInfo]): List of query parameters accepted by the route.
    """
    path: str
    methods: List[str]
    body_model: Optional[Type[BaseModel]]
    response_model: Optional[Type[BaseModel]]
    path_params: List[str]
    handler_name: str
    query_params: List[FieldInfo] = dc_field(default_factory=list)
    endpoint: Any = None

def get_routes(app: FastAPI) -> List[RouteInfo]:
    """Inspects a FastAPI application and returns a structured list of route metadata.

    This function automatically skips system or docs endpoints (e.g., /docs, /openapi.json)
    and AgentML-specific workspace routes (endpoints ending with /agents) to focus on human
    application paths.

    Args:
        app (FastAPI): The target FastAPI application to inspect.

    Returns:
        List[RouteInfo]: Extracted route definitions.
    """
    routes = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        
        # Skip AgentML internal/system routes
        if route.path.endswith("/agents"):
            continue
        if "/docs" in route.path or "/openapi.json" in route.path or "/redoc" in route.path:
            continue
            
        # Extract body model
        body_model = None
        if hasattr(route, "dependant") and route.dependant and route.dependant.body_params:
            first_body = route.dependant.body_params[0]
            if hasattr(first_body, "type_"):
                body_model = first_body.type_
            elif hasattr(first_body, "annotation"):
                body_model = first_body.annotation

        if body_model is None or not (isinstance(body_model, type) and issubclass(body_model, BaseModel)):
            try:
                sig = inspect.signature(route.endpoint)
                for param in sig.parameters.values():
                    # Skip Depends()
                    from fastapi.params import Depends
                    if isinstance(param.default, Depends) or type(param.default).__name__ == "Depends":
                        continue

                    # Skip FastAPI Request, Response, BackgroundTasks
                    from fastapi import Request, Response, BackgroundTasks
                    annotation = param.annotation
                    if annotation in (Request, Response, BackgroundTasks):
                        continue

                    if hasattr(annotation, "__origin__") and annotation.__origin__ is Union:
                        for arg in annotation.__args__:
                            if arg in (Request, Response, BackgroundTasks):
                                continue
                            if isinstance(arg, type) and issubclass(arg, BaseModel):
                                body_model = arg
                                break
                    elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                        body_model = annotation
                        break
                    if body_model:
                        break
            except Exception:
                pass

        # Extract response model
        response_model = route.response_model
        if response_model is None:
            try:
                sig = inspect.signature(route.endpoint)
                return_annotation = sig.return_annotation
                if isinstance(return_annotation, type) and issubclass(return_annotation, BaseModel):
                    response_model = return_annotation
            except Exception:
                pass

        path_params = re.findall(r"\{([^}]+)\}", route.path)

        # Extract query parameters
        query_params = []
        if hasattr(route, "dependant") and route.dependant and route.dependant.query_params:
            for q_param in route.dependant.query_params:
                name = q_param.name
                type_str = "string"
                if hasattr(q_param, "field_info") and q_param.field_info and q_param.field_info.annotation:
                    annot = q_param.field_info.annotation
                    if hasattr(annot, "__origin__") and annot.__origin__ is Union:
                        args = [a for a in annot.__args__ if a is not type(None)]
                        annot = args[0] if args else str
                    if annot is int:
                        type_str = "integer"
                    elif annot is float:
                        type_str = "number"
                    elif annot is bool:
                        type_str = "boolean"
                elif hasattr(q_param, "type_") and q_param.type_:
                    t_val = q_param.type_
                    if t_val is int:
                        type_str = "integer"
                    elif t_val is float:
                        type_str = "number"
                    elif t_val is bool:
                        type_str = "boolean"

                required = False
                default_val = None
                description = ""

                if hasattr(q_param, "field_info") and q_param.field_info:
                    f_info = q_param.field_info
                    from pydantic_core import PydanticUndefined
                    if f_info.default is not PydanticUndefined and f_info.default is not ...:
                        default_val = f_info.default
                    else:
                        required = True
                    description = f_info.description or ""

                query_params.append(
                    FieldInfo(
                        name=name,
                        type=type_str,
                        required=required,
                        default=default_val,
                        constraints={},
                        description=description,
                    )
                )

        routes.append(
            RouteInfo(
                path=route.path,
                methods=list(route.methods),
                body_model=body_model if (isinstance(body_model, type) and issubclass(body_model, BaseModel)) else None,
                response_model=response_model if (isinstance(response_model, type) and issubclass(response_model, BaseModel)) else None,
                path_params=path_params,
                handler_name=route.endpoint.__name__,
                query_params=query_params,
                endpoint=route.endpoint,
            )
        )
    return routes

def extract_fields(model: Type[BaseModel]) -> List[FieldInfo]:
    """Parses a Pydantic model into a unified list of FieldInfo metadata.

    Leverages Pydantic v2's built-in JSON schema generation to map field types, defaults,
    and validation constraints (minimum, maximum, string lengths, patterns, enums, format dates)
    to a simplified schema format that agents can consume.

    Args:
        model (Type[BaseModel]): A Pydantic class to inspect.

    Returns:
        List[FieldInfo]: List of extracted field information.
    """
    fields = []
    if not (isinstance(model, type) and issubclass(model, BaseModel)):
        return fields

    # Leverage Pydantic v2's built-in JSON Schema generation
    schema = model.model_json_schema()
    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])

    for name, prop in properties.items():
        type_str = prop.get("type", "string")
        
        # Detect enum
        if "enum" in prop:
            type_str = "enum"
        elif prop.get("format") in ("date", "date-time"):
            type_str = "date"
        elif type_str == "integer":
            type_str = "integer"
        elif type_str == "number":
            type_str = "number"
        elif type_str == "boolean":
            type_str = "boolean"

        # Resolve constraints from OpenAPI JSON Schema fields
        constraints = {}
        if "enum" in prop:
            constraints["enum"] = prop["enum"]
        if "minimum" in prop:
            constraints["ge"] = prop["minimum"]
        if "maximum" in prop:
            constraints["le"] = prop["maximum"]
        if "exclusiveMinimum" in prop:
            constraints["gt"] = prop["exclusiveMinimum"]
        if "exclusiveMaximum" in prop:
            constraints["lt"] = prop["exclusiveMaximum"]
        if "minLength" in prop:
            constraints["min_length"] = prop["minLength"]
        if "maxLength" in prop:
            constraints["max_length"] = prop["maxLength"]
        if "pattern" in prop:
            constraints["pattern"] = prop["pattern"]

        fields.append(
            FieldInfo(
                name=name,
                type=type_str,
                required=name in required_fields,
                default=prop.get("default"),
                constraints=constraints,
                description=prop.get("description", ""),
            )
        )
    return fields

