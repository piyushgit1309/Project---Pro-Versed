"""
PRO-VERSED — Comprehensive P0-02 Project Authorization & IDOR Regression Test Suite
Validates anti-enumeration (404), ownership enforcement, field-level authorization,
mass assignment prevention, and session identity binding against PostgreSQL.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend modules are accessible
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pv_backend_dir = os.path.join(root_dir, "Pro-Versed", "backend")
pv_dir = os.path.join(root_dir, "Pro-Versed")
for p in [pv_backend_dir, pv_dir, root_dir]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from main import app
from database import init_db, get_db_session, SessionLocal
from models import UserORM, ProjectORM, SessionORM
from auth import hash_password, create_user_session

client = TestClient(app)


def create_authenticated_user_session(email: str, role: str, name: str, user_id: str) -> str:
    """Helper to create or get a user and establish an active session token."""
    db = SessionLocal()
    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        pwhash, pwsalt = hash_password("Password123!")
        user = UserORM(
            id=user_id,
            name=name,
            email=email,
            role=role,
            college="Indian Institute of Technology (IIT) Bombay",
            password_hash=pwhash,
            password_salt=pwsalt,
            is_active=1,
            created_at="2026-01-01T00:00:00"
        )
        db.add(user)
        db.commit()

    session_info = create_user_session(
        db,
        user_id=user_id,
        ip_address="127.0.0.1",
        user_agent="Pytest-Client",
        remember_me=True
    )
    db.commit()
    db.close()
    return session_info["session_id"]


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Initializes schema and resets database baseline."""
    init_db()
    yield


# ==========================================
# 1. AUTHENTICATION & SESSION GUARDS (401)
# ==========================================

def test_unauthenticated_project_update_returns_401():
    """Unauthenticated requests to PUT /api/projects/{id} must return 401 Unauthorized."""
    res = client.put("/api/projects/proj_001", json={
        "title": "Malicious Unauthenticated Title Update"
    })
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]

    # Verify database was NOT modified
    with get_db_session() as session:
        proj = session.query(ProjectORM).filter(ProjectORM.id == "proj_001").first()
        assert proj is not None
        assert proj.title != "Malicious Unauthenticated Title Update"


def test_invalid_or_expired_session_returns_401():
    """Requests with forged or invalid session tokens return 401 Unauthorized."""
    headers = {"Authorization": "Bearer invalid_forged_session_token_xyz"}
    res = client.put("/api/projects/proj_001", json={
        "title": "Malicious Forged Token Title"
    }, headers=headers)
    assert res.status_code == 401
    assert "Session is invalid" in res.json()["detail"]


# ==========================================
# 2. HORIZONTAL IDOR & ANTI-ENUMERATION (404)
# ==========================================

