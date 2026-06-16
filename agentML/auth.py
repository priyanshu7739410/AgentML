from dataclasses import dataclass
from typing import Optional
from fastapi import Request

@dataclass
class AuthContext:
    """Security credentials and role context for the current agent session.

    Attributes:
        role (str, optional): The dynamic security role of the authenticated agent.
        user_id (str, optional): The unique identifier of the user or session.
    """
    role: Optional[str] = None
    user_id: Optional[str] = None

def default_auth_extractor(request: Request) -> AuthContext:
    """Default dependency function to extract authentication context from an incoming request.

    By default, returns an unauthenticated/anonymous AuthContext. Applications can override
    this to populate role and user_id from headers, JWT tokens, or cookies.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        AuthContext: The resolved auth context.
    """
    return AuthContext()

