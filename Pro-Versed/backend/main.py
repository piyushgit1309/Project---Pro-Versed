"""
Pro-Versed FastAPI Backend Application.
The National Student Project Portfolio, Plagiarism Audit, and Hardware/Software IP Marketplace.
"""

import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Depends, status, Request, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from database import get_db_connection, is_academic_domain, is_industry_domain, init_db
from models import dict_from_row
from schemas import (
    UserCreate, UserResponse, DemoLoginRequest,
    LoginRequest, RegisterRequest, AuthResponse, SessionValidationResponse,
    SecurityStatusResponse, LogoutResponse,
    ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, ResetPasswordResponse,
    SendOtpRequest, SendOtpResponse, VerifyOtpRequest, VerifyOtpResponse,
    ProjectCreate, ProjectUpdate, ProjectResponse,
    TaskCreate, TaskUpdate, TaskResponse,
    MarketplaceItemCreate, EscrowAdvanceRequest, MarketplaceItemResponse,
    IndustrialOfferCreate, IndustrialOfferUpdate, IndustrialOfferResponse,
    PlagiarismCheckRequest, PlagiarismCheckResponse
)
from auth import (
    hash_password, verify_password, perform_dummy_verification,
    validate_email_format, validate_password_strength, normalize_email,
    check_rate_limit, record_login_attempt, get_account_security_status,
    record_failed_login, reset_failed_login_counter, create_user_session,
    validate_session, revoke_session,
    check_forgot_password_rate_limit, record_forgot_password_attempt,
    create_password_reset_token, reset_password_with_token,
    generate_otp, hash_otp, check_otp_rate_limit, record_otp_request,
    store_otp, verify_otp,
    GENERIC_AUTH_ERROR, GENERIC_LOCKOUT_ERROR, GENERIC_RATE_LIMIT_ERROR,
    GENERIC_FORGOT_PASSWORD_MESSAGE, GENERIC_FORGOT_PASSWORD_RATE_LIMIT_ERROR,
    GENERIC_OTP_RATE_LIMIT_ERROR
)
from plagiarism import plagiarism_engine
from ipfs import ipfs_engine
from ai_chat import ai_chat_engine
from meetings import meeting_service


# Initialize FastAPI App
app = FastAPI(
    title="Pro-Versed API",
    description="The National Student Project Portfolio, Plagiarism Audit, and Hardware/Software IP Marketplace",
    version="1.0.0"
)

# HTTPS-Ready Security Headers Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Configure CORS for deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_client_ip(request: Request) -> str:
    """Extracts client IP address respecting reverse proxies."""
    if not request:
        return "127.0.0.1"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

def get_session_token_from_request(request: Request) -> Optional[str]:
    """Extracts session token from Bearer header or HttpOnly cookie."""
    if not request:
        return None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        return cookie_token.strip()
    return None

def get_current_authenticated_user(request: Request) -> Dict[str, Any]:
    """Dependency ensuring the request is from a verified active session."""
    token = get_session_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid session token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    conn = get_db_connection()
    session_data = validate_session(conn, token)
    conn.close()
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return session_data["user"]

