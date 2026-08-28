"""
Unit and regression tests for Database Connection and Transaction Lifecycle (P0-01).
Tests SQLAlchemy 2.0 Session lifecycle, transaction rollback on error,
foreign key violation handling (HTTP 400), and verified immunity against locked states.
"""

import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Ensure project backend is on sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pv_backend_dir = os.path.join(root_dir, "Pro-Versed", "backend")
pv_dir = os.path.join(root_dir, "Pro-Versed")
for p in [pv_backend_dir, pv_dir, root_dir]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from main import app
from database import get_db_session, get_db, SessionLocal, engine, init_db
from models import ProjectORM, TaskORM, UserORM

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_lifecycle_db():
    init_db()


def test_invalid_foreign_key_returns_controlled_400():
    """
    Negative test: Attempting to insert a task with a non-existent project_id
    must trigger FOREIGN KEY enforcement, returning clean HTTP 400 (NOT HTTP 500 or raw traceback).
    """
    bad_project_id = f"nonexistent_proj_{uuid.uuid4().hex[:8]}"
    response = client.post("/api/tasks", json={
        "project_id": bad_project_id,
        "title": "Task with invalid project FK",
        "description": "Should fail foreign key constraint",
        "column": "backlog",
        "priority": "High",
        "assignee_name": "QA Tester"
    })
    assert response.status_code == 400
    data = response.json()
    assert "foreign key" in data.get("detail", "").lower() or "constraint" in data.get("detail", "").lower()


def test_no_database_lock_after_exception():
    """
    Regression test for P0-01:
    After a failed write (foreign key failure), verify that the session
    was rolled back and closed, and subsequent write operations succeed immediately
    without hanging or throwing database-locked errors.
    """
    # 1. Trigger foreign key failure
    bad_resp = client.post("/api/tasks", json={
        "project_id": "bad_id_12345",
        "title": "Failing task",
        "column": "backlog",
        "priority": "Low"
    })
    assert bad_resp.status_code == 400

    # 2. Get valid project ID
    with get_db_session() as session:
        proj = session.query(ProjectORM).first()
        valid_proj_id = proj.id if proj else "proj_001"

    # 3. Immediately execute valid task creation write
    success_resp = client.post("/api/tasks", json={
        "project_id": valid_proj_id,
        "title": "Post-Exception Success Task",
        "description": "Proves DB connection/session was released and is not locked",
        "column": "in_progress",
        "priority": "Medium",
        "assignee_name": "QA Innovator"
    })
    assert success_resp.status_code == 200
    created_task = success_resp.json()
    assert created_task["title"] == "Post-Exception Success Task"

    # Clean up test task
    del_resp = client.delete(f"/api/tasks/{created_task['id']}")
    assert del_resp.status_code == 200


def test_sqlalchemy_session_lifecycle_cleanup_on_exception():
    """
    Direct unit test for get_db_session:
    Ensures that when an exception is raised inside the context block,
    session.rollback() and session.close() are called.
    """
    saved_session = None
    with pytest.raises(RuntimeError, match="Simulated transaction failure"):
        with get_db_session() as session:
            saved_session = session
            # Perform a temporary uncommitted change
            dummy_user = UserORM(
                id=f"test_temp_{uuid.uuid4().hex[:6]}",
                name="Temp User",
                email=f"temp_{uuid.uuid4().hex[:6]}@test.com",
                role="student",
                created_at="2026-01-01T00:00:00"
            )
            session.add(dummy_user)
            raise RuntimeError("Simulated transaction failure")

    assert saved_session is not None
    # Verify that the session is closed / inactive
    assert not saved_session.is_active or saved_session.get_transaction() is None


def test_sqlalchemy_session_lifecycle_commit_on_success():
    """
    Direct unit test for get_db_session:
    Ensures that on normal context exit, changes are committed and session is closed.
    """
    test_id = f"test_user_{uuid.uuid4().hex[:8]}"
    test_email = f"user_{uuid.uuid4().hex[:8]}@iitb.ac.in"

    with get_db_session() as session:
        user = UserORM(
            id=test_id,
            name="Lifecycle Test User",
            email=test_email,
            role="student",
            created_at="2026-01-01T00:00:00"
        )
        session.add(user)

    # Verify persisted in a new separate session
    with get_db_session() as session:
        queried = session.query(UserORM).filter(UserORM.id == test_id).first()
        assert queried is not None
        assert queried.email == test_email
        # Clean up
        session.delete(queried)
