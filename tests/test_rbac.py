import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add Pro-Versed directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
pro_versed_dir = os.path.join(parent_dir, "Pro-Versed")
if pro_versed_dir not in sys.path:
    sys.path.insert(0, pro_versed_dir)

from backend.main import app

client = TestClient(app)

def test_student_allowed_to_buy_marketplace_item():
    """
    Feature 2: Allow Students to purchase hardware items under Student Escrow Protection.
    POST /api/bazaar/items/{item_id}/escrow with actor_role='student' and action='lock' -> 200 OK (Step 2, In Escrow).
    """
    # Fetch first available item
    res = client.get("/api/bazaar/items")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    item_id = items[0]["id"]

    # Student initiates escrow order
    escrow_payload = {
        "action": "lock",
        "actor_id": "usr_student_1",
        "actor_role": "student",
        "actor_name": "Aarav Sharma",
        "actor_college": "IIT Bombay",
        "buyer_id": "usr_student_1",
        "buyer_name": "Aarav Sharma",
        "buyer_company": "IIT Bombay"
    }
    resp = client.post(f"/api/bazaar/items/{item_id}/escrow", json=escrow_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["escrow_step"] == 2
    assert data["status"] == "In Escrow"
    assert data["escrow_buyer_id"] == "usr_student_1"


def test_enterprise_buyer_allowed_to_buy_marketplace_item():
    """
    Enterprise buyers / industrialists CAN lock escrow.
    """
    res = client.get("/api/bazaar/items")
    assert res.status_code == 200
    items = res.json()
    item_id = items[0]["id"]

    escrow_payload = {
        "action": "hold_escrow",
        "actor_id": "usr_industrialist_1",
        "actor_role": "industrialist",
        "buyer_id": "usr_industrialist_1",
        "buyer_name": "Vikram Singhania",
        "buyer_company": "Tata Elxsi"
    }
    resp = client.post(f"/api/bazaar/items/{item_id}/escrow", json=escrow_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["escrow_step"] == 2
    assert data["status"] == "In Escrow"

def test_faculty_mentor_cannot_submit_project():
    """
    Requirement 5: Faculty mentors cannot submit projects (403 Forbidden).
    """
    project_payload = {
        "title": "Quantum Neural Network Optimizer for Autonomous Drones",
        "abstract": "Hybrid quantum computing algorithm designed for low-power edge robotics.",
        "domain": "AI & Robotics",
        "category": "Software IP / Model",
        "tech_stack": ["Qiskit", "Python", "PyTorch"],
        "college_name": "IISc Bangalore",
        "team_lead_id": "usr_faculty_1",
        "team_lead_name": "Dr. Sunita Raman"
    }
    resp = client.post("/api/projects", json=project_payload)
    assert resp.status_code == 403
    assert "Only registered students or platform administrators may submit new projects" in resp.json()["detail"]

def test_campus_spoc_cannot_submit_project():
    """
    Requirement 5: Campus SPOCs cannot submit projects (403 Forbidden).
    """
    project_payload = {
        "title": "Solid State Lithium Sulfur Battery Cells",
        "abstract": "High energy density nano-composite cathode battery architecture.",
        "domain": "Green Tech & Energy",
        "category": "Hardware Prototype",
        "tech_stack": ["COMSOL", "MaterialStudio"],
        "college_name": "NIT Trichy",
        "team_lead_id": "usr_spoc_1",
        "team_lead_name": "Prof. R. K. Mukherjee"
    }
    resp = client.post("/api/projects", json=project_payload)
    assert resp.status_code == 403
    assert "Only registered students or platform administrators may submit new projects" in resp.json()["detail"]

def test_industrial_partner_cannot_submit_project():
    """
    Requirement 5: Industrial Partners cannot submit projects (403 Forbidden).
    """
    project_payload = {
        "title": "Commercial Enterprise ERP Integration Engine",
        "abstract": "Proprietary industrial supply chain optimization system.",
        "domain": "FinTech & Security",
        "category": "Software IP / Model",
        "tech_stack": ["Go", "Kubernetes"],
        "college_name": "Tata Elxsi",
        "team_lead_id": "usr_industrialist_1",
        "team_lead_name": "Vikram Singhania"
    }
    resp = client.post("/api/projects", json=project_payload)
    assert resp.status_code == 403
    assert "Only registered students or platform administrators may submit new projects" in resp.json()["detail"]

def test_student_allowed_to_submit_project():
    """
    Requirement 5: Students CAN submit projects (200 OK).
    """
    project_payload = {
        "title": f"Bio-Degradable Agro-Sensor Network for Smart Farming",
        "abstract": "Low-cost wireless sensor network using starch-based PCB boards for precision agriculture.",
        "domain": "Smart Cities & IoT",
        "category": "Hybrid (IoT / Embedded)",
        "tech_stack": ["ESP32", "LoRaWAN", "C++"],
        "college_name": "IIT Bombay",
        "team_lead_id": "usr_student_1",
        "team_lead_name": "Aarav Sharma"
    }
    resp = client.post("/api/projects", json=project_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == project_payload["title"]
    assert data["team_lead_id"] == "usr_student_1"
    assert data["originality_score"] > 0
