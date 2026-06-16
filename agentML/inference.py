"""Module for inferring business-focused capability names from HTTP methods and URL paths."""

METHOD_VERB = {
    ("GET", False): "List",       # GET /patients
    ("GET", True): "Get",         # GET /patients/{id}
    ("POST", False): "Create",    # POST /patients
    ("PUT", True): "Update",
    ("DELETE", True): "Delete",
    ("PATCH", True): "Update",
}

SINGULARIZATION_EXCEPTIONS = {
    "address", "status", "process", "class", "access",
    "progress", "discuss", "canvas", "alias", "bonus"
}

def _should_singularize(word: str) -> bool:
    """Helper to check if a word/resource ends with a known exception that shouldn't be singularized."""
    word_lower = word.lower()
    for exc in SINGULARIZATION_EXCEPTIONS:
        if word_lower == exc or word_lower.endswith(exc):
            return False
    return True

def infer_capability_name(method: str, path: str) -> str:
    """Derives a clean, business-focused capability name from an HTTP method and route path.

    Transforms technical route details (e.g., 'POST /patients') into domain action
    names (e.g., 'CreatePatient'), following the AgentML convention of using purely
    business semantic terminology rather than HTTP verb vocabulary.

    Args:
        method (str): HTTP method (e.g., 'GET', 'POST').
        path (str): The route URL path (e.g., '/patients/{id}').

    Returns:
        str: PascalCase business capability name.
    """
    # Clean path
    segments = [s for s in path.split("/") if s]
    if not segments:
        return "Root"
    
    # Identify if it's an instance path: does the last segment start with '{' and end with '}'
    is_instance = segments[-1].startswith("{") and segments[-1].endswith("}")
    
    # Find the resource name.
    if is_instance:
        resource = segments[-2] if len(segments) >= 2 else "Resource"
    else:
        resource = segments[-1]
    
    # Clean resource name (convert snake_case/kebab-case/etc. to PascalCase)
    resource = "".join(part.capitalize() for part in resource.replace("-", "_").split("_"))
    
    # Check for custom actions in path, e.g. /billing/generate or /patients/{id}/cancel
    # If not an instance path, and last segment is a known action verb
    if not is_instance and len(segments) >= 2 and segments[-1] in ("generate", "verify", "cancel", "approve", "reject", "submit"):
        action = segments[-1].capitalize()
        parent_resource = "".join(part.capitalize() for part in segments[-2].replace("-", "_").split("_"))
        # Clean any ending 's' if not appropriate
        if parent_resource.endswith("s") and not parent_resource.endswith("ss"):
            if _should_singularize(parent_resource):
                parent_resource = parent_resource[:-1]
        return f"{action}{parent_resource}"

    # Determine the prefix based on method and is_instance
    verb = METHOD_VERB.get((method.upper(), is_instance), "")
    if not verb:
        if method.upper() == "POST":
            verb = "Create"
        elif method.upper() in ("PUT", "PATCH"):
            verb = "Update"
        elif method.upper() == "DELETE":
            verb = "Delete"
        else:
            verb = "Get"
    
    # Singularize resource if it ends with "s" (but not "ss") for non-List verbs
    if verb != "List" and resource.endswith("s") and not resource.endswith("ss"):
        if _should_singularize(resource):
            resource = resource[:-1]
        
    return f"{verb}{resource}"


