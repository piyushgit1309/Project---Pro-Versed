"""
PRO-VERSED — Comprehensive P0-03 Industrial Offers Authorization & State Machine Test Suite
Tests multi-tenant scoping, buyer/lead commercial negotiations, financial validation,
buyer withdrawal, post-agreement SPOC institutional approval, and database invariants against PostgreSQL.
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
from models import UserORM, ProjectORM, IndustrialOfferORM
from auth import hash_password, create_user_session

client = TestClient(app)


def create_authenticated_user_session(email: str, role: str, name: str, user_id: str, college: str = "Indian Institute of Technology (IIT) Bombay") -> str:
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
            college=college,
            company=name if role == "industrialist" else None,
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
# 1. AUTHENTICATION GUARDS (401)
# ==========================================

def test_unauthenticated_requests_return_401():
    """Unauthenticated calls to list, submit, or update offers return 401."""
    # List
    res_list = client.get("/api/industrial/offers")
    assert res_list.status_code == 401

    # Submit
    res_post = client.post("/api/industrial/offers", json={
        "project_id": "proj_001",
        "offer_amount_inr": 50000.0,
        "proposal_type": "Commercial IP Acquisition"
    })
    assert res_post.status_code == 401

    # Update
    res_put = client.put("/api/industrial/offers/off_001", json={
        "status": "Accepted"
    })
    assert res_put.status_code == 401


# ==========================================
# 2. ROLE AUTHORIZATION & FINANCIAL BOUNDS (POST)
# ==========================================

def test_non_industry_roles_cannot_submit_offers_returns_403():
    """Students, Faculty, and SPOCs cannot submit industrial offers."""
    token_student = create_authenticated_user_session("student_test@iitb.ac.in", "student", "Student", "usr_student_test")
    res = client.post("/api/industrial/offers", json={
        "project_id": "proj_001",
        "offer_amount_inr": 250000.0,
        "proposal_type": "Commercial IP Acquisition"
    }, headers={"Authorization": f"Bearer {token_student}"})
    assert res.status_code == 403


def test_offer_amount_minimum_validation():
    """Offer amount must be >= 1,000 INR; smaller or negative amounts are rejected."""
    token_ind = create_authenticated_user_session("vikram@tataelxsi.co.in", "industrialist", "Tata Elxsi", "usr_industrialist_1")
    headers = {"Authorization": f"Bearer {token_ind}"}

    # Negative amount
    res_neg = client.post("/api/industrial/offers", json={
        "project_id": "proj_001",
        "offer_amount_inr": -500.0,
        "proposal_type": "Grant"
    }, headers=headers)
    assert res_neg.status_code == 422

    # Under 1,000 INR
    res_low = client.post("/api/industrial/offers", json={
        "project_id": "proj_001",
        "offer_amount_inr": 500.0,
        "proposal_type": "Grant"
    }, headers=headers)
    assert res_low.status_code == 422


def test_industry_partner_submits_offer_with_server_derived_identity():
    """Industry partner submits valid offer; buyer metadata is derived from verified session."""
    token_ind = create_authenticated_user_session("vikram@tataelxsi.co.in", "industrialist", "Vikramaditya Singhania", "usr_industrialist_1")
    headers = {"Authorization": f"Bearer {token_ind}"}

    res = client.post("/api/industrial/offers", json={
        "project_id": "proj_001",
        "offer_amount_inr": 500000.0,
        "proposal_type": "Commercial IP Acquisition",
        "deliverables_message": "Full schematics and CAD assets.",
        # Forged client-side IDs
        "buyer_id": "usr_forged_victim",
        "buyer_name": "Forged Company"
    }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["buyer_id"] == "usr_industrialist_1"
    assert data["buyer_name"] == "Vikramaditya Singhania"
    assert data["status"] == "Pending"
    assert data["spoc_approval"] == "Pending"
    assert data["offer_amount_inr"] == 500000.0


# ==========================================
# 3. MULTI-TENANT VISIBILITY SCOPING (GET)
# ==========================================

def test_multi_tenant_visibility_scoping():
    """
    Validates that:
    - Student only sees offers on their projects.
    - Buyer only sees offers they submitted.
    - SPOC only sees offers from their institution.
    - Admin sees all.
    """
    token_student_1 = create_authenticated_user_session("aarav@cse.iitb.ac.in", "student", "Aarav Patel", "usr_student_1")
    token_student_other = create_authenticated_user_session("other_student@iitd.ac.in", "student", "Other Student", "usr_student_other")
    token_buyer = create_authenticated_user_session("vikram@tataelxsi.co.in", "industrialist", "Vikram", "usr_industrialist_1")
    token_spoc_iitb = create_authenticated_user_session("spoc.iitb@iitb.ac.in", "spoc", "Prof IITB", "usr_spoc_iitb", college="Indian Institute of Technology (IIT) Bombay")
    token_admin = create_authenticated_user_session("admin@proved.gov.in", "admin", "Admin", "usr_admin_1")

    # 1. Student 1 (owner of proj_001) queries offers -> Sees off_001
    res_s1 = client.get("/api/industrial/offers", headers={"Authorization": f"Bearer {token_student_1}"})
    assert res_s1.status_code == 200
    offers_s1 = res_s1.json()
    assert any(o["project_id"] == "proj_001" for o in offers_s1)

    # 2. Other student (owns no projects with offers) queries offers -> Empty
    res_other = client.get("/api/industrial/offers", headers={"Authorization": f"Bearer {token_student_other}"})
    assert res_other.status_code == 200
    assert len(res_other.json()) == 0

    # 3. Buyer queries offers -> Sees their own submitted offers
    res_buyer = client.get("/api/industrial/offers", headers={"Authorization": f"Bearer {token_buyer}"})
    assert res_buyer.status_code == 200
    assert all(o["buyer_id"] == "usr_industrialist_1" for o in res_buyer.json())

    # 4. SPOC from IIT Bombay queries offers -> Sees offers for IIT Bombay projects
    res_spoc = client.get("/api/industrial/offers", headers={"Authorization": f"Bearer {token_spoc_iitb}"})
    assert res_spoc.status_code == 200
    assert len(res_spoc.json()) > 0

    # 5. Admin queries offers -> Sees all offers
    res_admin = client.get("/api/industrial/offers", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin.status_code == 200
    assert len(res_admin.json()) >= len(offers_s1)


# ==========================================
# 4. NEGOTIATION, COUNTER & ACCEPT (PUT)
# ==========================================

def test_student_lead_can_counter_and_buyer_accept():
    """Student Lead counters the offer, and Buyer accepts the counter-offer."""
    token_lead = create_authenticated_user_session("aarav@cse.iitb.ac.in", "student", "Aarav Patel", "usr_student_1")
    token_buyer = create_authenticated_user_session("vikram@tataelxsi.co.in", "industrialist", "Vikram", "usr_industrialist_1")

    # Reset off_001 to Pending
    with get_db_session() as s:
        off = s.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == "off_001").first()
        off.status = "Pending"
        off.counter_amount_inr = 0.0
        off.spoc_approval = "Pending"

    # 1. Lead counters with ₹450,000 INR
    res_counter = client.put("/api/industrial/offers/off_001", json={
        "status": "Countered",
        "counter_amount_inr": 450000.0
    }, headers={"Authorization": f"Bearer {token_lead}"})

    assert res_counter.status_code == 200
    data_counter = res_counter.json()
    assert data_counter["status"] == "Countered"
    assert data_counter["counter_amount_inr"] == 450000.0

    # 2. Buyer accepts the counter-offer
    res_accept = client.put("/api/industrial/offers/off_001", json={
        "status": "Accepted"
    }, headers={"Authorization": f"Bearer {token_buyer}"})

    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "Accepted"
    # SPOC approval remains Pending
    assert res_accept.json()["spoc_approval"] == "Pending"


def test_buyer_can_withdraw_pending_offer():
    """Buyer can withdraw their pending offer."""
    token_buyer = create_authenticated_user_session("vikram@tataelxsi.co.in", "industrialist", "Vikram", "usr_industrialist_1")

    # Reset off_001 to Pending
    with get_db_session() as s:
        off = s.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == "off_001").first()
        off.status = "Pending"

    res = client.put("/api/industrial/offers/off_001", json={
        "status": "Withdrawn"
    }, headers={"Authorization": f"Bearer {token_buyer}"})

    assert res.status_code == 200
    assert res.json()["status"] == "Withdrawn"

    # Verify terminal state: cannot counter or accept a Withdrawn offer
    res_attempt = client.put("/api/industrial/offers/off_001", json={
        "status": "Accepted"
    }, headers={"Authorization": f"Bearer {token_buyer}"})
    assert res_attempt.status_code == 400


# ==========================================
# 5. POST-AGREEMENT SPOC APPROVAL WORKFLOW
# ==========================================

def test_spoc_approval_rejected_before_status_accepted_returns_400():
    """SPOC cannot approve or deny an offer while it is still Pending or Countered."""
    token_spoc = create_authenticated_user_session(
        "spoc.iitb@iitb.ac.in", "spoc", "Prof. R&D", "usr_spoc_iitb",
        college="Indian Institute of Technology (IIT) Bombay"
    )

    # Set off_001 to Pending
    with get_db_session() as s:
        off = s.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == "off_001").first()
        off.status = "Pending"
        off.spoc_approval = "Pending"

    res = client.put("/api/industrial/offers/off_001", json={
        "spoc_approval": "Approved"
    }, headers={"Authorization": f"Bearer {token_spoc}"})

    assert res.status_code == 400
    assert "mutual commercial agreement" in res.json()["detail"].lower()


def test_spoc_approval_succeeds_after_status_accepted_returns_200():
    """SPOC from the project's college successfully approves an Accepted offer."""
    token_spoc = create_authenticated_user_session(
        "spoc.iitb@iitb.ac.in", "spoc", "Prof. R&D", "usr_spoc_iitb",
        college="Indian Institute of Technology (IIT) Bombay"
    )

    # Set off_001 to Accepted
    with get_db_session() as s:
        off = s.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == "off_001").first()
        off.status = "Accepted"
        off.spoc_approval = "Pending"

    res = client.put("/api/industrial/offers/off_001", json={
        "spoc_approval": "Approved"
    }, headers={"Authorization": f"Bearer {token_spoc}"})

    assert res.status_code == 200
    assert res.json()["status"] == "Accepted"
    assert res.json()["spoc_approval"] == "Approved"


