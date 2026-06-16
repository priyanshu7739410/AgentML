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

def clean_and_capitalize(seg: str, singularize: bool) -> str:
    # Convert snake_case/kebab-case/etc. to PascalCase
    capitalized = "".join(part.capitalize() for part in seg.replace("-", "_").split("_"))
    if singularize and capitalized.endswith("s") and not capitalized.endswith("ss"):
        if _should_singularize(capitalized):
            return capitalized[:-1]
    return capitalized

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
    
    # Check for custom actions in path, e.g. /billing/generate or /patients/{id}/cancel
    # If not an instance path, and last segment is a known action verb
    if not is_instance and len(segments) >= 2 and segments[-1] in ("generate", "verify", "cancel", "approve", "reject", "submit"):
        action = segments[-1].capitalize()
        # Resources are all segments before the custom action that are not parameters
        action_resources = [s for s in segments[:-1] if not (s.startswith("{") and s.endswith("}"))]
        resource_str = "".join(clean_and_capitalize(s, singularize=True) for s in action_resources)
        return f"{action}{resource_str}"

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

    # Identify non-parameter segments
    non_param_segs = [s for s in segments if not (s.startswith("{") and s.endswith("}"))]
    
    # Filter out generic/versioning prefixes from naming
    generic_prefixes = {"api", "v1", "v2", "v3", "v4", "v5"}
    if non_param_segs and non_param_segs[0].lower() in generic_prefixes:
        non_param_segs = non_param_segs[1:]
        
    if not non_param_segs:
        return f"{verb}Resource"

    # Build resource string from all non-parameter segments to prevent collisions on nested routes
    parts = []
    for i, seg in enumerate(non_param_segs):
        is_last = (i == len(non_param_segs) - 1)
        # Singularize if it's not the last segment, or if it is the last segment and verb is not "List"
        should_sing = (not is_last) or (verb != "List")
        parts.append(clean_and_capitalize(seg, singularize=should_sing))
        
    resource_str = "".join(parts)
    return f"{verb}{resource_str}"