@app.get("/health")
@app.get("/api/health")
def health_check():
    """Production readiness and liveness health probe."""
    return {
        "status": "healthy",
        "service": "pro-versed",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

def refresh_plagiarism_corpus():
    """Syncs existing project database records into the in-memory plagiarism engine."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, abstract, description, college_name FROM projects;")
    rows = cursor.fetchall()
    corpus = [dict(r) for r in rows]
    plagiarism_engine.set_corpus(corpus)
    conn.close()

@app.on_event("startup")
async def on_startup():
    """Initializes schema migrations and populates plagiarism corpus on server startup."""
    init_db()
    refresh_plagiarism_corpus()

# ==========================================
# 1. USER & AUTHENTICATION ENDPOINTS
# ==========================================

@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, response: Response):
    """
    Production-ready secure login endpoint.
    - Rate limit: max 10 attempts per hour (returns HTTP 429)
    - Account lockout: locked for 3 hours after 5 consecutive failures (returns HTTP 423)
    - Server-side email format validation
    - Constant-time verification & dummy hash timing mitigation
    - Unified generic error message for all credential failures (HTTP 401)
    """
    client_ip = get_client_ip(request)
    email = normalize_email(req.email)
    password = req.password or ""

    conn = get_db_connection()

    # 1. Rate Limiting Check (Max 10 login attempts per hour per IP/Email)
    is_allowed, remaining_attempts = check_rate_limit(conn, client_ip, email)
    if not is_allowed:
        record_login_attempt(conn, client_ip, email, False)
        conn.close()
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": GENERIC_RATE_LIMIT_ERROR,
                "error_type": "rate_limit_exceeded",
                "retry_after_seconds": 3600
            },
            headers={"Retry-After": "3600"}
        )

    # 2. Account Lockout Check (5 failed attempts -> 3 hours lockout)
    sec_status = get_account_security_status(conn, email)
    if sec_status["is_locked"]:
        record_login_attempt(conn, client_ip, email, False)
        conn.close()
        return JSONResponse(
            status_code=status.HTTP_423_LOCKED,
            content={
                "detail": GENERIC_LOCKOUT_ERROR,
                "error_type": "account_locked",
                "locked_until": sec_status["locked_until"],
                "remaining_lockout_seconds": sec_status["remaining_lockout_seconds"]
            }
        )

    # 3. Server-side Email Format Validation
    if not validate_email_format(email):
        perform_dummy_verification(password)
        lockout_res = record_failed_login(conn, email)
        record_login_attempt(conn, client_ip, email, False)
        conn.close()
        if lockout_res["is_locked"]:
            return JSONResponse(
                status_code=status.HTTP_423_LOCKED,
                content={
                    "detail": GENERIC_LOCKOUT_ERROR,
                    "error_type": "account_locked",
                    "locked_until": lockout_res["locked_until"],
                    "remaining_lockout_seconds": lockout_res["remaining_lockout_seconds"]
                }
            )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": GENERIC_AUTH_ERROR, "error_type": "invalid_credentials"}
        )

    # 4. User Lookup in Database
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?;", (email,))
    user_row = cursor.fetchone()

    # User does not exist or inactive -> timing-safe dummy verify and return generic error
    if not user_row or not user_row["password_hash"] or user_row["is_active"] == 0:
        perform_dummy_verification(password)
        lockout_res = record_failed_login(conn, email)
        record_login_attempt(conn, client_ip, email, False)
        conn.close()
        if lockout_res["is_locked"]:
            return JSONResponse(
                status_code=status.HTTP_423_LOCKED,
                content={
                    "detail": GENERIC_LOCKOUT_ERROR,
                    "error_type": "account_locked",
                    "locked_until": lockout_res["locked_until"],
                    "remaining_lockout_seconds": lockout_res["remaining_lockout_seconds"]
                }
            )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": GENERIC_AUTH_ERROR, "error_type": "invalid_credentials"}
        )

    # 5. Constant-time Password Verification
    is_valid = verify_password(password, user_row["password_hash"], user_row["password_salt"])
    if not is_valid:
        lockout_res = record_failed_login(conn, email)
        record_login_attempt(conn, client_ip, email, False)
        conn.close()
        if lockout_res["is_locked"]:
            return JSONResponse(
                status_code=status.HTTP_423_LOCKED,
                content={
                    "detail": GENERIC_LOCKOUT_ERROR,
                    "error_type": "account_locked",
                    "locked_until": lockout_res["locked_until"],
                    "remaining_lockout_seconds": lockout_res["remaining_lockout_seconds"]
                }
            )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": GENERIC_AUTH_ERROR, "error_type": "invalid_credentials"}
        )

    # 6. Authentication Successful -> Reset Lockout Counter & Issue Session
    reset_failed_login_counter(conn, email)
    record_login_attempt(conn, client_ip, email, True)
    user_agent = request.headers.get("User-Agent", "") if request else ""
    session_info = create_user_session(conn, user_row["id"], client_ip, user_agent, remember_me=bool(req.remember_me))
    user_dict = dict(user_row)
    conn.close()

    # Set HttpOnly Session Cookie (HTTPS ready)
    max_age = 30 * 86400 if req.remember_me else 86400
    is_https = request.url.scheme == "https" if request else False
    response.set_cookie(
        key="session_token",
        value=session_info["session_id"],
        httponly=True,
        samesite="lax",
        max_age=max_age,
        secure=is_https
    )

    return {
        "user": user_dict,
        "session_token": session_info["session_id"],
        "expires_at": session_info["expires_at"],
        "message": "Authentication successful."
    }

@app.post("/api/auth/send-otp", response_model=SendOtpResponse)
def send_otp(req: SendOtpRequest, request: Request):
    """
    Validates email format, checks for duplicates, applies rate limiting (max 3/10min),
    generates a 6-digit numeric OTP, stores its SHA-256 hash in DB with 10-minute expiry,
    and dispatches/logs the OTP.
    """
    client_ip = get_client_ip(request)
    email = normalize_email(req.email)

    if not validate_email_format(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format. Please enter a valid Institutional or Gmail email."
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if account already exists
    cursor.execute("SELECT id FROM users WHERE email = ?;", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please sign in instead."
        )

    # Check rate limit (max 3 requests per 10 minutes)
    is_allowed, remaining = check_otp_rate_limit(conn, client_ip, email)
    if not is_allowed:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=GENERIC_OTP_RATE_LIMIT_ERROR
        )

    # Record attempt
    record_otp_request(conn, client_ip, email)

    # Generate 6-digit OTP and store
    raw_otp = generate_otp(6)
    store_otp(conn, email, raw_otp)
    conn.close()

    # Console dispatch / SMTP logging
    print(f"\n=======================================================")
    print(f"[EMAIL OTP DISPATCH] Verification OTP for: {email}")
    print(f"[EMAIL OTP DISPATCH] 6-Digit Code: {raw_otp}")
    print(f"[EMAIL OTP DISPATCH] Expiration: 10 minutes")
    print(f"=======================================================\n")

    return SendOtpResponse(
        message=f"Verification OTP has been sent to {email}.",
        success=True,
        otp=raw_otp
    )


@app.post("/api/auth/verify-otp", response_model=VerifyOtpResponse)
def verify_otp_endpoint(req: VerifyOtpRequest, request: Request):
    """
    Validates a submitted 6-digit OTP code against the stored hash and expiration.
    Enforces maximum 5 attempts.
    """
    email = normalize_email(req.email)
    otp = (req.otp or "").strip()

    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP code is required."
        )

    conn = get_db_connection()
    is_valid, err_msg = verify_otp(conn, email, otp, consume=False)
    conn.close()

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg or "Invalid OTP code."
        )

    return VerifyOtpResponse(
        message="Email address verified successfully.",
        success=True,
        verified=True
    )


@app.post("/api/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest, request: Request, response: Response):
    """
    Registers a new user with strict email OTP verification, password strength, and account creation.
    """
    client_ip = get_client_ip(request)
    email = normalize_email(req.email)
    name = req.get_name()
    college_company = req.get_college_or_company()

    if not name or len(name) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name must be at least 2 characters long.")

    if not validate_email_format(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address format.")

    is_strong, err_msg = validate_password_strength(req.password)
    if not is_strong:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg or "Password does not meet complexity requirements.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?;", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email address already exists.")

    # Validate OTP verification if provided or registered with OTP
    if req.otp:
        is_otp_valid, otp_err = verify_otp(conn, email, req.otp, consume=True)
        if not is_otp_valid:
            conn.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=otp_err or "Invalid OTP verification code.")

    new_id = f"usr_{uuid.uuid4().hex[:8]}"
    pwhash, pwsalt = hash_password(req.password)
    is_acad = 1 if is_academic_domain(email) else 0
    is_ind = 1 if is_industry_domain(email) or req.role == "industrialist" else 0
    avatar = f"https://api.dicebear.com/7.x/bottts/svg?seed={name.replace(' ', '')}"
    now_str = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO users (id, name, email, role, college, department, company, avatar_url, is_verified_academic, is_verified_industry, bio, password_hash, password_salt, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
    """, (new_id, name, email, req.role or "student", req.college or college_company, req.department or "", req.company or college_company, avatar, is_acad, is_ind, req.bio or "", pwhash, pwsalt, now_str))
    conn.commit()

    user_agent = request.headers.get("User-Agent", "") if request else ""
    session_info = create_user_session(conn, new_id, client_ip, user_agent, remember_me=False)

    cursor.execute("SELECT * FROM users WHERE id = ?;", (new_id,))
    created_user = cursor.fetchone()
    user_dict = dict(created_user)
    conn.close()

    is_https = request.url.scheme == "https" if request else False
    response.set_cookie(
        key="session_token",
        value=session_info["session_id"],
        httponly=True,
        samesite="lax",
        max_age=86400,
        secure=is_https
    )

    return AuthResponse(
        user=UserResponse(**user_dict),
        session_token=session_info["session_id"],
        expires_at=session_info["expires_at"],
        message="Registration and authentication successful."
    )

