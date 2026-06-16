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
    ResourceMapEntry,
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
    feedback: Optional[Dict[str, Any]] = None,
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
        feedback (Dict[str, Any], optional): The payload of mutation execution feedback.

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
    
    # Build breadcrumbs
    breadcrumb = ["Home"]
    for idx, seg in enumerate(human_segments):
        if idx % 2 == 0:
            breadcrumb.append(seg.capitalize())
        else:
            parent = human_segments[idx - 1]
            from agentML.inference import _should_singularize
            parent_cap = parent.capitalize()
            if parent_cap.endswith("s") and not parent_cap.endswith("ss") and _should_singularize(parent_cap):
                parent_singular = parent_cap[:-1]
            else:
                parent_singular = parent_cap
            breadcrumb.append(f"{parent_singular} {seg}")

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
            meta = None
            if registry:
                meta = registry.get(r.endpoint)
                if not meta and hasattr(r, "endpoint") and r.endpoint:
                    import inspect
                    try:
                        unwrapped = inspect.unwrap(r.endpoint)
                        meta = registry.get(unwrapped)
                    except Exception:
                        pass
                if not meta:
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
                except Exception as e:
                    alerts.append(
                        Alert(
                            level="error",
                            message=f"Alert evaluation failed for {cap_name}: {type(e).__name__}: {str(e)}"
                        )
                    )

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
                except Exception as e:
                    reason = f"Safety check evaluation error: {type(e).__name__}: {str(e)}"
                    unavailable.append(
                        UnavailableCapability(name=cap_name, reason=reason)
                    )
                    is_unavailable = True

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
            
            # Extract query parameters (Tier 2/3 optional fields)
            if hasattr(r, "query_params") and r.query_params:
                for q_info in r.query_params:
                    current_val = state.get(q_info.name)
                    fields.append(
                        FieldDefinition(
                            name=q_info.name,
                            type=q_info.type,
                            required=False,
                            description=q_info.description,
                            current=current_val,
                            constraints=q_info.constraints,
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

    # 1. Instance-scoped nested links
    if len(human_segments) >= 2:
        prefix = human_segments[0]
        instance_id = human_segments[1]
        for r in routes:
            r_seg = [s for s in r.path.split("/") if s]
            if len(r_seg) > 2 and r_seg[0] == prefix and r_seg[1].startswith("{") and r_seg[1].endswith("}"):
                sub_seg = [instance_id if (s.startswith("{") and s.endswith("}")) else s for s in r_seg]
                nested_human_path = "/" + "/".join(sub_seg)
                nested_agent_endpoint = nested_human_path + "/agents"
                label = r_seg[2].capitalize()
                
                if not any(n.agent_endpoint == nested_agent_endpoint for n in navigation):
                    navigation.append(
                        NavigationLink(
                            label=label,
                            agent_endpoint=nested_agent_endpoint
                        )
                    )

    # 2. Sibling/Global navigation links
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

    # Gather guidance steps from capabilities/registry
    guidance = []
    for c in capabilities:
        for meta in registry.values():
            if hasattr(meta, "action") and meta.action == c.name:
                if hasattr(meta, "guidance") and meta.guidance:
                    for step in meta.guidance:
                        if step not in guidance:
                            guidance.append(step)

    # Build root resource map if root /agents
    resources = []
    if not human_segments:
        prefix_groups = {}
        for r in routes:
            r_segments = [s for s in r.path.split("/") if s]
            if r_segments:
                prefix = r_segments[0]
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []
                prefix_groups[prefix].append(r)
        
        for p in sorted(prefix_groups.keys()):
            desc = f"{p.capitalize()} directory"
            first_exposed_desc = None
            action_count = 0
            for r in prefix_groups[p]:
                meta = None
                if registry:
                    meta = registry.get(r.endpoint)
                    if not meta and hasattr(r, "endpoint") and r.endpoint:
                        import inspect
                        try:
                            unwrapped = inspect.unwrap(r.endpoint)
                            meta = registry.get(unwrapped)
                        except Exception:
                            pass
                    if not meta:
                        meta = registry.get(r.handler_name)
                if meta and meta.description and not first_exposed_desc:
                    first_exposed_desc = meta.description
                for method in r.methods:
                    if method.upper() in ("POST", "GET", "PUT", "DELETE", "PATCH"):
                        action_count += 1
            
            if first_exposed_desc:
                desc = first_exposed_desc
                
            resources.append(
                ResourceMapEntry(
                    name=p.capitalize(),
                    description=desc,
                    agent_endpoint=f"/{p}/agents",
                    action_count=action_count
                )
            )
        capabilities = []

    return AgentWorkspace(
        agentML="0.1",
        workspace=WorkspaceBlock(
            title=title,
            resource=human_path,
            agent_resource=agent_resource,
            breadcrumb=breadcrumb,
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
        guidance=guidance,
        feedback=feedback or {},
        meta=meta_block,
        resources=resources,
    )

