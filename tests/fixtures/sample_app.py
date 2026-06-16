from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from agentML import AgentML

app = FastAPI()
agent = AgentML(app)

class PatientCreate(BaseModel):
    name: str = Field(..., description="Full name of the patient")
    age: int = Field(..., ge=0, le=120)

class PatientResponse(BaseModel):
    id: int
    name: str
    age: int

class BillingGenerate(BaseModel):
    patient_id: int
    amount: float = Field(..., gt=0)

# Beautiful HTML wrapper
def render_html(title: str, content: str) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title} - AgentML</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 29, 49, 0.7);
            --border-color: rgba(59, 130, 246, 0.2);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.4);
            --success: #10b981;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        header {{
            width: 100%;
            max-width: 1000px;
            padding: 2rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            box-sizing: border-box;
        }}
        .logo {{
            font-size: 1.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #3b82f6, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .nav-links a {{
            color: var(--text-secondary);
            text-decoration: none;
            margin-left: 1.5rem;
            font-weight: 600;
            transition: color 0.3s;
        }}
        .nav-links a:hover {{
            color: var(--accent);
        }}
        main {{
            width: 100%;
            max-width: 1000px;
            padding: 3rem 1rem;
            box-sizing: border-box;
        }}
        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }}
        h1 {{
            font-size: 2.5rem;
            font-weight: 800;
            margin-top: 0;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #ffffff, #9ca3af);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p {{
            color: var(--text-secondary);
            line-height: 1.6;
            font-size: 1.1rem;
        }}
        .btn {{
            background: linear-gradient(135deg, var(--accent), #1d4ed8);
            color: white;
            border: none;
            padding: 0.8rem 1.8rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 20px var(--accent-glow);
        }}
        .badge {{
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
            padding: 0.4rem 1rem;
            border-radius: 50px;
            font-size: 0.9rem;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 1.5rem;
        }}
        .table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 2rem;
        }}
        .table th, .table td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        .table th {{
            color: var(--text-secondary);
            font-weight: 600;
        }}
        .table tr:hover td {{
            color: #ffffff;
            background: rgba(59, 130, 246, 0.05);
        }}
        .detail-item {{
            margin-bottom: 1rem;
            font-size: 1.1rem;
        }}
        .detail-label {{
            color: var(--text-secondary);
            font-weight: 600;
            margin-right: 0.5rem;
        }}
    </style>
</head>
<body>
    <header>
        <div class="logo">AgentML</div>
        <div class="nav-links">
            <a href="/">Home</a>
            <a href="/patients">Patients</a>
            <a href="/agents" style="color: #10b981;">/agents</a>
        </div>
    </header>
    <main>
        {content}
    </main>
</body>
</html>"""
    return HTMLResponse(content=html)

# User routes
@app.get("/")
async def root(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        content = """
        <div class="card">
            <span class="badge">Convention Active</span>
            <h1>HTML for Humans.<br>AgentML for AI.</h1>
            <p>Welcome to the AgentML sample application. Humans view styled pages at standard URLs, while AI agents consume clean, structured, and action-ready views by appending <code>/agents</code>.</p>
            <div style="margin-top: 2rem;">
                <a href="/patients" class="btn">View Human UI</a>
                <a href="/agents" class="btn" style="background: linear-gradient(135deg, #10b981, #059669); margin-left: 1rem;">View AgentML UI</a>
            </div>
        </div>
        """
        return render_html("Home", content)
    return {"message": "Welcome to AgentML"}

@app.get("/patients")
@agent.expose(action="ListPatients", description="Retrieve all patients registered in the clinic system")
async def list_patients(request: Request, q: Optional[str] = None):
    # For testing, we return an empty list if not HTML. But for human UI, let's show some demo patients.
    if "text/html" in request.headers.get("accept", ""):
        content = """
        <div class="card">
            <h1>Patients Directory</h1>
            <p>List of currently registered patients in the medical system.</p>
            <table class="table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Age</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>Aanya Sharma</td>
                        <td>34</td>
                        <td><a href="/patients/1" class="btn" style="padding: 0.4rem 1rem; font-size: 0.9rem;">View Profile</a></td>
                    </tr>
                    <tr>
                        <td>2</td>
                        <td>John Doe</td>
                        <td>30</td>
                        <td><a href="/patients/2" class="btn" style="padding: 0.4rem 1rem; font-size: 0.9rem;">View Profile</a></td>
                    </tr>
                </tbody>
            </table>
            <div style="margin-top: 2rem;">
                <a href="/patients/agents" class="btn" style="background: linear-gradient(135deg, #10b981, #059669);">View as AgentML</a>
            </div>
        </div>
        """
        return render_html("Patients", content)
    # Default JSON return matching the test client requirements
    if q:
        return [{"id": 1, "name": q, "age": 20}]
    return []

@app.post("/patients", response_model=PatientResponse)
@agent.expose(action="RegisterPatient", description="Register a new patient with personal and demographic data")
async def create_patient(data: PatientCreate):
    """Create a new patient."""
    return {"id": 1, "name": data.name, "age": data.age}

@app.get("/patients/{id}", response_model=PatientResponse)
@agent.expose(action="ViewPatientDetails", description="Fetch the demographic profile of a single patient by ID")
async def get_patient(id: int, request: Request):
    """Get patient details."""
    if "text/html" in request.headers.get("accept", ""):
        name = "Aanya Sharma" if id == 1 else "John Doe"
        age = 34 if id == 1 else 30
        content = f"""
        <div class="card">
            <span class="badge">Patient ID: {id}</span>
            <h1>Patient Profile</h1>
            <div style="margin: 2rem 0;">
                <div class="detail-item"><span class="detail-label">Full Name:</span> {name}</div>
                <div class="detail-item"><span class="detail-label">Age:</span> {age} years old</div>
                <div class="detail-item"><span class="detail-label">Status:</span> Active / Insured</div>
            </div>
            <div>
                <a href="/patients" class="btn" style="background: #4b5563;">Back to List</a>
                <a href="/patients/{id}/agents" class="btn" style="background: linear-gradient(135deg, #10b981, #059669); margin-left: 1rem;">View as AgentML</a>
            </div>
        </div>
        """
        return render_html(f"Patient {id}", content)
    # Default JSON return
    return {"id": id, "name": "John Doe" if id != 1 else "Aanya Sharma", "age": 30 if id != 1 else 34}

@app.put("/patients/{id}", response_model=PatientResponse)
@agent.expose(action="UpdatePatientDetails", description="Modify name or age of an existing patient")
async def update_patient(id: int, data: PatientCreate):
    """Update patient details."""
    return {"id": id, "name": data.name, "age": data.age}

@app.delete("/patients/{id}")
@agent.expose(action="ArchivePatient", description="Remove or archive a patient record from the database")
async def delete_patient(id: int):
    """Delete a patient."""
    return {"status": "deleted"}

@app.post("/billing/generate")
@agent.expose(action="GenerateInvoice", description="Compute and issue an invoice for patient billing")
async def generate_billing(data: BillingGenerate):
    """Generate invoice for a patient."""
    return {"invoice_id": 123}

@app.get("/patients/{id}/appointments")
@agent.expose(action="ListPatientAppointments", description="Retrieve scheduled appointments for a patient")
async def list_patient_appointments(id: int):
    return [{"appointment_id": 101, "patient_id": id}]