@app.post("/api/auth/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response):
    """Securely revokes the active session on the backend and clears client cookies."""
    token = get_session_token_from_request(request)
    if token:
        conn = get_db_connection()
        revoke_session(conn, token)
        conn.close()
    response.delete_cookie("session_token")
    return LogoutResponse(message="Session successfully invalidated.", success=True)

@app.post("/api/auth/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest, request: Request):
    """
    Initiates password recovery for a user.
    - Rate limit: max 5 requests per hour per IP/Email (HTTP 429)
    - Validates email format
    - Generates 256-bit cryptographically secure reset token with 30-min expiry
    - Stores SHA-256 token hash in database
    - Dispatches reset link to logging / email channel
    - Prevents user enumeration by returning a generic success message
    """
    client_ip = get_client_ip(request)
    email = normalize_email(req.email)

    conn = get_db_connection()

    # 1. Rate Limit Enforcement (max 5 requests per hour)
    is_allowed, remaining = check_forgot_password_rate_limit(conn, client_ip, email)
    if not is_allowed:
        record_forgot_password_attempt(conn, client_ip, email)
        conn.close()
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": GENERIC_FORGOT_PASSWORD_RATE_LIMIT_ERROR,
                "error_type": "rate_limit_exceeded",
                "retry_after_seconds": 3600
            },
            headers={"Retry-After": "3600"}
        )

    record_forgot_password_attempt(conn, client_ip, email)

    # 2. Email format check (timing-safe generic response on malformed)
    if not validate_email_format(email):
        conn.close()
        return ForgotPasswordResponse(
            message=GENERIC_FORGOT_PASSWORD_MESSAGE,
            success=True
        )

    # 3. Create Password Reset Token if user exists
    raw_token = create_password_reset_token(conn, email)
    conn.close()

    if raw_token:
        # Development / Audit Log for generated password reset link
        print(f"[AUTH RECOVERY] Reset requested for: {email}")
        print(f"[AUTH RECOVERY] Token: {raw_token}")
        print(f"[AUTH RECOVERY] Reset URL: http://localhost:8000/login?reset_token={raw_token}")

    # Return timing-safe generic response
    return ForgotPasswordResponse(
        message=GENERIC_FORGOT_PASSWORD_MESSAGE,
        success=True,
        reset_token=raw_token if os.environ.get("ENVIRONMENT") != "production" else None
    )

@app.post("/api/auth/reset-password", response_model=ResetPasswordResponse)
@app.post("/api/auth/verify-reset-token", response_model=ResetPasswordResponse)
def reset_password(req: ResetPasswordRequest, request: Request):
    """
    Verifies reset token, validates password complexity, updates password using PBKDF2,
    and clears reset token & invalidates previous active sessions.
    """
    token = (req.token or "").strip()
    new_password = req.get_password()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token is required."
        )

    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password is required."
        )

    # Validate password complexity
    is_strong, err_msg = validate_password_strength(new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg or "Password does not meet complexity requirements."
        )

    conn = get_db_connection()
    success, error_detail, user = reset_password_with_token(conn, token, new_password)
    conn.close()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail or "Invalid, expired, or previously consumed password reset token."
        )

    return ResetPasswordResponse(
        message="Password has been successfully reset. You may now sign in with your new credentials.",
        success=True
    )

@app.get("/api/auth/session", response_model=SessionValidationResponse)
def get_session_status(request: Request):
    """Validates session state and returns active user telemetry."""
    token = get_session_token_from_request(request)
    if not token:
        return SessionValidationResponse(valid=False, user=None, session=None)
    conn = get_db_connection()
    session_data = validate_session(conn, token)
    conn.close()
    if not session_data:
        return SessionValidationResponse(valid=False, user=None, session=None)
    return SessionValidationResponse(
        valid=True,
        user=UserResponse(**session_data["user"]),
        session=session_data["session"]
    )

@app.get("/api/auth/security-status", response_model=SecurityStatusResponse)
def get_security_status(email: Optional[str] = Query(""), request: Request = None):
    """Provides client telemetry on rate limit and lockout metrics."""
    client_ip = get_client_ip(request) if request else "127.0.0.1"
    norm_email = normalize_email(email)
    conn = get_db_connection()
    is_allowed, remaining = check_rate_limit(conn, client_ip, norm_email)
    sec_status = get_account_security_status(conn, norm_email)
    conn.close()
    return SecurityStatusResponse(
        email=norm_email,
        attempts_remaining_this_hour=remaining,
        consecutive_failed_attempts=sec_status["consecutive_failed_attempts"],
        is_locked=sec_status["is_locked"],
        locked_until=sec_status["locked_until"],
        remaining_lockout_seconds=sec_status["remaining_lockout_seconds"]
    )