def test_wrong_college_spoc_cannot_approve_offer_returns_404():
    """SPOC from another college cannot approve an offer on an IIT Bombay project."""
    token_wrong_spoc = create_authenticated_user_session(
        "spoc.coep@coep.ac.in", "spoc", "Prof. COEP", "usr_spoc_coep",
        college="COEP Technological University"
    )

    res = client.put("/api/industrial/offers/off_001", json={
        "spoc_approval": "Approved"
    }, headers={"Authorization": f"Bearer {token_wrong_spoc}"})

    assert res.status_code == 404
    assert res.json()["detail"] == "Industrial offer not found"


# ==========================================
# 6. DATABASE INVARIANCE UNDER ATTACK
# ==========================================

def test_database_state_unchanged_on_unauthorized_mutation_attempts():
    """Verifies that unauthorized requests leave PostgreSQL records completely unchanged."""
    with get_db_session() as s:
        off = s.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == "off_001").first()
        initial_status = off.status
        initial_amount = off.offer_amount_inr
        initial_counter = off.counter_amount_inr
        initial_approval = off.spoc_approval

    token_unauth = create_authenticated_user_session("unauthorized@other.ac.in", "student", "Random Student", "usr_random_student_1")

    # Attacker tries to accept the offer
    r = client.put("/api/industrial/offers/off_001", json={"status": "Accepted"}, headers={"Authorization": f"Bearer {token_unauth}"})
    assert r.status_code == 404

    # Attacker tries to approve the offer
    r2 = client.put("/api/industrial/offers/off_001", json={"spoc_approval": "Approved"}, headers={"Authorization": f"Bearer {token_unauth}"})
    assert r2.status_code == 404

    # Verify database record was NOT modified
    with get_db_session() as s:
        off_after = s.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == "off_001").first()
        assert off_after.status == initial_status
        assert off_after.offer_amount_inr == initial_amount
        assert off_after.counter_amount_inr == initial_counter
        assert off_after.spoc_approval == initial_approval
