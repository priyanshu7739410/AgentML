from fastapi import FastAPI
from pydantic import BaseModel, Field
from agentML.introspector import get_routes, extract_fields
from tests.fixtures.sample_app import app, PatientCreate

def test_get_routes():
    routes = get_routes(app)
    paths = [r.path for r in routes]
    
    # Assert human endpoints are present
    assert "/patients" in paths
    assert "/patients/{id}" in paths
    assert "/billing/generate" in paths
    
    # Assert agent/docs endpoints are ignored
    assert "/agents" not in paths
    assert "/patients/agents" not in paths
    assert "/docs" not in paths

def test_extract_fields():
    fields = extract_fields(PatientCreate)
    fields_dict = {f.name: f for f in fields}
    
    assert "name" in fields_dict
    assert fields_dict["name"].type == "string"
    assert fields_dict["name"].required is True
    assert fields_dict["name"].description == "Full name of the patient"
    
    assert "age" in fields_dict
    assert fields_dict["age"].type == "integer"
    assert fields_dict["age"].required is True
    assert fields_dict["age"].constraints["ge"] == 0
    assert fields_dict["age"].constraints["le"] == 120

def test_infer_capability_name_exceptions():
    from agentML.inference import infer_capability_name
    assert infer_capability_name("GET", "/api/address") == "ListAddress"
    assert infer_capability_name("GET", "/api/address/{id}") == "GetAddress"
    assert infer_capability_name("POST", "/api/status") == "CreateStatus"
    assert infer_capability_name("PUT", "/api/process/{id}") == "UpdateProcess"
    assert infer_capability_name("DELETE", "/api/class/{id}") == "DeleteClass"
    assert infer_capability_name("GET", "/api/patients") == "ListPatients"
    assert infer_capability_name("GET", "/api/patients/{id}") == "GetPatient"