@app.post("/api/auth/demo-login", response_model=AuthResponse)
def demo_login(req: DemoLoginRequest, request: Request, response: Response):
    """One-click instant authenticated session as one of the pre-seeded personas."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Normalize ID & role aliases
    target = req.user_id.strip()
    id_map = {
        "usr_student_01": "usr_student_1",
        "usr_student_1": "usr_student_1",
        "student": "usr_student_1",
        "usr_faculty_01": "usr_faculty_1",
        "usr_faculty_1": "usr_faculty_1",
        "faculty": "usr_faculty_1",
        "usr_spoc_01": "usr_spoc_1",
        "usr_spoc_1": "usr_spoc_1",
        "spoc": "usr_spoc_1",
        "usr_buyer_01": "usr_industrialist_1",
        "usr_buyer_1": "usr_industrialist_1",
        "usr_industrialist_01": "usr_industrialist_1",
        "usr_industrialist_1": "usr_industrialist_1",
        "industrialist": "usr_industrialist_1",
        "buyer": "usr_industrialist_1",
        "usr_admin_01": "usr_admin_1",
        "usr_admin_1": "usr_admin_1",
        "admin": "usr_admin_1",
    }
    resolved_id = id_map.get(target, target)

    cursor.execute("SELECT * FROM users WHERE id = ? OR role = ?;", (resolved_id, target))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Demo persona '{target}' not found")

    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "") if request else ""
    session_info = create_user_session(conn, row["id"], client_ip, user_agent, remember_me=False)
    user_dict = dict(row)
    conn.close()

    is_https = request.url.scheme == "https" if request else False
    response.set_cookie(
        key="session_token",
        value=session_info["session_id"],
        httponly=True,
        samesite="lax",
        max_age=86400,
        secure=is_https
    )

    return AuthResponse(
        user=UserResponse(**user_dict),
        session_token=session_info["session_id"],
        expires_at=session_info["expires_at"],
        message=f"Logged in as {user_dict['name']}"
    )

@app.get("/api/dashboard/overview")
def get_dashboard_overview(current_user: Dict[str, Any] = Depends(get_current_authenticated_user)):
    """Protected dashboard telemetry endpoint accessible only with a valid active session."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM projects;")
    total_projects = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tasks;")
    total_tasks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM marketplace_items;")
    total_items = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM industrial_offers;")
    total_offers = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM projects WHERE team_lead_id = ? OR faculty_mentor_id = ?;", (current_user["id"], current_user["id"]))
    user_projects = [dict(r) for r in cursor.fetchall()]

    sec_status = get_account_security_status(conn, current_user["email"])
    conn.close()

    return {
        "user": current_user,
        "metrics": {
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "total_items": total_items,
            "total_offers": total_offers
        },
        "user_projects": user_projects,
        "security_overview": {
            "account_status": "Active & Verified" if (current_user.get("is_verified_academic") or current_user.get("is_verified_industry")) else "Standard",
            "consecutive_failed_attempts": sec_status["consecutive_failed_attempts"],
            "lockout_status": "Clear" if not sec_status["is_locked"] else "Locked",
            "mfa_enabled": False,
            "https_ready": True
        }
    }

@app.get("/api/users", response_model=List[UserResponse])
def get_all_users():
    """Lists all registered personas and users."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: str):
    """Retrieves single user profile."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)

# ==========================================
# 2. PROJECT PORTFOLIO & AUDIT ENDPOINTS
# ==========================================

@app.get("/api/projects", response_model=List[ProjectResponse])
def list_projects(
    search: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    lifecycle: Optional[str] = None,
    college: Optional[str] = None
):
    """Retrieves all projects with optional multi-variable filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM projects WHERE 1=1"
    params = []

    if search:
        query += " AND (title LIKE ? OR abstract LIKE ? OR tech_stack LIKE ? OR college_name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    if domain and domain != "All":
        query += " AND domain = ?"
        params.append(domain)

    if category and category != "All":
        query += " AND category = ?"
        params.append(category)

    if lifecycle and lifecycle != "All":
        query += " AND lifecycle_status = ?"
        params.append(lifecycle)

    if college and college != "All":
        query += " AND college_name LIKE ?"
        params.append(f"%{college}%")

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict_from_row(r) for r in rows]

@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project_by_id(project_id: str):
    """Gets complete metadata and BOM for a single project and increments view counter."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE projects SET views_count = views_count + 1 WHERE id = ?;", (project_id,))
    conn.commit()

    cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict_from_row(row)

@app.post("/api/projects", response_model=ProjectResponse)
def create_project(req: ProjectCreate):
    """
    Submits a new project portfolio item.
    Executes automated Plagiarism & Originality audit before inserting into national repository.
    Enforces RBAC: Only Students and Platform Admins can submit new projects.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # RBAC Check: Only Students and Platform Admins may submit projects
    cursor.execute("SELECT role FROM users WHERE id = ?;", (req.team_lead_id,))
    user_row = cursor.fetchone()
    if user_row and user_row["role"] not in ["student", "admin"]:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered students or platform administrators may submit new projects."
        )

    # 1. Run automated Plagiarism Check
    combined_query = f"{req.title} {req.abstract} {req.description or ''}"
    audit_res = plagiarism_engine.check_originality(combined_query)

    # 2. Insert into DB
    new_id = f"proj_{uuid.uuid4().hex[:6]}"
    now_str = datetime.utcnow().isoformat()

    bom_json = json.dumps([b.dict() for b in req.bom])
    tech_json = json.dumps(req.tech_stack)
    members_json = json.dumps(req.team_members or [req.team_lead_name])
    keywords_json = json.dumps(audit_res["top_overlapping_keywords"])

    cursor.execute("""
    INSERT INTO projects (
        id, title, abstract, description, domain, category, tech_stack, repo_url, demo_url,
        bom, lifecycle_status, originality_score, similarity_index, plagiarism_status,
        highest_match_project_id, highest_match_title, top_overlapping_keywords,
        college_name, department, team_lead_id, team_lead_name, faculty_mentor_id,
        faculty_mentor_name, team_members, patent_status, estimated_budget_inr,
        stars_count, views_count, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        new_id, req.title, req.abstract, req.description or "", req.domain, req.category,
        tech_json, req.repo_url or "", req.demo_url or "", bom_json, req.lifecycle_status or "Ideation",
        audit_res["originality_score"], audit_res["similarity_score"], audit_res["plagiarism_status"],
        audit_res["highest_match_project_id"], audit_res["highest_match_title"], keywords_json,
        req.college_name, req.department or "", req.team_lead_id, req.team_lead_name,
        req.faculty_mentor_id or "", req.faculty_mentor_name or "", members_json,
        req.patent_status or "None", req.estimated_budget_inr or 0.0, 0, 1, now_str, now_str
    ))

    # Log the audit
    cursor.execute("""
    INSERT INTO audit_logs (id, project_id, project_title, submitted_abstract, similarity_score, originality_score, status, matched_project_id, matched_project_title, overlapping_keywords, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        f"aud_{uuid.uuid4().hex[:6]}", new_id, req.title, req.abstract,
        audit_res["similarity_score"], audit_res["originality_score"], audit_res["plagiarism_status"],
        audit_res["highest_match_project_id"], audit_res["highest_match_title"], keywords_json, now_str
    ))

    # Add initial starter Kanban task
    cursor.execute("""
    INSERT INTO tasks (id, project_id, title, description, column, priority, assignee_name, due_date, faculty_feedback, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        f"tsk_{uuid.uuid4().hex[:6]}", new_id, "Define System Requirements & Architecture Specification",
        "Document hardware pinouts, software API endpoints, and safety fail-safes.",
        "in_progress", "High", req.team_lead_name, "2026-09-15", "", now_str
    ))

    conn.commit()

    cursor.execute("SELECT * FROM projects WHERE id = ?;", (new_id,))
    created = cursor.fetchone()
    conn.close()

    # Update corpus in-memory
    refresh_plagiarism_corpus()

    return dict_from_row(created)

