import inspect
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, List, Optional, Type, Union
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

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
    """
    path: str
    methods: List[str]
    body_model: Optional[Type[BaseModel]]
    response_model: Optional[Type[BaseModel]]
    path_params: List[str]
    handler_name: str

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
                    annotation = param.annotation
                    if hasattr(annotation, "__origin__") and annotation.__origin__ is Union:
                        for arg in annotation.__args__:
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

        routes.append(
            RouteInfo(
                path=route.path,
                methods=list(route.methods),
                body_model=body_model if (isinstance(body_model, type) and issubclass(body_model, BaseModel)) else None,
                response_model=response_model if (isinstance(response_model, type) and issubclass(response_model, BaseModel)) else None,
                path_params=path_params,
                handler_name=route.endpoint.__name__,
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

