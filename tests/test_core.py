from fastapi.testclient import TestClient
from tests.fixtures.sample_app import app

def test_existing_routes_unaltered():
    with TestClient(app) as client:
        # Test GET /patients
        response = client.get("/patients")
        assert response.status_code == 200
        assert response.json() == []
        
        # Test POST /patients
        response = client.post("/patients", json={"name": "Alice", "age": 25})
        assert response.status_code == 200
        assert response.json() == {"id": 1, "name": "Alice", "age": 25}

def test_root_agents_endpoint():
    with TestClient(app) as client:
        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        
        assert data["agentML"] == "0.1"
        assert data["workspace"]["title"] == "Root Agent Workspace"
        assert data["workspace"]["resource"] == "/"
        assert data["workspace"]["agent_resource"] == "/agents"
        
        # Capabilities should not contain HTTP verbs
        for cap in data["capabilities"]:
            for verb in ("POST", "GET", "PUT", "DELETE", "PATCH"):
                assert verb not in cap["name"]
                
        # Navigation links should end with /agents
        for nav in data["navigation"]:
            assert nav["agent_endpoint"].endswith("/agents")

def test_resource_agents_endpoint():
    with TestClient(app) as client:
        response = client.get("/patients/agents")
        assert response.status_code == 200
        data = response.json()
        
        assert data["workspace"]["title"] == "Patients Agent Workspace"
        assert data["workspace"]["resource"] == "/patients"
        assert data["workspace"]["agent_resource"] == "/patients/agents"
        
        # Check that only patient capabilities are returned
        cap_names = [cap["name"] for cap in data["capabilities"]]
        assert len(cap_names) > 0
        for name in cap_names:
            assert "Patient" in name
        
def test_instance_agents_endpoint():
    with TestClient(app) as client:
        response = client.get("/patients/42/agents")
        assert response.status_code == 200
        data = response.json()
        
        assert data["workspace"]["title"] == "Patients Instance Agent Workspace"
        assert data["workspace"]["resource"] == "/patients/42"
        assert data["workspace"]["agent_resource"] == "/patients/42/agents"
        assert data["state"] == {"id": 42, "name": "John Doe", "age": 30}

def test_query_parameters_forwarding():
    with TestClient(app) as client:
        response = client.get("/patients/agents?q=Bob")
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == {"items": [{"id": 1, "name": "Bob", "age": 20}]}

def test_last_action_feedback_header():
    with TestClient(app) as client:
        # Pass a JSON string in X-AgentML-Last-Action header
        response = client.get(
            "/patients/agents",
            headers={"X-AgentML-Last-Action": '{"mutated": true, "id": 1}'}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback"] == {"mutated": True, "id": 1}

        # Pass non-JSON text in X-AgentML-Last-Action header
        response2 = client.get(
            "/patients/agents",
            headers={"X-AgentML-Last-Action": "raw_feedback_string"}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["feedback"] == {"result": "raw_feedback_string"}

def test_v03_relational_navigation_and_breadcrumbs():
    with TestClient(app) as client:
        # Test root resource map
        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        
        # capabilities should be empty, and resources should contain the map
        assert len(data["capabilities"]) == 0
        assert len(data["resources"]) > 0
        
        res_map = {r["name"]: r for r in data["resources"]}
        assert "Patients" in res_map
        assert res_map["Patients"]["agent_endpoint"] == "/patients/agents"
        # Total endpoints under /patients (list_patients, create_patient, get_patient, update_patient, delete_patient, list_patient_appointments)
        assert res_map["Patients"]["action_count"] == 6

        # Test breadcrumbs and instance-scoped navigation
        response2 = client.get("/patients/42/agents")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Breadcrumbs
        assert data2["workspace"]["breadcrumb"] == ["Home", "Patients", "Patient 42"]
        
        # Instance-scoped navigation
        nav_endpoints = {n["label"]: n["agent_endpoint"] for n in data2["navigation"]}
        assert "Appointments" in nav_endpoints
        assert nav_endpoints["Appointments"] == "/patients/42/appointments/agents"