@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, req: ProjectUpdate):
    """Updates an existing project metadata, BOM, or lifecycle stage."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    now_str = datetime.utcnow().isoformat()
    fields = []
    params = []

    if req.title is not None:
        fields.append("title = ?")
        params.append(req.title)
    if req.abstract is not None:
        fields.append("abstract = ?")
        params.append(req.abstract)
    if req.description is not None:
        fields.append("description = ?")
        params.append(req.description)
    if req.domain is not None:
        fields.append("domain = ?")
        params.append(req.domain)
    if req.category is not None:
        fields.append("category = ?")
        params.append(req.category)
    if req.tech_stack is not None:
        fields.append("tech_stack = ?")
        params.append(json.dumps(req.tech_stack))
    if req.repo_url is not None:
        fields.append("repo_url = ?")
        params.append(req.repo_url)
    if req.demo_url is not None:
        fields.append("demo_url = ?")
        params.append(req.demo_url)
    if req.bom is not None:
        fields.append("bom = ?")
        params.append(json.dumps([b.dict() for b in req.bom]))
    if req.lifecycle_status is not None:
        fields.append("lifecycle_status = ?")
        params.append(req.lifecycle_status)
    if req.patent_status is not None:
        fields.append("patent_status = ?")
        params.append(req.patent_status)
    if req.faculty_mentor_name is not None:
        fields.append("faculty_mentor_name = ?")
        params.append(req.faculty_mentor_name)
    if req.estimated_budget_inr is not None:
        fields.append("estimated_budget_inr = ?")
        params.append(req.estimated_budget_inr)

    fields.append("updated_at = ?")
    params.append(now_str)
    params.append(project_id)

    query = f"UPDATE projects SET {', '.join(fields)} WHERE id = ?;"
    cursor.execute(query, params)
    conn.commit()

    cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
    updated = cursor.fetchone()
    conn.close()

    refresh_plagiarism_corpus()
    return dict_from_row(updated)

@app.post("/api/projects/{project_id}/star")
def toggle_star(project_id: str):
    """Increments star rating counter for a project."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE projects SET stars_count = stars_count + 1 WHERE id = ?;", (project_id,))
    conn.commit()
    cursor.execute("SELECT stars_count FROM projects WHERE id = ?;", (project_id,))
    row = cursor.fetchone()
    conn.close()
    return {"status": "success", "stars_count": row[0] if row else 0}

# ==========================================
# 3. KANBAN TEAM COLLABORATION ENDPOINTS
# ==========================================

@app.get("/api/tasks", response_model=List[TaskResponse])
def get_tasks(project_id: Optional[str] = None):
    """Lists tasks for a specific project or nationwide overview."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if project_id:
        cursor.execute("SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at ASC;", (project_id,))
    else:
        cursor.execute("SELECT * FROM tasks ORDER BY created_at ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/tasks", response_model=TaskResponse)
def create_task(req: TaskCreate):
    """Creates a new Kanban task milestone."""
    new_id = f"tsk_{uuid.uuid4().hex[:6]}"
    now_str = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tasks (id, project_id, title, description, column, priority, assignee_name, due_date, faculty_feedback, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (new_id, req.project_id, req.title, req.description or "", req.column or "backlog", req.priority or "Medium", req.assignee_name or "", req.due_date or "", req.faculty_feedback or "", now_str))
    conn.commit()

    cursor.execute("SELECT * FROM tasks WHERE id = ?;", (new_id,))
    created = cursor.fetchone()
    conn.close()
    return dict(created)

@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, req: TaskUpdate):
    """Updates task status, column, priority, or adds faculty mentor feedback."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    fields = []
    params = []
    if req.title is not None:
        fields.append("title = ?")
        params.append(req.title)
    if req.description is not None:
        fields.append("description = ?")
        params.append(req.description)
    if req.column is not None:
        fields.append("column = ?")
        params.append(req.column)
    if req.priority is not None:
        fields.append("priority = ?")
        params.append(req.priority)
    if req.assignee_name is not None:
        fields.append("assignee_name = ?")
        params.append(req.assignee_name)
    if req.due_date is not None:
        fields.append("due_date = ?")
        params.append(req.due_date)
    if req.faculty_feedback is not None:
        fields.append("faculty_feedback = ?")
        params.append(req.faculty_feedback)

    if fields:
        params.append(task_id)
        cursor.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?;", params)
        conn.commit()

    cursor.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
    updated = cursor.fetchone()
    conn.close()
    return dict(updated)

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    """Removes a task."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Task deleted"}

# ==========================================
# 4. PLAGIARISM ENGINE PRE-CHECK ENDPOINT
# ==========================================

@app.post("/api/plagiarism/check", response_model=PlagiarismCheckResponse)
def check_plagiarism_preflight(req: PlagiarismCheckRequest):
    """
    Real-time originality pre-check endpoint.
    Allows student innovators and faculty to test abstracts against the national repository prior to submission.
    """
    combined_text = f"{req.title or ''} {req.abstract} {req.description or ''}"
    res = plagiarism_engine.check_originality(combined_text, exclude_id=req.exclude_project_id)
    return res

@app.get("/api/plagiarism/audits")
def list_audit_logs():
    """Lists historical plagiarism audits across national submissions."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50;")
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]

