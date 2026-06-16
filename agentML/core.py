import logging
from typing import Callable, Dict, Any, Optional
from fastapi import FastAPI, Request
from agentML.auth import AuthContext, default_auth_extractor
from agentML.decorators import ActionMeta
from agentML.introspector import get_routes
from agentML.renderer import render_agent_workspace
from agentML.schema import AgentWorkspace

logger = logging.getLogger("agentML")

class AgentML:
    """AgentML class acts as the core router wrapper and route registry for FastAPI.
    
    It auto-inspects the registered routes at startup and mounts corresponding
    agent workspace endpoints at /agents for machine traversal.
    """
    def __init__(self, app: FastAPI, auth_extractor: Optional[Callable[[Request], AuthContext]] = None):
        """Initialize AgentML on the FastAPI application.
        
        Args:
            app (FastAPI): The FastAPI application instance to extend.
            auth_extractor (Callable, optional): Custom extractor function mapping
                HTTP requests to an AuthContext role/user payload.
        """
        self.app = app
        self.auth_extractor = auth_extractor or default_auth_extractor
        self._registry: Dict[str, ActionMeta] = {}    # handler_name → ActionMeta
        self._routes_registered = False
        
        from contextlib import asynccontextmanager

        # Inject startup registration into the lifespan lifecycle without breaking existing lifespans
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def agentml_lifespan(app_instance):
            self._register_agent_routes()
            async with original_lifespan(app_instance) as maybe_state:
                yield maybe_state

        app.router.lifespan_context = agentml_lifespan

    def expose(
        self,
        action: str,
        description: str = "",
        roles: Optional[list] = None,
        unavailable_fn: Optional[Callable] = None,
        alerts_fn: Optional[Callable] = None,
    ):
        """Decorate a route handler function to register custom AgentWorkspace metadata.
        
        Args:
            action (str): The business-oriented name of the action (e.g. 'RegisterPatient').
            description (str, optional): A descriptive text explaining what the action does.
            roles (list, optional): Allowed roles that can view/trigger this action.
            unavailable_fn (Callable, optional): Hook that receives (state, auth) and returns
                a string explanation if the action is currently blocked by state.
            alerts_fn (Callable, optional): Hook that receives (state, auth) and returns
                a list of Alert schemas.
        """
        def decorator(fn: Callable):
            self._registry[fn.__name__] = ActionMeta(
                action=action,
                description=description,
                roles=roles,
                unavailable_fn=unavailable_fn,
                alerts_fn=alerts_fn,
            )
            return fn
        return decorator

    def _register_agent_routes(self):
        if self._routes_registered:
            return
        self._routes_registered = True
        
        routes = get_routes(self.app)
        
        # Collect unique user paths
        user_paths = set()
        for r in routes:
            user_paths.add(r.path)
        
        # Ensure root path is included
        user_paths.add("/")

        registered_paths = set()
        for p in sorted(user_paths):
            agent_path = (p.rstrip("/") + "/agents") if p != "/" else "/agents"
            if agent_path in registered_paths:
                continue
            registered_paths.add(agent_path)

            # Route conflict detection
            conflict = False
            for r in self.app.routes:
                if r.path == agent_path:
                    if hasattr(r, "methods") and "GET" in r.methods:
                        conflict = True
                        break
            
            if conflict:
                msg = f"Route conflict detected: GET {agent_path} already exists. Skipping AgentML registration."
                logger.warning(msg)
                print(f"WARNING: {msg}")
                continue

            # Add the API route
            self.app.add_api_route(
                path=agent_path,
                endpoint=self._make_handler(agent_path),
                methods=["GET"],
                response_model=AgentWorkspace,
                name=f"agentml_{agent_path.replace('/', '_').replace('{', '').replace('}', '')}"
            )
            
        # Reorder routes so that agent routes (which end in /agents) are matched first.
        # This prevents path parameter routes (like /{id}) from matching /agents and causing 422/404.
        agent_routes = []
        other_routes = []
        for r in self.app.router.routes:
            if r.path.endswith("/agents"):
                agent_routes.append(r)
            else:
                other_routes.append(r)
        self.app.router.routes[:] = agent_routes + other_routes

    def _make_handler(self, agent_path: str):
        async def agent_handler(request: Request):
            auth = self.auth_extractor(request)
            
            # Fetch state from human UI endpoint dynamically using in-process ASGI call
            state = {}
            path_clean = "/" + request.url.path.strip("/")
            if path_clean.endswith("/agents"):
                human_path = path_clean[:-7]
                if not human_path:
                    human_path = "/"
            else:
                human_path = path_clean

            import httpx
            headers = dict(request.headers)
            headers["accept"] = "application/json"
            
            try:
                transport = httpx.ASGITransport(app=self.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get(human_path, headers=headers, params=request.query_params)
                    if resp.status_code == 200:
                        state_data = resp.json()
                        if isinstance(state_data, dict):
                            state = state_data
                        elif isinstance(state_data, list):
                            state = {"items": state_data}
            except Exception as e:
                logger.warning(f"Error fetching state for {human_path}: {e}")
                
            routes = get_routes(self.app)
            workspace_data = render_agent_workspace(
                resource_path=request.url.path,
                routes=routes,
                registry=self._registry,
                auth=auth,
                state=state
            )
            return workspace_data
        return agent_handler
