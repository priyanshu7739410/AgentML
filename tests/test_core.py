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