def test_student_a_cannot_update_student_b_project_returns_404():
    """
    Student B attempting to update Student A's project returns 404 Not Found (anti-enumeration).
    Guarantees no horizontal privilege escalation and no database modification.
    """
    # Create Student B (attacker)
    token_b = create_authenticated_user_session(
        email="student_b_attacker@iitd.ac.in",
        role="student",
        name="Student Attacker",
        user_id="usr_student_attacker_99"
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # proj_001 is owned by usr_student_1 (Aarav Patel)
    original_title = ""
    with get_db_session() as session:
        proj = session.query(ProjectORM).filter(ProjectORM.id == "proj_001").first()
        assert proj is not None
        assert proj.team_lead_id == "usr_student_1"
        original_title = proj.title

    # Student B attempts to overwrite proj_001
    res = client.put("/api/projects/proj_001", json={
        "title": "Hacked Title By Student B",
        "description": "Compromised abstract and repository"
    }, headers=headers_b)

    assert res.status_code == 404
    assert res.json()["detail"] == "Project not found"

    # Verify database record was strictly NOT changed
    with get_db_session() as session:
        proj_after = session.query(ProjectORM).filter(ProjectORM.id == "proj_001").first()
        assert proj_after.title == original_title
        assert "Hacked Title" not in proj_after.title


# ==========================================
# 3. LEGITIMATE OWNER & ADMIN UPDATES (200)
# ==========================================

def test_student_owner_can_update_own_project_returns_200():
    """The legitimate project owner (team_lead_id) can update permissible metadata."""
    token_owner = create_authenticated_user_session(
        email="aarav@cse.iitb.ac.in",
        role="student",
        name="Aarav Patel",
        user_id="usr_student_1"
    )
    headers_owner = {"Authorization": f"Bearer {token_owner}"}

    new_title = "AeroGuard: Autonomous Solar-Powered UAV — Upgraded 2026 Edition"
    res = client.put("/api/projects/proj_001", json={
        "title": new_title,
        "description": "Updated high-efficiency drone propulsion specifications."
    }, headers=headers_owner)

    assert res.status_code == 200
    data = res.json()
    assert data["title"] == new_title

    # Verify persistence in PostgreSQL
    with get_db_session() as session:
        proj = session.query(ProjectORM).filter(ProjectORM.id == "proj_001").first()
        assert proj.title == new_title


def test_admin_can_update_any_project_returns_200():
    """Platform Administrator has administrative override to update any project."""
    token_admin = create_authenticated_user_session(
        email="admin@proved.gov.in",
        role="admin",
        name="Dr. Rajesh Verma",
        user_id="usr_admin_1"
    )
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    admin_title = "AeroGuard: Administrative Verified Title"
    res = client.put("/api/projects/proj_001", json={
        "title": admin_title
    }, headers=headers_admin)

    assert res.status_code == 200
    assert res.json()["title"] == admin_title


# ==========================================
# 4. CREATION & IDENTITY BINDING (POST)
# ==========================================

def test_forged_team_lead_id_cannot_transfer_ownership():
    """
    Authenticated Student A creating a project with a forged team_lead_id in request body
    is strictly bound to Student A's own verified session user ID.
    """
    token_student = create_authenticated_user_session(
        email="aarav@cse.iitb.ac.in",
        role="student",
        name="Aarav Patel",
        user_id="usr_student_1"
    )
    headers = {"Authorization": f"Bearer {token_student}"}

    # Attempt to spoof team_lead_id as another victim user
    res = client.post("/api/projects", json={
        "title": "Quantum Sensor Security Subsystem",
        "abstract": "High precision quantum magnetometer for industrial fault detection.",
        "domain": "Hardware & Embedded",
        "category": "Hardware Prototype",
        "tech_stack": ["C++", "VHDL"],
        "team_lead_id": "usr_victim_spoofed_id_999",
        "team_lead_name": "Victim User"
    }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    # Verified: Ownership is bound to the session owner (usr_student_1), NOT the forged body ID
    assert data["team_lead_id"] == "usr_student_1"
    assert data["team_lead_name"] == "Aarav Patel"


def test_faculty_cannot_submit_project_returns_403():
    """Faculty members cannot submit new projects."""
    token_faculty = create_authenticated_user_session(
        email="sunita.sharma@ece.iisc.ac.in",
        role="faculty",
        name="Dr. Sunita Sharma",
        user_id="usr_faculty_1"
    )
    headers = {"Authorization": f"Bearer {token_faculty}"}

    res = client.post("/api/projects", json={
        "title": "Faculty Research Initiative",
        "abstract": "Theoretical analysis of dielectric resonators.",
        "domain": "AI & Robotics",
        "category": "Software IP / Model",
        "tech_stack": ["Python"]
    }, headers=headers)

    assert res.status_code == 403
    assert "Only registered students" in res.json()["detail"]


def test_spoc_cannot_submit_project_returns_403():
    """Campus SPOCs cannot submit new projects."""
    token_spoc = create_authenticated_user_session(
        email="spoc.rnd@coep.ac.in",
        role="spoc",
        name="Prof. Anil Sahasrabudhe",
        user_id="usr_spoc_1"
    )
    headers = {"Authorization": f"Bearer {token_spoc}"}

    res = client.post("/api/projects", json={
        "title": "Institutional Battery Research",
        "abstract": "Solid state composite cathode evaluation.",
        "domain": "Green Tech & Energy",
        "category": "Hardware Prototype",
        "tech_stack": ["COMSOL"]
    }, headers=headers)

    assert res.status_code == 403


def test_industry_partner_cannot_submit_project_returns_403():
    """Industry Partners cannot submit student innovation projects."""
    token_ind = create_authenticated_user_session(
        email="vikram@tataelxsi.co.in",
        role="industrialist",
        name="Vikramaditya Singhania",
        user_id="usr_industrialist_1"
    )
    headers = {"Authorization": f"Bearer {token_ind}"}

    res = client.post("/api/projects", json={
        "title": "Enterprise Commercial Pipeline",
        "abstract": "Corporate internal supply chain tracking.",
        "domain": "FinTech & Security",
        "category": "Software IP / Model",
        "tech_stack": ["Go"]
    }, headers=headers)

    assert res.status_code == 403


# ==========================================
# 5. FIELD-LEVEL AUTHORIZATION & MASS ASSIGNMENT
# ==========================================

def test_student_cannot_set_privileged_patent_status_returns_403():
    """Students cannot set authoritative patent status (e.g. 'Granted', 'Filed')."""
    token_owner = create_authenticated_user_session(
        email="aarav@cse.iitb.ac.in",
        role="student",
        name="Aarav Patel",
        user_id="usr_student_1"
    )
    headers = {"Authorization": f"Bearer {token_owner}"}

    res = client.put("/api/projects/proj_001", json={
        "patent_status": "Granted"
    }, headers=headers)

    assert res.status_code == 403
    assert "patent status" in res.json()["detail"].lower()


def test_student_cannot_set_privileged_lifecycle_status_returns_403():
    """Students cannot set privileged lifecycle transitions (e.g. 'Commercialized', 'IP_Transferred')."""
    token_owner = create_authenticated_user_session(
        email="aarav@cse.iitb.ac.in",
        role="student",
        name="Aarav Patel",
        user_id="usr_student_1"
    )
    headers = {"Authorization": f"Bearer {token_owner}"}

    res = client.put("/api/projects/proj_001", json={
        "lifecycle_status": "Commercialized"
    }, headers=headers)

    assert res.status_code == 403
    assert "lifecycle" in res.json()["detail"].lower()


def test_admin_can_set_privileged_patent_and_lifecycle_statuses():
    """Administrators can set privileged patent and lifecycle statuses."""
    token_admin = create_authenticated_user_session(
        email="admin@proved.gov.in",
        role="admin",
        name="Dr. Rajesh Verma",
        user_id="usr_admin_1"
    )
    headers = {"Authorization": f"Bearer {token_admin}"}

    res = client.put("/api/projects/proj_001", json={
        "patent_status": "Granted",
        "lifecycle_status": "Commercialized"
    }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["patent_status"] == "Granted"
    assert data["lifecycle_status"] == "Commercialized"
