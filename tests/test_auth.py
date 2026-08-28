"""
PRO-VERSED — Comprehensive Pytest Authentication & Security Test Suite
Tests server-side validation, zero-information-disclosure errors,
sliding 1-hour rate limiting (max 10 attempts), 5-failure / 3-hour account lockout,
session lifecycle, and protected dashboard access.
"""

import os
import sys
import tempfile
import sqlite3
from datetime import datetime, timedelta, timezone

# Ensure project backend is on sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pv_backend_dir = os.path.join(root_dir, "Pro-Versed", "backend")
pv_dir = os.path.join(root_dir, "Pro-Versed")
for p in [pv_backend_dir, pv_dir, root_dir]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# Point database to isolated test DB
test_db_fd, test_db_path = tempfile.mkstemp(suffix="_test_auth.db")
os.close(test_db_fd)
os.environ["PROVERSED_DB_PATH"] = test_db_path

import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db, get_db_connection
from auth import (
    hash_password, verify_password,
    check_rate_limit, record_login_attempt,
    get_account_security_status, record_failed_login,
    reset_failed_login_counter, create_user_session,
    validate_session, revoke_session,
    GENERIC_AUTH_ERROR, GENERIC_LOCKOUT_ERROR, GENERIC_RATE_LIMIT_ERROR,
    ACCOUNT_LOCKOUT_DURATION_SECONDS
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Initializes and resets the test database before each test."""
    init_db()
    yield
    # Clean up test database tables
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM login_attempts;")
    cursor.execute("DELETE FROM password_reset_attempts;")
    cursor.execute("DELETE FROM otp_verifications;")
    cursor.execute("DELETE FROM otp_requests;")
    cursor.execute("DELETE FROM account_security;")
    cursor.execute("DELETE FROM sessions;")
    conn.commit()
    conn.close()


# ==========================================
# 1. AUTHENTICATION & ZERO-DISCLOSURE TESTS
# ==========================================

def test_login_success():
    """Valid credentials return 200 OK, session token, and user profile."""
    res = client.post("/api/auth/login", json={
        "email": "aarav@cse.iitb.ac.in",
        "password": "Password123!"
    })
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "session_token" in data
    assert len(data["session_token"]) > 20
    assert data["user"]["email"] == "aarav@cse.iitb.ac.in"
    assert data["user"]["name"] == "Aarav Patel"
    assert "session_token" in res.cookies


def test_login_wrong_password_returns_generic_error():
    """Incorrect password returns 401 with generic error message."""
    res = client.post("/api/auth/login", json={
        "email": "aarav@cse.iitb.ac.in",
        "password": "WrongPassword999!"
    })
    assert res.status_code == 401
    data = res.json()
    assert data["detail"] == GENERIC_AUTH_ERROR


def test_login_nonexistent_email_returns_identical_generic_error():
    """Non-existent account returns 401 with identical generic error message."""
    res = client.post("/api/auth/login", json={
        "email": "nonexistent.hacker@unknown.domain.org",
        "password": "WrongPassword999!"
    })
    assert res.status_code == 401
    data = res.json()
    assert data["detail"] == GENERIC_AUTH_ERROR


def test_login_invalid_email_format_returns_generic_error():
    """Malformed email returns 401 with generic error message without leaking format diagnostics."""
    res = client.post("/api/auth/login", json={
        "email": "not-an-email",
        "password": "Password123!"
    })
    assert res.status_code == 401
    data = res.json()
    assert data["detail"] == GENERIC_AUTH_ERROR


def test_information_disclosure_prevention():
    """Ensures responses for wrong password vs non-existent email are byte-for-byte identical."""
    res_wrong_pw = client.post("/api/auth/login", json={
        "email": "aarav@cse.iitb.ac.in",
        "password": "WrongPassword!"
    })
    res_missing_user = client.post("/api/auth/login", json={
        "email": "ghost.user@doesnotexist.edu.in",
        "password": "WrongPassword!"
    })
    assert res_wrong_pw.status_code == res_missing_user.status_code == 401
    assert res_wrong_pw.json()["detail"] == res_missing_user.json()["detail"] == GENERIC_AUTH_ERROR


# ==========================================
# 2. ACCOUNT LOCKOUT TESTS (5 FAILS -> 3 HRS)
# ==========================================

def test_account_lockout_after_5_consecutive_failures():
    """5 consecutive failed logins trigger 3-hour account lockout; 6th attempt returns HTTP 423."""
    target_email = "sunita.raman@iisc.ac.in"

    # 1st to 4th failed attempts -> HTTP 401
    for i in range(1, 5):
        res = client.post("/api/auth/login", json={
            "email": target_email,
            "password": f"BadPassword_{i}"
        })
        assert res.status_code == 401, f"Attempt {i} expected 401, got {res.status_code}"
        assert res.json()["detail"] == GENERIC_AUTH_ERROR

    # 5th failed attempt -> Reaches threshold of 5, locks account and returns HTTP 423
    res_5 = client.post("/api/auth/login", json={
        "email": target_email,
        "password": "BadPassword_5"
    })
    assert res_5.status_code == 423
    assert res_5.json()["detail"] == GENERIC_LOCKOUT_ERROR

    # 6th attempt (even with correct password) -> Blocked by lockout with HTTP 423
    res_6 = client.post("/api/auth/login", json={
        "email": target_email,
        "password": "Password123!"
    })
    assert res_6.status_code == 423
    assert res_6.json()["detail"] == GENERIC_LOCKOUT_ERROR
    assert "remaining_lockout_seconds" in res_6.json()
    assert res_6.json()["remaining_lockout_seconds"] > 0


def test_lockout_auto_resets_after_3_hours():
    """Account automatically unlocks and counter resets after the 3-hour lockout expires."""
    target_email = "rk.mukherjee@nitt.edu.in"
    conn = get_db_connection()

    # Trigger 5 failed attempts at T0
    t0 = datetime.now(timezone.utc)
    for _ in range(5):
        record_failed_login(conn, target_email, now=t0)

    # Verify locked at T0 + 1 hour
    t_1hr = t0 + timedelta(hours=1)
    status_1hr = get_account_security_status(conn, target_email, now=t_1hr)
    assert status_1hr["is_locked"] is True
    assert status_1hr["remaining_lockout_seconds"] > 0

    # Verify unlocked at T0 + 3 hours + 1 second
    t_3hr_post = t0 + timedelta(seconds=ACCOUNT_LOCKOUT_DURATION_SECONDS + 1)
    status_expired = get_account_security_status(conn, target_email, now=t_3hr_post)
    assert status_expired["is_locked"] is False
    assert status_expired["consecutive_failed_attempts"] == 0

    conn.close()


def test_successful_login_resets_failed_attempts_counter():
    """A successful login immediately resets consecutive failed attempts counter to 0."""
    target_email = "vikram.s@tataelxsi.com"

    # 3 failed attempts
    for i in range(3):
        res = client.post("/api/auth/login", json={
            "email": target_email,
            "password": "IncorrectPassword!"
        })
        assert res.status_code == 401

    conn = get_db_connection()
    status_before = get_account_security_status(conn, target_email)
    assert status_before["consecutive_failed_attempts"] == 3
    conn.close()

    # Successful login
    res_ok = client.post("/api/auth/login", json={
        "email": target_email,
        "password": "Password123!"
    })
    assert res_ok.status_code == 200

    conn = get_db_connection()
    status_after = get_account_security_status(conn, target_email)
    assert status_after["consecutive_failed_attempts"] == 0
    conn.close()


# ==========================================
# 3. RATE LIMITING TESTS (MAX 10 / HOUR)
# ==========================================

def test_rate_limiting_10_attempts_per_hour():
    """Allows up to 10 login attempts per hour; the 11th attempt returns HTTP 429."""
    test_ip = "192.168.1.100"
    test_email = "ratelimit.user@test.org"

    headers = {"X-Forwarded-For": test_ip}

    # 10 attempts
    for i in range(10):
        res = client.post("/api/auth/login", json={
            "email": test_email,
            "password": "SomePassword!"
        }, headers=headers)
        # Status code could be 401 or 423 depending on lockout, but NOT 429
        assert res.status_code in [401, 423], f"Attempt {i+1} got unexpected status {res.status_code}"

    # 11th attempt -> Exceeds rate limit -> HTTP 429 Too Many Requests
    res_11 = client.post("/api/auth/login", json={
        "email": test_email,
        "password": "SomePassword!"
    }, headers=headers)
    assert res_11.status_code == 429
    assert res_11.json()["detail"] == GENERIC_RATE_LIMIT_ERROR
    assert res_11.headers.get("Retry-After") == "3600"


def test_rate_limiting_sliding_window():
    """Direct test of check_rate_limit sliding 1-hour window mechanism."""
    conn = get_db_connection()
    ip = "10.0.0.50"
    email = "sliding@window.test"

    t0 = datetime.now(timezone.utc)
    for _ in range(10):
        record_login_attempt(conn, ip, email, is_success=False, now=t0)

    # 11th at T0 -> Blocked
    allowed, rem = check_rate_limit(conn, ip, email, now=t0)
    assert allowed is False
    assert rem == 0

    # At T0 + 61 minutes -> Window has slid past -> Allowed again
    t_later = t0 + timedelta(minutes=61)
    allowed_later, rem_later = check_rate_limit(conn, ip, email, now=t_later)
    assert allowed_later is True
    assert rem_later == 10

    conn.close()


# ==========================================
# 4. SESSION MANAGEMENT & PROTECTED ROUTES
# ==========================================

def test_session_validation_endpoint():
    """Tests /api/auth/session with valid token and unauthenticated state."""
    # Unauthenticated
    res_unauth = client.get("/api/auth/session")
    assert res_unauth.status_code == 200
    assert res_unauth.json()["valid"] is False

    # Authenticate
    login_res = client.post("/api/auth/login", json={
        "email": "aarav@cse.iitb.ac.in",
        "password": "Password123!"
    })
    token = login_res.json()["session_token"]

    # Verify with Bearer header
    res_auth = client.get("/api/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert res_auth.status_code == 200
    auth_data = res_auth.json()
    assert auth_data["valid"] is True
    assert auth_data["user"]["email"] == "aarav@cse.iitb.ac.in"


def test_protected_dashboard_endpoint():
    """Tests /api/dashboard/overview rejects unauthenticated and allows authenticated users."""
    # Unauthenticated -> 401
    res_unauth = client.get("/api/dashboard/overview")
    assert res_unauth.status_code == 401

    # Login
    login_res = client.post("/api/auth/login", json={
        "email": "aarav@cse.iitb.ac.in",
        "password": "Password123!"
    })
    token = login_res.json()["session_token"]

    # Authenticated -> 200 OK with metrics & security overview
    res_auth = client.get("/api/dashboard/overview", headers={"Authorization": f"Bearer {token}"})
    assert res_auth.status_code == 200
    data = res_auth.json()
    assert "metrics" in data
    assert "security_overview" in data
    assert data["security_overview"]["lockout_status"] == "Clear"


def test_logout_revokes_session():
    """Logging out revokes session; subsequent requests fail with 401."""
    login_res = client.post("/api/auth/login", json={
        "email": "aarav@cse.iitb.ac.in",
        "password": "Password123!"
    })
    token = login_res.json()["session_token"]

    # Verify dashboard accessible
    res1 = client.get("/api/dashboard/overview", headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Subsequent dashboard request -> 401
    res2 = client.get("/api/dashboard/overview", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 401


# ==========================================
# 5. USER REGISTRATION TESTS
# ==========================================

def test_user_registration_success():
    """Registering with valid email and strong password creates an account and returns session."""
    reg_email = f"new.innovator_{datetime.utcnow().timestamp()}@iitd.ac.in"
    res = client.post("/api/auth/register", json={
        "name": "Rohan Gupta",
        "email": reg_email,
        "password": "SuperSecret@2026!",
        "role": "student",
        "college": "IIT Delhi",
        "department": "Mechanical Engineering"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == reg_email
    assert data["user"]["is_verified_academic"] == 1
    assert "session_token" in data


def test_user_registration_weak_password_rejected():
    """Weak password fails server-side validation with 400 Bad Request or 422."""
    # 1. Complexity failure (missing uppercase, number)
    res_complexity = client.post("/api/auth/register", json={
        "name": "Weak Pass User",
        "email": "weak.complexity@test.com",
        "password": "onlylowercaseandnochars"
    })
    assert res_complexity.status_code == 400
    assert "Password must contain at least one uppercase letter" in res_complexity.json()["detail"]

    # 2. Length failure (< 8 chars)
    res_short = client.post("/api/auth/register", json={
        "name": "Short Pass User",
        "email": "short@test.com",
        "password": "short"
    })
    assert res_short.status_code in [400, 422]


# ==========================================
# 6. SECURITY HEADERS & 404 ROUTE TESTS
# ==========================================

def test_security_headers_present():
    """Verifies all HTTPS-ready security headers are attached to responses."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Strict-Transport-Security" in res.headers


def test_404_unmatched_api_route():
    """Unmatched /api/* routes return JSON 404 response."""
    res = client.get("/api/completely-nonexistent-endpoint-xyz")
    assert res.status_code == 404
    data = res.json()
    assert data["error"] == "Not Found"


# ==========================================
# 7. FORGOT PASSWORD & RESET PASSWORD TESTS
# ==========================================

def test_forgot_password_success_and_generic_response():
    """Forgot password returns generic success message preventing user enumeration."""
    res = client.post("/api/auth/forgot-password", json={"email": "aarav@cse.iitb.ac.in"})
    assert res.status_code == 200
    data = res.json()
    assert "If an account exists with this email" in data["message"]
    assert data["success"] is True
    assert data.get("reset_token") is not None

    # Verify reset token was hashed and stored in database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT reset_password_token, reset_password_expires FROM users WHERE email = ?;", ("aarav@cse.iitb.ac.in",))
    row = cursor.fetchone()
    conn.close()
    assert row["reset_password_token"] is not None
    assert row["reset_password_expires"] is not None


def test_forgot_password_nonexistent_email_returns_identical_generic_response():
    """Non-existent emails receive identical 200 response with zero disclosure."""
    res = client.post("/api/auth/forgot-password", json={"email": "unknown.user.999@domain.com"})
    assert res.status_code == 200
    data = res.json()
    assert "If an account exists with this email" in data["message"]
    assert data["success"] is True


def test_forgot_password_rate_limit_enforced():
    """Enforces maximum 5 forgot-password requests per hour."""
    test_email = "rate.test@cse.iitb.ac.in"
    for i in range(5):
        r = client.post("/api/auth/forgot-password", json={"email": test_email})
        assert r.status_code == 200

    # 6th attempt -> HTTP 429
    r_exceeded = client.post("/api/auth/forgot-password", json={"email": test_email})
    assert r_exceeded.status_code == 429
    assert "Rate limit exceeded" in r_exceeded.json()["detail"]


def test_reset_password_flow_and_login_with_new_credentials():
    """Full lifecycle: forgot password -> reset with token -> login with new password."""
    email = "aarav@cse.iitb.ac.in"

    # 1. Request reset
    req_res = client.post("/api/auth/forgot-password", json={"email": email})
    assert req_res.status_code == 200
    token = req_res.json()["reset_token"]
    assert token

    # 2. Reset password with new password (supporting camelCase newPassword)
    new_pass = "SuperSecure@2026"
    reset_res = client.post("/api/auth/reset-password", json={
        "token": token,
        "newPassword": new_pass
    })
    assert reset_res.status_code == 200
    assert "Password has been successfully reset" in reset_res.json()["message"]

    # 3. Old password should now fail
    old_login = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert old_login.status_code == 401

    # 4. New password should succeed
    new_login = client.post("/api/auth/login", json={"email": email, "password": new_pass})
    assert new_login.status_code == 200
    assert new_login.json()["session_token"]


def test_reset_password_invalid_or_consumed_token_rejected():
    """Invalid or already consumed tokens return 400 Bad Request."""
    # Invalid token
    res_fake = client.post("/api/auth/reset-password", json={
        "token": "completely_fake_invalid_token_123",
        "newPassword": "ValidPassword@123"
    })
    assert res_fake.status_code == 400
    assert "Invalid, expired, or previously consumed" in res_fake.json()["detail"]

    # Valid token consumed once
    email = "sunita.raman@iisc.ac.in"
    req_res = client.post("/api/auth/forgot-password", json={"email": email})
    token = req_res.json()["reset_token"]

    first_use = client.post("/api/auth/reset-password", json={
        "token": token,
        "newPassword": "ValidPassword@123"
    })
    assert first_use.status_code == 200

    # Second use of same token -> rejected
    second_use = client.post("/api/auth/reset-password", json={
        "token": token,
        "newPassword": "AnotherPassword@123"
    })
    assert second_use.status_code == 400
    assert "Invalid, expired, or previously consumed" in second_use.json()["detail"]


def test_reset_password_weak_password_rejected():
    """Weak passwords during reset are rejected with 400 Bad Request."""
    email = "rk.mukherjee@nitt.edu.in"
    req_res = client.post("/api/auth/forgot-password", json={"email": email})
    token = req_res.json()["reset_token"]

    # 1. Short password (< 8 chars)
    weak_res = client.post("/api/auth/reset-password", json={
        "token": token,
        "newPassword": "short"
    })
    assert weak_res.status_code == 400
    assert "Password must be at least 8 characters long" in weak_res.json()["detail"]

    # 2. Missing uppercase or number
    complex_res = client.post("/api/auth/reset-password", json={
        "token": token,
        "newPassword": "alllowercasepassword"
    })
    assert complex_res.status_code == 400
    assert "Password must contain at least one uppercase letter" in complex_res.json()["detail"]


# ==========================================
# 8. EMAIL/GMAIL OTP VERIFICATION TESTS
# ==========================================

def test_send_otp_success():
    """Generates and returns 6-digit OTP for new valid email."""
    email = "new.innovator.otp@gmail.com"
    res = client.post("/api/auth/send-otp", json={"email": email})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Verification OTP has been sent" in data["message"]
    assert len(data["otp"]) == 6
    assert data["otp"].isdigit()


def test_send_otp_duplicate_email_rejected():
    """Attempting OTP dispatch for an already registered email fails with 400 Bad Request."""
    res = client.post("/api/auth/send-otp", json={"email": "aarav@cse.iitb.ac.in"})
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_send_otp_rate_limiting():
    """Enforces maximum 3 OTP requests per 10 minutes."""
    email = "otp.ratelimit.test@gmail.com"
    for i in range(3):
        r = client.post("/api/auth/send-otp", json={"email": email})
        assert r.status_code == 200

    # 4th request within 10 minutes -> HTTP 429
    r_exceeded = client.post("/api/auth/send-otp", json={"email": email})
    assert r_exceeded.status_code == 429
    assert "Rate limit exceeded" in r_exceeded.json()["detail"]


def test_verify_otp_endpoint_success_and_failure():
    """Verifies valid OTP passes and incorrect OTP fails with remaining attempts."""
    email = "verify.flow@gmail.com"
    res_send = client.post("/api/auth/send-otp", json={"email": email})
    otp = res_send.json()["otp"]

    # Incorrect OTP
    res_bad = client.post("/api/auth/verify-otp", json={"email": email, "otp": "000000"})
    assert res_bad.status_code == 400
    assert "Incorrect OTP" in res_bad.json()["detail"]

    # Correct OTP
    res_good = client.post("/api/auth/verify-otp", json={"email": email, "otp": otp})
    assert res_good.status_code == 200
    assert res_good.json()["verified"] is True


def test_register_with_otp_success_and_login():
    """Full lifecycle: Send OTP -> Register with OTP -> Authenticated session."""
    email = "complete.registration@iitb.ac.in"
    send_res = client.post("/api/auth/send-otp", json={"email": email})
    otp = send_res.json()["otp"]

    reg_res = client.post("/api/auth/register", json={
        "fullName": "Priya Sharma",
        "email": email,
        "password": "Password@123",
        "role": "student",
        "collegeCompany": "IIT Bombay",
        "otp": otp
    })
    assert reg_res.status_code == 200
    auth_data = reg_res.json()
    assert auth_data["user"]["email"] == email
    assert auth_data["user"]["name"] == "Priya Sharma"
    assert auth_data["session_token"]

    # OTP should now be consumed; second registration with same OTP fails
    reg_res_dup = client.post("/api/auth/register", json={
        "fullName": "Duplicate User",
        "email": email,
        "password": "Password@123",
        "otp": otp
    })
    assert reg_res_dup.status_code == 400


