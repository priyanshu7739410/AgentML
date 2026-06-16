# AgentML

> **AgentML is a universal rendering convention for AI agents.**
> The same way browsers render HTML into a visual experience for humans, AgentML renders a complete agent-page/workspace for AI — context, state, permissions, actions, guidance, navigation — everything an agent needs to understand where it is and what it can do, in one response.

---

## Quickstart

### 1. Install
```bash
pip install agentml
```

### 2. Setup in 3 Lines
```python
from fastapi import FastAPI
from agentML import AgentML

app = FastAPI()
agent = AgentML(app)
agent.add_middleware() # Enables mutation response semantics
```

---

## 1. Mutation Enriched Response (POST /patients)
When an agent performs an action (e.g. `POST /patients`) and sends the header `Accept: application/vnd.agentml+json`, AgentML intercepts the response to tell the agent exactly what changed (`delta`), where the resource now lives (`agent_resource`), and what actions are available next (`transitions`):

```http
POST /patients
Accept: application/vnd.agentml+json
Content-Type: application/json

{
  "name": "Aanya Sharma",
  "age": 34
}
```

**Response:**
```json
{
  "result": {
    "id": 42,
    "name": "Aanya Sharma",
    "age": 34
  },
  "delta": {
    "name": "Aanya Sharma",
    "age": 34
  },
  "agent_resource": "/patients/42/agents",
  "actions": [
    {
      "name": "UpdatePatientDetails",
      "agent_endpoint": "/patients/42/agents"
    },
    {
      "name": "ViewPatientDetails",
      "agent_endpoint": "/patients/42/agents"
    },
    {
      "name": "ArchivePatient",
      "agent_endpoint": "/patients/42/agents"
    }
  ],
  "navigation": [
    {
      "label": "Appointments",
      "agent_endpoint": "/patients/42/appointments/agents"
    },
    {
      "label": "Billing",
      "agent_endpoint": "/billing/agents"
    },
    {
      "label": "Home",
      "agent_endpoint": "/agents"
    }
  ]
}
```

---

## 2. Resource Workspace (GET /patients/42/agents)
When an agent navigates to the resulting `agent_resource`, they receive a complete state-aware workspace:

```http
GET /patients/42/agents
```

**Response:**
```json
{
  "agentML": "0.1",
  "workspace": {
    "title": "Patients Instance Agent Workspace",
    "resource": "/patients/42",
    "agent_resource": "/patients/42/agents",
    "breadcrumb": ["Home", "Patients", "Patient 42"]
  },
  "identity": {
    "role": "doctor",
    "user_id": "doc_88"
  },
  "state": {
    "id": 42,
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
      "label": "Appointments",
      "agent_endpoint": "/patients/42/appointments/agents"
    },
    {
      "label": "Billing",
      "agent_endpoint": "/billing/agents"
    },
    {
      "label": "Home",
      "agent_endpoint": "/agents"
    }
  ],
  "alerts": [],
  "guidance": []
}
```

### Understanding the Workspace Blocks
- **`workspace`**: Native location context containing the human URL, the agent URL, and path breadcrumbs.
- **`identity`**: The dynamic security credentials and role context for the current request.
- **`state`**: The serialized current resource state fetched in-process.
- **`capabilities`**: Permitted business-language actions (never HTTP verbs) with dynamic schema validation rules and pre-filled current values.
- **`unavailable`**: Actions that are temporarily disabled due to the current resource state, complete with explanations.
- **`navigation`**: Context-aware sibling and sub-resource links matching the instance's active ID.
- **`alerts`**: Banner notifications or warning details generated dynamically based on state.

---

## Philosophy: HTML for Humans, AgentML for AI

The web was built for human eyes. AI agents are currently forced to parse layout-heavy HTML, guess dynamic form flows, and reverse-engineer endpoints.

AgentML introduces a simple, universal web rendering convention: **append `/agents` to any HTTP resource.**
A browser requests a resource and gets human-friendly HTML. An AI agent requests the same resource + `/agents` (or issues mutations requesting the `vnd.agentml+json` payload) and gets a structured, action-ready Agent Workspace.

---

## Core Features

- **Relational Navigation**: Context-aware nested resources (e.g. `/patients/42/agents` links to `/patients/42/appointments/agents` substituting the identifier automatically).
- **Mutation Semantics (v0.4)**: Mutation writes return execution feedback, updated state deltas, and structured action and navigation lists to eliminate agent state blindness.
- **Invisible-by-Design RBAC**: Permissions are evaluated at render-time; capabilities the agent is unauthorized to perform are completely absent.
- **Zero HTTP Verbs**: All actions are presented in clean business terminology (e.g. `RegisterPatient` instead of `POST /patients`).
- **Fail-Closed Safety**: Dynamic safety check hooks (`unavailable_fn`) default to blocked state on exceptions.
- **Pydantic Validation**: Auto-extracts field types, constraints (`ge`, `le`, patterns, enums) and pre-fills current state values.
