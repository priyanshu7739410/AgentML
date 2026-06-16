from typing import List, Optional, Dict
from agentML.schema import Capability

def filter_capabilities(
    capabilities: List[Capability],
    registry: Dict,
    role: Optional[str]
) -> List[Capability]:
    """Filters the list of capabilities based on the dynamic role of the authenticated agent.

    Following AgentML Rule #3, RBAC is invisible by design: if a capability's required roles
    do not match the current actor's role, the capability is completely omitted from the workspace.

    Args:
        capabilities (List[Capability]): List of candidate capabilities.
        registry (Dict): The application's action/endpoint registry of ActionMeta.
        role (str, optional): The authenticated role of the agent.

    Returns:
        List[Capability]: The filtered list of authorized capabilities.
    """
    filtered = []
    # Build a lookup of action names to their allowed roles
    action_to_roles = {}
    for meta in registry.values():
        if hasattr(meta, "action") and hasattr(meta, "roles"):
            action_to_roles[meta.action] = meta.roles

    for cap in capabilities:
        allowed_roles = action_to_roles.get(cap.name)
        if allowed_roles is not None:
            # If the action has explicit role restrictions, verify the agent's role matches
            if role not in allowed_roles:
                continue
        filtered.append(cap)
    return filtered

