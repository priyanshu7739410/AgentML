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
        assert "transitions" in data
        
        # Result matches original response
        assert data["result"]["name"] == "Alice"
        assert data["result"]["age"] == 25
        assert data["result"]["id"] == 1
        
        # Delta contains request inputs returned in response
        assert data["delta"] == {"name": "Alice", "age": 25}
        
        # Explicit returns="/patients/{id}" resolved using result["id"] (1)
        assert data["agent_resource"] == "/patients/1/agents"
        
        # Transitions contains capabilities of the matched patient profile workspace
        # /patients/1/agents has capabilities like UpdatePatientDetails, ViewPatientDetails, ArchivePatient
        transitions = {t["action"]: t["agent_endpoint"] for t in data["transitions"]}
        assert "UpdatePatientDetails" in transitions
        assert "ViewPatientDetails" in transitions
        assert "ArchivePatient" in transitions

def test_mutation_enriched_response_put():
    with TestClient(app) as client:
        headers = {"Accept": "application/vnd.agentml+json"}
        # Put updates patient details
        response = client.put("/patients/1", json={"name": "Bob", "age": 30}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["result"]["name"] == "Bob"
        assert data["result"]["age"] == 30
        assert data["delta"] == {"name": "Bob", "age": 30}
        assert data["agent_resource"] == "/patients/1/agents"
        
        transitions = {t["action"]: t["agent_endpoint"] for t in data["transitions"]}
        assert "UpdatePatientDetails" in transitions
        assert "ViewPatientDetails" in transitions

def test_mutation_enriched_response_delete_fallback():
    with TestClient(app) as client:
        headers = {"Accept": "application/vnd.agentml+json"}
        # Delete patient 1
        response = client.delete("/patients/1", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["result"] == {"status": "deleted"}
        # Falls back to path since there's no id in response or returns on delete decorator
        assert data["agent_resource"] == "/patients/1/agents"