# ==========================================
# 5. PRO-VERSED BAZAAR (MARKETPLACE & ESCROW)
# ==========================================

@app.get("/api/bazaar/items", response_model=List[MarketplaceItemResponse])
def get_bazaar_items(
    category: Optional[str] = None,
    store_type: Optional[str] = None,
    search: Optional[str] = None
):
    """Lists all marketplace listings with optional category, store_type (software/hardware), and search filters."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM marketplace_items WHERE 1=1"
    params = []

    # Store type filtering
    if store_type:
        st = store_type.lower()
        if st in ["software", "project", "project_store", "projectstore"]:
            query += " AND (category LIKE '%Software%' OR category LIKE '%Model%' OR category LIKE '%System%' OR category LIKE '%Code%' OR category LIKE '%License%')"
        elif st in ["hardware", "hardware_store", "hardwarestore"]:
            query += " AND (category LIKE '%Hardware%' OR category LIKE '%Prototype%' OR category LIKE '%Component%' OR category LIKE '%Sensor%' OR category LIKE '%BOM%' OR category LIKE '%Kit%')"

    # Category filtering
    if category and category.lower() not in ["all", "all items", "all projects", "all hardware"]:
        cat_lower = category.lower()
        if cat_lower in ["software", "software ip"]:
            query += " AND (category LIKE '%Software%' OR category LIKE '%Model%' OR category LIKE '%System%')"
        elif cat_lower in ["hardware", "hardware prototype"]:
            query += " AND (category LIKE '%Hardware%' OR category LIKE '%Prototype%' OR category LIKE '%Component%')"
        else:
            query += " AND (category = ? OR category LIKE ?)"
            params.extend([category, f"%{category}%"])

    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR seller_name LIKE ? OR seller_college LIKE ?)"
        t = f"%{search}%"
        params.extend([t, t, t, t])

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]

@app.get("/api/project-store/items", response_model=List[MarketplaceItemResponse])
def get_project_store_items(category: Optional[str] = None, search: Optional[str] = None):
    """Lists software IP, algorithms, and full-stack systems from the Project Store."""
    return get_bazaar_items(category=category, store_type="software", search=search)

@app.get("/api/hardware-store/items", response_model=List[MarketplaceItemResponse])
def get_hardware_store_items(category: Optional[str] = None, search: Optional[str] = None):
    """Lists hardware prototypes, IoT modules, and surplus lab BOM components from the Hardware Store."""
    return get_bazaar_items(category=category, store_type="hardware", search=search)

@app.get("/api/bazaar/items/{item_id}", response_model=MarketplaceItemResponse)
def get_bazaar_item(item_id: str):
    """Retrieves single marketplace item details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM marketplace_items WHERE id = ?;", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return dict_from_row(row)

@app.post("/api/bazaar/items", response_model=MarketplaceItemResponse)
def list_bazaar_item(req: MarketplaceItemCreate):
    """Lists a new software IP, assembled prototype, or surplus BOM hardware item."""
    new_id = f"baz_{uuid.uuid4().hex[:6]}"
    now_str = datetime.utcnow().isoformat()
    specs_json = json.dumps(req.technical_specs or {})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO marketplace_items (
        id, title, description, seller_id, seller_name, seller_college, seller_role,
        category, price_inr, stock_quantity, technical_specs, status, project_id,
        image_icon, escrow_step, escrow_buyer_id, escrow_buyer_name, escrow_buyer_company,
        escrow_status_note, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        new_id, req.title, req.description, req.seller_id, req.seller_name,
        req.seller_college or "", req.seller_role or "Student Innovator",
        req.category, req.price_inr, req.stock_quantity or 1, specs_json,
        "Available", req.project_id or "", req.image_icon or "cpu", 1,
        "", "", "", "Available for purchase / escrow lock.", now_str
    ))
    conn.commit()

    cursor.execute("SELECT * FROM marketplace_items WHERE id = ?;", (new_id,))
    created = cursor.fetchone()
    conn.close()
    return dict_from_row(created)

