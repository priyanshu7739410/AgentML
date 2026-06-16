from agentML.renderer import render_agent_workspace
from agentML.auth import AuthContext
from agentML.introspector import get_routes
from tests.fixtures.sample_app import app

def test_renderer_root():
    routes = get_routes(app)
    auth = AuthContext(role="doctor", user_id="doc1")
    page = render_agent_workspace(
        resource_path="/agents",
        routes=routes,
        registry={},
        auth=auth,
        state={}
    )
    
    assert page.agentML == "0.1"
    assert page.workspace.title == "Root Agent Workspace"
    assert page.workspace.resource == "/"
    assert page.workspace.agent_resource == "/agents"
    assert page.identity.role == "doctor"
    assert page.identity.user_id == "doc1"
    
    # Root should show all sibling navigation links
    nav_endpoints = [n.agent_endpoint for n in page.navigation]
    assert "/patients/agents" in nav_endpoints
    assert "/billing/agents" in nav_endpoints

def test_renderer_prefix_filtering():
    routes = get_routes(app)
    auth = AuthContext()
    page = render_agent_workspace(
        resource_path="/patients/agents",
        routes=routes,
        registry={},
        auth=auth,
        state={}
    )
    
    assert page.workspace.title == "Patients Agent Workspace"
    assert page.workspace.resource == "/patients"
    assert page.workspace.agent_resource == "/patients/agents"
    
    # Capabilities should be only patient-related
    for cap in page.capabilities:
        assert "Patient" in cap.name
        # Ensure no HTTP verbs
        for verb in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            assert verb not in cap.name
            
    # Sibling navigation
    nav_endpoints = [n.agent_endpoint for n in page.navigation]
    assert "/billing/agents" in nav_endpoints
    assert "/agents" in nav_endpoints

def test_renderer_state_alerts_unavailable_meta():
    from agentML.decorators import ActionMeta
    from agentML.schema import Alert

    routes = get_routes(app)
    auth = AuthContext(role="doctor")
    
    # Mock registry with metadata
    registry = {
        "update_patient": ActionMeta(
            action="UpdatePatientDetails",
            unavailable_fn=lambda state, auth: "Cannot edit archived patient" if state.get("archived") else None,
            alerts_fn=lambda state, auth: [Alert(level="warning", message="Patient is nearing limit")] if state.get("age", 0) > 100 else []
        )
    }

    # Test 1: Action unavailable and alert triggered
    state_archived = {"name": "Old Man", "age": 105, "archived": True}
    page = render_agent_workspace(
        resource_path="/patients/1/agents",
        routes=routes,
        registry=registry,
        auth=auth,
        state=state_archived
    )

    # Check alert is present
    assert len(page.alerts) == 1
    assert page.alerts[0].message == "Patient is nearing limit"

    # Check update capability is moved to unavailable
    unavailable_names = [u.name for u in page.unavailable]
    assert "UpdatePatientDetails" in unavailable_names
    assert page.unavailable[0].reason == "Cannot edit archived patient"

    # Ensure update is not in active capabilities
    cap_names = [c.name for c in page.capabilities]
    assert "UpdatePatientDetails" not in cap_names

    # Test 2: Field current values populated
    state_active = {"name": "Alice", "age": 25, "archived": False}
    page2 = render_agent_workspace(
        resource_path="/patients/1/agents",
        routes=routes,
        registry=registry,
        auth=auth,
        state=state_active
    )

    # Update should be active
    cap_dict = {c.name: c for c in page2.capabilities}
    assert "UpdatePatientDetails" in cap_dict
    
    # Check field current values
    fields_dict = {f.name: f for f in cap_dict["UpdatePatientDetails"].fields}
    assert fields_dict["name"].current == "Alice"
    assert fields_dict["age"].current == 25

    # Test 3: Meta block generated for collections
    page3 = render_agent_workspace(
        resource_path="/patients/agents",
        routes=routes,
        registry=registry,
        auth=auth,
        state={"items": [{"id": 1}, {"id": 2}]}
    )
    assert page3.meta is not None
    assert page3.meta.total == 2

def test_renderer_rbac():
    from agentML.decorators import ActionMeta

    routes = get_routes(app)
    
    # Register an action with specific roles
    registry = {
        "create_patient": ActionMeta(
            action="RegisterPatient",
            roles=["doctor", "admin"]
        ),
        "list_patients": ActionMeta(
            action="ListPatients"
        )
    }

    # Test with role that is allowed
    auth_doctor = AuthContext(role="doctor")
    page_doc = render_agent_workspace(
        resource_path="/patients/agents",
        routes=routes,
        registry=registry,
        auth=auth_doctor,
        state={}
    )
    cap_names_doc = [c.name for c in page_doc.capabilities]
    assert "RegisterPatient" in cap_names_doc
    assert "ListPatients" in cap_names_doc

    # Test with role that is NOT allowed
    auth_nurse = AuthContext(role="nurse")
    page_nurse = render_agent_workspace(
        resource_path="/patients/agents",
        routes=routes,
        registry=registry,
        auth=auth_nurse,
        state={}
    )
    cap_names_nurse = [c.name for c in page_nurse.capabilities]
    # RegisterPatient should be hidden for nurse (not in the list)
    assert "RegisterPatient" not in cap_names_nurse
    assert "ListPatients" in cap_names_nurse

def test_renderer_guidance_and_feedback():
    from agentML.decorators import ActionMeta

    routes = get_routes(app)
    
    registry = {
        "create_patient": ActionMeta(
            action="RegisterPatient",
            guidance=["Step 1: Check in", "Step 2: Collect vitals"]
        )
    }

    auth = AuthContext(role="doctor")
    
    # Check guidance and feedback are correctly rendered
    page = render_agent_workspace(
        resource_path="/patients/agents",
        routes=routes,
        registry=registry,
        auth=auth,
        state={},
        feedback={"status": "success", "id": 100}
    )
    
    assert page.guidance == ["Step 1: Check in", "Step 2: Collect vitals"]
    assert page.feedback == {"status": "success", "id": 100}


