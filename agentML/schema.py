from typing import Any, List, Optional
from pydantic import BaseModel, Field

class FieldDefinition(BaseModel):
    """Defines a property or input field of an agent resource or action parameter.

    Attributes:
        name (str): The identifier name of the field.
        type (str): The data type, e.g., 'string', 'integer', 'number', 'boolean', 'enum'.
        required (bool): Whether the field is mandatory for the operation.
        description (str): Explanatory text describing the field's purpose.
        current (Any, optional): The current value of this field on the target resource.
        constraints (dict): Constraints on validation (e.g. minimum, maximum, pattern, options).
    """
    name: str
    type: str                        # "string", "integer", "date", "boolean", "enum"
    required: bool
    description: str = ""
    current: Any = None              # Current value of this field on the resource
    constraints: dict = Field(default_factory=dict)           # min, max, enum options, pattern, etc.

class Capability(BaseModel):
    """Represents a business capability/action that the agent can perform.

    Attributes:
        name (str): The business-focused name of the action (e.g., 'RegisterPatient').
        description (str): Clear instruction on when and how to invoke this capability.
        fields (List[FieldDefinition]): The parameters/input fields required for this capability.
        note (str): Important contextual or safety warning notes for the agent.
    """
    name: str                        # Business name: "RegisterPatient"
    description: str                 # Plain language: what this does in the real world
    fields: List[FieldDefinition] = Field(default_factory=list)
    note: str = ""                   # Context agent needs before acting

class UnavailableCapability(BaseModel):
    """Represents a capability that would normally be available but is disabled dynamically.

    Attributes:
        name (str): The name of the capability that is disabled.
        reason (str): The business reason describing why this capability is disabled.
    """
    name: str                        # Same naming convention as Capability
    reason: str                      # Why it can't be performed right now

class Alert(BaseModel):
    """Contextual prompt, banner, or dynamic notification for the agent.

    Attributes:
        level (str): The alert level, e.g., 'info', 'warning', 'error'.
        message (str): The text message intended for the agent to read.
    """
    level: str                       # "info", "warning", "error"
    message: str

class NavigationLink(BaseModel):
    """A link to navigate to related agent workspaces.

    Attributes:
        label (str): A descriptive label of the transition or resource (e.g., 'ViewAllPatients').
        agent_endpoint (str): The absolute or relative /agents path to navigate to.
    """
    label: str
    agent_endpoint: str              # Always an /agents URL

class WorkspaceBlock(BaseModel):
    """Contextual location details for the workspace.

    Attributes:
        title (str): Friendly title for this workspace.
        resource (str): The human counterpart URL.
        agent_resource (str): The agent-page counterpart URL (ending in /agents).
    """
    title: str
    resource: str                    # The human URL
    agent_resource: str              # The /agents URL

class IdentityBlock(BaseModel):
    """Security credentials and role context for the current request.

    Attributes:
        role (str, optional): The dynamic role of the authenticated agent.
        user_id (str, optional): The unique identifier of the user/session.
    """
    role: Optional[str] = None
    user_id: Optional[str] = None

class MetaBlock(BaseModel):
    """Pagination and query metadata for list collections.

    Attributes:
        total (int, optional): Total count of items in the resource.
        page (int, optional): The current page index (1-based).
        per_page (int, optional): Maximum item count per page.
        filters (dict): Key-value dictionary of query parameters or active filters.
    """
    total: Optional[int] = None
    page: Optional[int] = None
    per_page: Optional[int] = None
    filters: dict = Field(default_factory=dict)

class AgentWorkspace(BaseModel):     # The top-level output (formerly AgentPage)
    """The complete agent-page structure representing the active Agent Workspace.

    Attributes:
        agentML (str): The spec version of AgentML convention.
        workspace (WorkspaceBlock): Location information.
        identity (IdentityBlock): Dynamic actor information.
        state (dict): The serialized current state of the resource.
        alerts (List[Alert]): Active alerts/notices.
        capabilities (List[Capability]): Permitted actions.
        unavailable (List[UnavailableCapability]): Inactive capabilities with reasons.
        navigation (List[NavigationLink]): Next-hop endpoints.
        guidance (List[str]): Procedural hints or context guidelines.
        feedback (dict): Return results from the previous execution.
        meta (MetaBlock, optional): Search/pagination metadata.
    """
    agentML: str = "0.1"
    workspace: WorkspaceBlock        # formerly page
    identity: IdentityBlock
    state: dict = Field(default_factory=dict)                      # Current resource state
    alerts: List[Alert] = Field(default_factory=list)
    capabilities: List[Capability] = Field(default_factory=list)
    unavailable: List[UnavailableCapability] = Field(default_factory=list)
    navigation: List[NavigationLink] = Field(default_factory=list)
    guidance: List[str] = Field(default_factory=list)         # Step-by-step hints for complex workflows
    feedback: dict = Field(default_factory=dict)              # Result of last action (for stateful sessions)
    meta: Optional[MetaBlock] = None