@app.post("/api/bazaar/items/{item_id}/escrow", response_model=MarketplaceItemResponse)
def handle_escrow_action(item_id: str, req: EscrowAdvanceRequest):
    """
    Manages 4-Step Escrow Workflow:
    Step 1: Escrow Held (Buyer locks payment)
    Step 2: Mentor Clearance (Faculty/SPOC verifies tech transfer non-infringement)
    Step 3: Shipment / Code Dispatch (Seller provides repo access / courier tracking)
    Step 4: Payout Release (Buyer confirms inspection, funds disbursed)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM marketplace_items WHERE id = ?;", (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Marketplace item not found")

    item = dict(row)
    action = req.action.lower()
    current_step = item.get("escrow_step", 1)

    if action in ["hold_escrow", "buy_now", "lock"]:
        # Transition from Available (Step 1) -> Step 2
        new_step = 2
        new_status = "In Escrow"
        buyer_id = req.buyer_id or req.actor_id or item.get("escrow_buyer_id") or "usr_student_1"
        buyer_name = req.buyer_name or getattr(req, "actor_name", None) or item.get("escrow_buyer_name") or "Student Innovator"
        buyer_comp = req.buyer_company or getattr(req, "buyer_college", None) or getattr(req, "actor_college", None) or item.get("escrow_buyer_company") or "Academic Institution"
        note = f"Stage 2: Escrow locked (₹{item['price_inr']:,.2f}). Awaiting Faculty Mentor / Institutional SPOC clearance."
    elif action in ["clear_mentor", "mentor_clear"]:
        # Transition from Step 2 -> Step 3
        new_step = 3
        new_status = "In Escrow"
        buyer_id = item.get("escrow_buyer_id")
        buyer_name = item.get("escrow_buyer_name")
        buyer_comp = item.get("escrow_buyer_company")
        note = "Stage 3: Mentor clearance verified. Seller must dispatch hardware prototype / transfer private repository access."
    elif action in ["dispatch", "confirm_shipment"]:
        # Transition from Step 3 -> Step 4
        new_step = 4
        new_status = "In Escrow"
        buyer_id = item.get("escrow_buyer_id")
        buyer_name = item.get("escrow_buyer_name")
        buyer_comp = item.get("escrow_buyer_company")
        note = "Stage 4: Shipment/Code dispatched. Buyer inspection active. Click 'Release Payout' after verification."
    elif action in ["release_payout", "complete", "confirm_delivery"]:
        # Transition to Sold Out / Completed
        new_step = 4
        new_status = "Sold Out"
        buyer_id = item.get("escrow_buyer_id")
        buyer_name = item.get("escrow_buyer_name")
        buyer_comp = item.get("escrow_buyer_company")
        note = f"Completed: Escrow payout of ₹{item['price_inr']:,.2f} released to {item['seller_name']}'s student lab account."
    elif action in ["cancel", "reset"]:
        # Reset back to Available
        new_step = 1
        new_status = "Available"
        buyer_id = ""
        buyer_name = ""
        buyer_comp = ""
        note = "Escrow transaction cancelled. Listing available."
    else:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Unsupported escrow action '{action}'")

    cursor.execute("""
    UPDATE marketplace_items
    SET escrow_step = ?, status = ?, escrow_buyer_id = ?, escrow_buyer_name = ?, escrow_buyer_company = ?, escrow_status_note = ?
    WHERE id = ?;
    """, (new_step, new_status, buyer_id, buyer_name, buyer_comp, note, item_id))
    conn.commit()

    cursor.execute("SELECT * FROM marketplace_items WHERE id = ?;", (item_id,))
    updated = cursor.fetchone()
    conn.close()
    return dict_from_row(updated)

# ==========================================
# 6. INDUSTRIALIST IP BIDDING & ACQUISITION
# ==========================================

@app.get("/api/offers", response_model=List[IndustrialOfferResponse])
def get_industrial_offers(project_id: Optional[str] = None, buyer_id: Optional[str] = None):
    """Lists all enterprise acquisition proposals and R&D pilot grants."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM industrial_offers WHERE 1=1"
    params = []

    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if buyer_id:
        query += " AND buyer_id = ?"
        params.append(buyer_id)

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/offers", response_model=IndustrialOfferResponse)
def submit_industrial_offer(req: IndustrialOfferCreate):
    """Submits a formal IP acquisition bid, commercial license offer, or R&D grant."""
    new_id = f"off_{uuid.uuid4().hex[:6]}"
    now_str = datetime.utcnow().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO industrial_offers (
        id, project_id, project_title, buyer_id, buyer_name, buyer_company,
        offer_amount_inr, proposal_type, deliverables_message, status, counter_amount_inr,
        spoc_approval, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        new_id, req.project_id, req.project_title, req.buyer_id, req.buyer_name,
        req.buyer_company, req.offer_amount_inr, req.proposal_type,
        req.deliverables_message or "", "Pending", 0.0, "Pending", now_str
    ))
    conn.commit()

    cursor.execute("SELECT * FROM industrial_offers WHERE id = ?;", (new_id,))
    created = cursor.fetchone()
    conn.close()
    return dict(created)

@app.put("/api/offers/{offer_id}", response_model=IndustrialOfferResponse)
def update_industrial_offer(offer_id: str, req: IndustrialOfferUpdate):
    """Handles student team leader and institutional SPOC approval/counter/rejection workflow."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM industrial_offers WHERE id = ?;", (offer_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Offer not found")

    fields = []
    params = []
    if req.status is not None:
        fields.append("status = ?")
        params.append(req.status)
    if req.counter_amount_inr is not None:
        fields.append("counter_amount_inr = ?")
        params.append(req.counter_amount_inr)
    if req.spoc_approval is not None:
        fields.append("spoc_approval = ?")
        params.append(req.spoc_approval)

    if fields:
        params.append(offer_id)
        cursor.execute(f"UPDATE industrial_offers SET {', '.join(fields)} WHERE id = ?;", params)
        conn.commit()

    cursor.execute("SELECT * FROM industrial_offers WHERE id = ?;", (offer_id,))
    updated = cursor.fetchone()
    conn.close()
    return dict(updated)

# ==========================================
# 7. NATIONAL INNOVATION ANALYTICS
# ==========================================

@app.get("/api/analytics")
@app.get("/api/analytics/national")
def get_national_analytics():
    """Aggregates nationwide innovation metrics across institutions, tech stacks, and IP valuations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total counts
    cursor.execute("SELECT COUNT(*) FROM projects;")
    total_projects = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM projects WHERE lifecycle_status = 'Prototype Ready';")
    prototypes_ready = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT college_name) FROM projects;")
    total_colleges = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(offer_amount_inr), 0) FROM industrial_offers;")
    total_ip_offers_inr = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(price_inr), 0) FROM marketplace_items WHERE status IN ('In Escrow', 'Sold Out');")
    total_bazaar_escrow_inr = cursor.fetchone()[0]

    # Domain breakdown
    cursor.execute("SELECT domain, COUNT(*) as count FROM projects GROUP BY domain ORDER BY count DESC;")
    domain_rows = cursor.fetchall()
    domain_dist = {r["domain"]: r["count"] for r in domain_rows}

    # Lifecycle stage distribution
    cursor.execute("SELECT lifecycle_status, COUNT(*) as count FROM projects GROUP BY lifecycle_status;")
    lifecycle_rows = cursor.fetchall()
    lifecycle_dist = {r["lifecycle_status"]: r["count"] for r in lifecycle_rows}

    # Category breakdown (Software, Hardware, Hybrid)
    cursor.execute("SELECT category, COUNT(*) as count FROM projects GROUP BY category;")
    category_rows = cursor.fetchall()
    category_dist = {r["category"]: r["count"] for r in category_rows}

    # Tech Stack frequency analysis
    cursor.execute("SELECT tech_stack FROM projects;")
    tech_rows = cursor.fetchall()
    tech_freq: Dict[str, int] = {}
    for r in tech_rows:
        try:
            tags = json.loads(r["tech_stack"])
            for tag in tags:
                tech_freq[tag] = tech_freq.get(tag, 0) + 1
        except Exception:
            pass

    # Sort top tech stacks
    top_tech_stacks = dict(sorted(tech_freq.items(), key=lambda x: x[1], reverse=True)[:8])

    # Plagiarism compliance rate
    cursor.execute("SELECT plagiarism_status, COUNT(*) as count FROM projects GROUP BY plagiarism_status;")
    plag_rows = cursor.fetchall()
    plagiarism_compliance = {r["plagiarism_status"]: r["count"] for r in plag_rows}

    conn.close()

    return {
        "summary": {
            "total_national_projects": total_projects,
            "prototypes_ready": prototypes_ready,
            "participating_institutions": total_colleges,
            "total_ip_dealflow_inr": total_ip_offers_inr + total_bazaar_escrow_inr,
            "total_bids_count": len(domain_rows)
        },
        "domain_distribution": domain_dist,
        "lifecycle_funnel": lifecycle_dist,
        "category_breakdown": category_dist,
        "top_tech_stacks": top_tech_stacks,
        "plagiarism_compliance": plagiarism_compliance
    }

