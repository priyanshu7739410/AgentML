from typing import List, Dict, Any, Optional
from agentML.schema import (
    AgentWorkspace,
    WorkspaceBlock,
    IdentityBlock,
    Capability,
    FieldDefinition,
    NavigationLink,
    UnavailableCapability,
    Alert,
    MetaBlock,
)
from agentML.auth import AuthContext
from agentML.introspector import RouteInfo, extract_fields
from agentML.inference import infer_capability_name
from agentML.rbac import filter_capabilities

def render_agent_workspace(
    resource_path: str,
    routes: List[RouteInfo],
    registry: Dict[str, Any],
    auth: AuthContext,
    state: Dict[str, Any],
) -> AgentWorkspace:
    """Renders the current API resource path into an AgentWorkspace structure.

    Dynamically inspects the matching routes, extracts capabilities/actions, resolves
    parameter schemas and validation rules, constructs the state dictionary, evaluates
    unavailability/alert states, and returns a fully conforming AgentML response.

    Args:
        resource_path (str): The current URL path being queried (e.g. '/patients/1/agents').
        routes (List[RouteInfo]): All route metadata parsed from the FastAPI application.
        registry (Dict[str, Any]): Registered metadata for explicitly exposed endpoints.
        auth (AuthContext): The current user role and session details.
        state (Dict[str, Any]): The dynamic state returned by the main resource endpoint.

    Returns:
        AgentWorkspace: The fully populated AgentML workspace.
    """
    # 1. Clean the resource_path
    path_clean = "/" + resource_path.strip("/")
    if path_clean.endswith("/agents"):
        human_path = path_clean[:-7]
        if not human_path:
            human_path = "/"
    else:
        human_path = path_clean
        
    agent_resource = (human_path.rstrip("/") + "/agents") if human_path != "/" else "/agents"

    # Determine prefix
    human_segments = [s for s in human_path.split("/") if s]
    
    # Filter routes related to the current resource path prefix
    filtered_routes = []
    if not human_segments:
        # Root /agents -> list all routes
        filtered_routes = routes
    else:
        prefix = human_segments[0]
        for r in routes:
            r_segments = [s for s in r.path.split("/") if s]
            if r_segments and r_segments[0] == prefix:
                filtered_routes.append(r)
                
    # Build capabilities
    capabilities = []
    unavailable = []
    alerts = []
    
    # To avoid duplicate capabilities (same name/method on same path)
    seen_capabilities = set()
    
    for r in filtered_routes:
        for method in r.methods:
            if method.upper() not in ("POST", "GET", "PUT", "DELETE", "PATCH"):
                continue
            
            # Retrieve capability from registry or infer it
            meta = registry.get(r.handler_name)
            if meta:
                cap_name = meta.action
                description = meta.description
                unavailable_fn = meta.unavailable_fn
                alerts_fn = meta.alerts_fn
            else:
                cap_name = infer_capability_name(method, r.path)
                description = r.handler_name.replace("_", " ").capitalize()
                unavailable_fn = None
                alerts_fn = None

            # Ensure capability name has no HTTP verbs
            for verb in ("POST", "GET", "PUT", "DELETE", "PATCH"):
                cap_name = cap_name.replace(verb, "")
                cap_name = cap_name.replace(verb.capitalize(), "")
                
            cap_key = (cap_name, method.upper())
            if cap_key in seen_capabilities:
                continue
            seen_capabilities.add(cap_key)

            # Evaluate alerts dynamically
            if alerts_fn:
                try:
                    generated_alerts = alerts_fn(state, auth)
                    for a in generated_alerts:
                        if isinstance(a, Alert):
                            alerts.append(a)
                        elif isinstance(a, dict):
                            alerts.append(Alert(**a))
                except Exception:
                    pass

            # Check if this capability is unavailable due to current resource state
            is_unavailable = False
            if unavailable_fn:
                try:
                    reason = unavailable_fn(state, auth)
                    if reason:
                        unavailable.append(
                            UnavailableCapability(name=cap_name, reason=reason)
                        )
                        is_unavailable = True
                except Exception:
                    pass

            if is_unavailable:
                continue

            # Build fields
            fields = []
            if r.body_model:
                for f_info in extract_fields(r.body_model):
                    # Fetch current value from state (nested check if state holds a dictionary representation)
                    current_val = state.get(f_info.name)
                    fields.append(
                        FieldDefinition(
                            name=f_info.name,
                            type=f_info.type,
                            required=f_info.required,
                            description=f_info.description,
                            current=current_val,
                            constraints=f_info.constraints,
                        )
                    )
            
            capabilities.append(
                Capability(
                    name=cap_name,
                    description=description,
                    fields=fields,
                    note=""
                )
            )

    # Filter capabilities using RBAC (Phase 0 stub, returns all)
    capabilities = filter_capabilities(capabilities, registry, auth.role)

    # Build navigation links
    navigation = []
    all_prefixes = set()
    for r in routes:
        r_segments = [s for s in r.path.split("/") if s]
        if r_segments:
            all_prefixes.add(r_segments[0])
            
    for p in sorted(all_prefixes):
        if not human_segments or p != human_segments[0]:
            navigation.append(
                NavigationLink(
                    label=p.capitalize(),
                    agent_endpoint=f"/{p}/agents"
                )
            )
            
    if human_segments:
        navigation.append(
            NavigationLink(
                label="Home",
                agent_endpoint="/agents"
            )
        )
        if len(human_segments) > 1:
            navigation.append(
                NavigationLink(
                    label=f"All {human_segments[0].capitalize()}",
                    agent_endpoint=f"/{human_segments[0]}/agents"
                )
            )

    # Determine title
    if not human_segments:
        title = "Root Agent Workspace"
    elif len(human_segments) == 1:
        title = f"{human_segments[0].capitalize()} Agent Workspace"
    else:
        title = f"{human_segments[0].capitalize()} Instance Agent Workspace"

    # Meta block for collections
    meta_block = None
    if isinstance(state, dict) and "items" in state and isinstance(state["items"], list):
        meta_block = MetaBlock(total=len(state["items"]))

    return AgentWorkspace(
        agentML="0.1",
        workspace=WorkspaceBlock(
            title=title,
            resource=human_path,
            agent_resource=agent_resource,
        ),
        identity=IdentityBlock(
            role=auth.role,
            user_id=auth.user_id,
        ),
        state=state,
        capabilities=capabilities,
        navigation=navigation,
        alerts=alerts,
        unavailable=unavailable,
        guidance=[],
        feedback={},
        meta=meta_block,
    )

