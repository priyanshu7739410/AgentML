import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("agentML")

class AgentMLMiddleware:
    """ASGI middleware that intercepts POST, PUT, and DELETE responses

    to return enriched AgentML mutation payloads when the client requests them.
    """
    def __init__(self, app, agentml):
        self.app = app
        self.agentml = agentml

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        if method not in ("POST", "PUT", "DELETE"):
            await self.app(scope, receive, send)
            return

        has_accept = False
        for k, v in scope.get("headers", []):
            if k.lower() == b"accept":
                if b"application/vnd.agentml+json" in v.lower():
                    has_accept = True
                    break

        if not has_accept:
            await self.app(scope, receive, send)
            return

        # 1. Capture request body chunks so we can compute delta
        request_body_chunks = []
        async def wrapped_receive():
            message = await receive()
            if message["type"] == "http.request":
                request_body_chunks.append(message.get("body", b""))
            return message

        # 2. Capture response body chunks, status, and headers
        response_body_chunks = []
        response_status = [200]
        response_headers = []

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                response_status[0] = message.get("status", 200)
                # Filter out content-length header as we will change the body size
                response_headers.extend([
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() != b"content-length"
                ])
            elif message["type"] == "http.response.body":
                response_body_chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    # We have captured the entire response!
                    await self._send_enriched_response(
                        scope,
                        response_status[0],
                        response_headers,
                        b"".join(response_body_chunks),
                        b"".join(request_body_chunks),
                        send
                    )
                    return
                else:
                    # Do not forward intermediate body chunks yet
                    return
            else:
                await send(message)

        # Call the application with our wrapped receive and send
        await self.app(scope, wrapped_receive, wrapped_send)

    async def _send_enriched_response(self, scope, status_code, headers, response_bytes, request_bytes, send):
        # Parse response JSON
        response_json = {}
        try:
            if response_bytes:
                response_json = json.loads(response_bytes.decode("utf-8"))
        except Exception:
            pass

        # Parse request JSON
        request_json = {}
        try:
            if request_bytes:
                request_json = json.loads(request_bytes.decode("utf-8"))
        except Exception:
            pass

        # 1. Compute delta (changed fields from request that are in response)
        delta = {}
        if isinstance(request_json, dict) and isinstance(response_json, dict):
            for k, v in request_json.items():
                if k in response_json:
                    delta[k] = response_json[k]

        # 2. Resolve endpoint ActionMeta if registered
        endpoint = scope.get("endpoint")
        meta = None
        if endpoint:
            meta = self.agentml._registry.get(endpoint)
            if not meta:
                import inspect
                try:
                    unwrapped = inspect.unwrap(endpoint)
                    meta = self.agentml._registry.get(unwrapped)
                except Exception:
                    pass

        # 3. Resolve target agent_resource
        agent_resource = None
        if meta and hasattr(meta, "returns") and meta.returns:
            template = meta.returns
            placeholders = re.findall(r"\{([^}]+)\}", template)
            human_path = template
            if isinstance(response_json, dict):
                for ph in placeholders:
                    val = response_json.get(ph)
                    if val is not None:
                        human_path = human_path.replace(f"{{{ph}}}", str(val))
            agent_resource = (human_path.rstrip("/") + "/agents") if human_path != "/" else "/agents"

        if not agent_resource and isinstance(response_json, dict):
            # Fallback heuristic: search for ID in response and prefix from request path
            id_val = None
            if "id" in response_json:
                id_val = response_json["id"]
            elif "uuid" in response_json:
                id_val = response_json["uuid"]
            else:
                for k, v in response_json.items():
                    if k.endswith("_id"):
                        id_val = v
                        break

            req_path = scope.get("path", "/")
            if id_val is not None:
                last_seg = req_path.split("/")[-1]
                if last_seg == str(id_val):
                    human_path = req_path
                else:
                    human_path = req_path.rstrip("/") + f"/{id_val}"
            else:
                human_path = req_path

            agent_resource = (human_path.rstrip("/") + "/agents") if human_path != "/" else "/agents"

        if not agent_resource:
            agent_resource = "/agents"

        # 4. Fetch the resulting workspace via in-process ASGI subrequest
        workspace_data = {}
        try:
            req_headers = {}
            for k, v in scope.get("headers", []):
                k_str = k.decode("latin1").lower()
                if k_str in ("authorization", "cookie", "x-agentml-role", "x-agentml-user-id"):
                    req_headers[k_str] = v.decode("latin1")

            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                query_string = scope.get("query_string", b"").decode("utf-8")
                resp = await client.get(agent_resource, headers=req_headers, params=query_string)
                if resp.status_code == 200:
                    workspace_data = resp.json()
        except Exception as e:
            logger.warning(f"Error fetching workspace state at {agent_resource}: {e}")

        # 5. Extract transitions
        transitions = []
        seen = set()
        if workspace_data:
            # Add capabilities
            for cap in workspace_data.get("capabilities", []):
                key = (cap["name"], agent_resource)
                if key not in seen:
                    seen.add(key)
                    transitions.append({
                        "action": cap["name"],
                        "agent_endpoint": agent_resource
                    })
            # Add navigation links
            for nav in workspace_data.get("navigation", []):
                key = (nav["label"], nav["agent_endpoint"])
                if key not in seen:
                    seen.add(key)
                    transitions.append({
                        "action": nav["label"],
                        "agent_endpoint": nav["agent_endpoint"]
                    })

        # Build final enriched response body
        enriched_body = {
            "result": response_json if response_json else response_bytes.decode("utf-8"),
            "delta": delta,
            "agent_resource": agent_resource,
            "transitions": transitions
        }

        enriched_bytes = json.dumps(enriched_body).encode("utf-8")

        # Update Content-Type to application/json or similar if we parsed it
        has_content_type = False
        new_headers = []
        for k, v in headers:
            if k.lower() == b"content-type":
                new_headers.append((k, b"application/json"))
                has_content_type = True
            else:
                new_headers.append((k, v))
        if not has_content_type:
            new_headers.append((b"content-type", b"application/json"))

        # Append correct content-length
        new_headers.append((b"content-length", str(len(enriched_bytes)).encode("latin1")))

        # Send response start and response body
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": new_headers
        })
        await send({
            "type": "http.response.body",
            "body": enriched_bytes,
            "more_body": False
        })
