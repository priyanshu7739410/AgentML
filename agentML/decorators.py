from dataclasses import dataclass
from typing import List, Optional, Callable, Dict, Any

@dataclass
class ActionMeta:
    """Metadata for exposing a FastAPI endpoint as an AgentML capability.

    Attributes:
        action (str): The business-focused name of the capability (e.g. 'PrescribeMedicine').
        description (str): Explanatory text for the agent detailing what the capability does.
        roles (List[str], optional): The list of roles authorized to perform this capability.
        unavailable_fn (Callable, optional): A callable invoked at runtime to check if this capability
                                             is dynamically unavailable. Returns a reason string or None.
        alerts_fn (Callable, optional): A callable invoked at runtime to generate contextual alerts or
                                        guidance for this capability. Returns a list of alerts.
    """
    action: str
    description: str = ""
    roles: Optional[List[str]] = None
    unavailable_fn: Optional[Callable[[Dict[str, Any], Any], Optional[str]]] = None
    alerts_fn: Optional[Callable[[Dict[str, Any], Any], List[Any]]] = None
    guidance: Optional[List[str]] = None


