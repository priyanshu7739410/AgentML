from fastapi.testclient import TestClient
from tests.fixtures.sample_app import app

def test_mutation_passthrough_no_header():
    with TestClient(app) as client:
        # Standard POST request without custom Accept header should return normal response
        response = client.post("/patients", json={"name": "Alice", "age": 25})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "delta" not in data  # No enrichment

def test_mutation_enriched_response_post():
    with TestClient(app) as client:
        # Request with Accept: application/vnd.agentml+json should return enriched payload
        headers = {"Accept": "application/vnd.agentml+json"}
        response = client.post("/patients", json={"name": "Alice", "age": 25}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "result" in data
        assert "delta" in data
        assert "agent_resource" in data
        assert "actions" in data
        assert "navigation" in data
        assert "transitions" not in data  # transitions must be removed
        
        # Result matches original response
        assert data["result"]["name"] == "Alice"
        assert data["result"]["age"] == 25
        assert data["result"]["id"] == 1
        
        # Delta contains request inputs returned in response
        assert data["delta"] == {"name": "Alice", "age": 25}
        
        # Explicit returns="/patients/{id}" resolved using result["id"] (1)
        assert data["agent_resource"] == "/patients/1/agents"
        
        # Actions contains capabilities of the matched patient profile workspace
        # /patients/1/agents has capabilities like UpdatePatientDetails, ViewPatientDetails, ArchivePatient
        actions = {a["name"]: a["agent_endpoint"] for a in data["actions"]}
        assert "UpdatePatientDetails" in actions
        assert "ViewPatientDetails" in actions
        assert "ArchivePatient" in actions

        # Navigation contains label-based links
        navigation = {n["label"]: n["agent_endpoint"] for n in data["navigation"]}
        assert "Appointments" in navigation
        assert "Billing" in navigation
        assert "Home" in navigation

def test_mutation_enriched_response_put():
    with TestClient(app) as client:
        headers = {"Accept": "application/vnd.agentml+json"}
        # Put updates patient details
        response = client.put("/patients/1", json={"name": "Bob", "age": 30}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "actions" in data
        assert "navigation" in data
        assert "transitions" not in data
        
        assert data["result"]["name"] == "Bob"
        assert data["result"]["age"] == 30
        assert data["delta"] == {"name": "Bob", "age": 30}
        assert data["agent_resource"] == "/patients/1/agents"
        
        actions = {a["name"]: a["agent_endpoint"] for a in data["actions"]}
        assert "UpdatePatientDetails" in actions
        assert "ViewPatientDetails" in actions

        navigation = {n["label"]: n["agent_endpoint"] for n in data["navigation"]}
        assert "Appointments" in navigation
        assert "Billing" in navigation

def test_mutation_enriched_response_delete_fallback():
    with TestClient(app) as client:
        headers = {"Accept": "application/vnd.agentml+json"}
        # Delete patient 1
        response = client.delete("/patients/1", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "actions" in data
        assert "navigation" in data
        assert "transitions" not in data
        
        assert data["result"] == {"status": "deleted"}
        # Falls back to path since there's no id in response or returns on delete decorator
        assert data["agent_resource"] == "/patients/1/agents"
