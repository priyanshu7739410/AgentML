# AgentML 

> **FastAPI generates APIs for humans and machines.**
> **AgentML generates resource workspaces for autonomous AI agents.**

---

## The Problem
Humans interact through visual interfaces. Because the web was built for human eyes, AI agents are forced to:
- Parse messy, layout-heavy HTML.
- Reverse-engineer form flows.
- Guess hidden workflows.
- Infer missing permissions.

These interfaces were never designed for autonomous systems.

---

## The Solution: One Backend, Two Renderers
AgentML introduces a simple, universal web rendering convention: **append `/agents` to any HTTP resource URL.**

A browser requests a resource and gets HTML. An AI agent requests the same resource + `/agents` and gets a fully rendered, action-ready **Agent Workspace**.

```
           Business Logic
                   |
       -------------|-------------
       |                         |
       v                         v
 Human Renderer         Agent Renderer
       |                         |
       v                         v
  HTML (for eyes)       Agent Workspace (JSON)
       |                         |
       v                         v
    Browser                   AI Agent
```

---

## Progressive Enhancement: The Four Tiers of AgentML
AgentML treats the AI agent experience like a webpage. Just as modern browsers render pages using progressive enhancement depending on stylesheet or JS availability, AgentML scales its workspaces based on the metadata available:

| Tier | Name | Generation Source | What the Agent Gets | Quality / Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 0** | **HTTP Inferred** | Raw HTTP traffic logs (e.g. at the reverse proxy/Cloudflare level) | Raw methods (`GET`, `POST`, `PUT`), URL paths, basic content types. | **Basic/Weak**: Good for legacy apps where you cannot access code or schemas. |
| **Tier 1** | **Schema Synthesized** | OpenAPI (Swagger) specs, database schemas, JSON Schemas | Route descriptions, parameter constraints, expected field names, basic descriptions. | **Decent**: Instantly turns any documented backend API into a basic Agent Workspace. |
| **Tier 2** | **Metadata Hybrid** | OpenAPI + Schema.org (Microdata) + HTML structure | Basic fields/actions + page semantic metadata (e.g. product names, prices) + basic state. | **Good**: Worker combines read-only SEO microdata with OpenAPI routes to link state and actions. |
| **Tier 3** | **Application Native** | Developer annotations (e.g. `@agent.expose()`) | Rich state, dynamic navigation (`/agents`), constraint hooks (`unavailable_fn`), custom RBAC. | **Excellent (Native)**: Full business workspace with deep application awareness and safety. |

### Architectural Takeaways:
1. **Zero-Friction Adoption**: A developer can start at **Tier 1** by simply pointing an edge proxy (e.g., a Cloudflare Worker) to their existing `openapi.json` file to auto-generate `/agents` workspaces immediately.
2. **Selective Upgrades**: As agent traffic scales, critical routes (like checkouts or billing) can be progressively enhanced to **Tier 3** (Application Native) using direct code annotations.
3. **The Role of CDNs/Edge Proxies**: The edge proxy can serve as the **aggregator and cache layer**—fetching OpenAPI schemas and current JSON data, merging them into the AgentML structure on the fly.

---

## Why not REST APIs?
- **REST APIs expose operations**: They tell you what endpoints exist globally (e.g. `POST /appointments`), but not who you are, what you can do right now, or what is currently set.
- **AgentML exposes context**: It bundles **Identity**, **Current State**, **Permissions**, **Available Actions**, and **Related Resources** together into a single, unified workspace. The agent doesn't reconstruct context; it receives it.

---

## How It Looks

### Human User Interface
```
GET /patients/1
```
➔ Returns a styled **HTML Page** with patient profile details, edit buttons, billing tabs, and appointment schedules.

---

### AI Agent Workspace
```
GET /patients/1/agents
```
➔ Returns an **Agent Workspace (JSON)** containing:

```json
{
  "agentML": "0.1",
  "workspace": {
    "title": "Patients Instance Agent Workspace",
    "resource": "/patients/1",
    "agent_resource": "/patients/1/agents"
  },
  "identity": {
    "role": "doctor",
    "user_id": "doc_88"
  },
  "state": {
    "id": 1,
    "name": "Aanya Sharma",
    "age": 34,
    "archived": false
  },
  "capabilities": [
    {
      "name": "UpdatePatientDetails",
      "description": "Modify name or age of an existing patient",
      "fields": [
        {
          "name": "name",
          "type": "string",
          "required": true,
          "current": "Aanya Sharma"
        },
        {
          "name": "age",
          "type": "integer",
          "required": true,
          "current": 34,
          "constraints": {
            "ge": 0,
            "le": 120
          }
        }
      ]
    }
  ],
  "unavailable": [],
  "navigation": [
    {
      "label": "Billing",
      "agent_endpoint": "/billing/agents"
    },
    {
      "label": "Home",
      "agent_endpoint": "/agents"
    },
    {
      "label": "All Patients",
      "agent_endpoint": "/patients/agents"
    }
  ],
  "alerts": []
}
```

---

## Getting Started

### 1. Install
```bash
pip install agentml
```

### 2. Integrate in 2 Lines
```python
from fastapi import FastAPI
from agentML import AgentML

app = FastAPI()
agent = AgentML(app)  # That's it!
```

---

## Business Semantics (Optional Decorators)
Annotate your routes to provide business action definitions, dynamic alerts, and state-based unavailability:

```python
@app.post("/patients")
@agent.expose(
    action="RegisterPatient",
    description="Register a new patient with personal and demographic data"
)
async def create_patient(data: PatientCreate):
    ...

@app.put("/patients/{id}")
@agent.expose(
    action="UpdatePatientDetails",
    description="Modify name or age of an existing patient",
    unavailable_fn=lambda state, auth: "Cannot edit archived patient" if state.get("archived") else None
)
async def update_patient(id: int, data: PatientCreate):
    ...
```

---

## philosophy (AgentML Rule #1)
> **Never make the developer write the same thing twice.**

If the developer has already defined the database models, API routes, and Pydantic validators, AgentML automatically extracts:
- Dynamic workspaces.
- Field types & constraints (e.g. `ge`/`le` values, patterns, enums).
- Related resources.

---

## Ecosystem Fit
AgentML complements existing AI agent frameworks and tooling (like Claude, OpenAI Assistants, or MCP) by providing a resource-oriented interaction layer directly on standard HTTP.

---

## Roadmap
- **v0.1 (Current)**: OpenAPI-driven introspection, Pydantic field extraction, capability auto-inference, in-process ASGI state retrieval.
- **v0.2**: Constraints, query filters, and action side effects.
- **v0.3**: Contextual workspaces, relation-aware navigation, context-aware permissions.
- **v0.4**: Swagger-like Workspace interactive UI (`/agents/docs`).