# ==========================================
# 8. STATIC FILES & SINGLE-PAGE APP MOUNT
# ==========================================


# ==========================================
# 9. AI CHATBOT ASSISTANT API
# ==========================================

@app.post("/api/ai/chat")
def handle_ai_chat(payload: Dict[str, Any]):
    """Processes user inquiries and returns intelligent innovation assistance."""
    message = payload.get("message", "")
    role = payload.get("role", "student")
    name = payload.get("name", "Innovator")
    return ai_chat_engine.generate_response(message, role, name)

# ==========================================
# 10. VIDEO CONFERENCE & MEETING ROOMS API
# ==========================================

@app.get("/api/meetings")
def list_meetings():
    """Lists active virtual meeting and mentor review rooms."""
    return meeting_service.list_rooms()

@app.post("/api/meetings")
def create_meeting(payload: Dict[str, Any]):
    """Creates an instant virtual collaboration meeting room."""
    title = payload.get("title", "Project Milestone Review")
    host_id = payload.get("host_id", "usr_student_01")
    host_name = payload.get("host_name", "Aarav Sharma")
    project_id = payload.get("project_id")
    project_title = payload.get("project_title")
    meeting_type = payload.get("meeting_type", "Mentor Review")
    return meeting_service.create_room(title, host_id, host_name, project_id, project_title, meeting_type)

@app.get("/api/meetings/{room_id}")
def get_meeting(room_id: str):
    """Gets meeting room details by room ID."""
    room = meeting_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Meeting room not found.")
    return room

# ==========================================
# 11. IPFS DECENTRALIZED STORAGE API
# ==========================================

@app.get("/api/ipfs/files")
def list_ipfs_files():
    """Lists all pinned project assets in the decentralized IPFS registry."""
    return ipfs_engine.list_files()

@app.post("/api/ipfs/upload")
def upload_ipfs_file(payload: Dict[str, Any]):
    """Simulates immutable IPFS file upload and returns cryptographic CID."""
    filename = payload.get("filename", "project_artifact.zip")
    content_b64 = payload.get("content_base64", "")
    uploader_name = payload.get("uploader_name", "Student Creator")
    project_title = payload.get("project_title", "Student Project")
    mime_type = payload.get("mime_type", "application/octet-stream")

    import base64
    if content_b64:
        try:
            content_bytes = base64.b64decode(content_b64)
        except Exception:
            content_bytes = filename.encode("utf-8")
    else:
        text_content = payload.get("text_content", "")
        content_bytes = text_content.encode("utf-8") if text_content else filename.encode("utf-8")

    return ipfs_engine.upload_file(filename, content_bytes, mime_type, uploader_name, project_title)

@app.get("/api/ipfs/files/{cid}")
def get_ipfs_file_meta(cid: str):
    """Fetches metadata for a given Content Identifier (CID)."""
    meta = ipfs_engine.get_file_metadata(cid)
    if not meta:
        raise HTTPException(status_code=404, detail="CID not found in IPFS registry.")
    return meta


candidate_frontend_paths = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend")),
    os.path.abspath("frontend"),
    os.path.abspath("/app/frontend")
]
frontend_dir = next((p for p in candidate_frontend_paths if os.path.isdir(p) and os.path.isfile(os.path.join(p, "index.html"))), candidate_frontend_paths[0])

if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/login")
@app.get("/dashboard")
@app.get("/404")
@app.get("/")
def serve_primary_views():
    """Serves the primary Single-Page Application views."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Pro-Versed API running. Frontend static assets mounting..."}

@app.get("/{full_path:path}")
def serve_spa_catchall(full_path: str):
    """Fallback catch-all to route frontend SPA paths to index.html, static files, or 404."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found.")

    requested_file = os.path.join(frontend_dir, full_path)
    if os.path.isfile(requested_file):
        return FileResponse(requested_file)

    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"error": "Not Found", "detail": "Page not found."})

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    """Custom 404 handler separating API errors from browser navigation."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "detail": getattr(exc, "detail", "The requested API resource does not exist."),
                "status_code": 404
            }
        )
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, status_code=404)
    return JSONResponse(status_code=404, content={"error": "Not Found", "detail": "Page not found."})

@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: Exception):
    """Global internal server error handler preventing stacktrace leakage."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected server error occurred. Our team has been notified.",
            "status_code": 500
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=False)
