# AgentML 🚀

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
