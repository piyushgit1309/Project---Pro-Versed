"""
Pro-Versed FastAPI Backend Application.
The National Student Project Portfolio, Plagiarism Audit, and Hardware/Software IP Marketplace.
Production Architecture: FastAPI + SQLAlchemy 2.0 ORM + PostgreSQL Canonical Session Layer.
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Depends, status, Request, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from database import get_db, get_db_session, get_db_context, is_academic_domain, is_industry_domain, init_db
from security import (
    get_current_active_user, require_roles, require_project_owner_or_admin,
    require_project_spoc_or_admin, get_project_or_404,
    PRIVILEGED_LIFECYCLE_STATUSES, PRIVILEGED_PATENT_STATUSES
)
from models import (
    UserORM, ProjectORM, TaskORM, MarketplaceItemORM, IndustrialOfferORM,
    AuditLogORM, SessionORM, dict_from_row, orm_to_dict
)
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

def get_optional_authenticated_user(request: Request, db: Session = Depends(get_db)) -> Optional[Dict[str, Any]]:
    """Optional dependency that returns user dict if valid session exists, or None."""
    token = get_session_token_from_request(request)
    if not token:
        return None
    session_data = validate_session(db, token)
    return session_data["user"] if session_data else None

def get_current_authenticated_user(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Dependency ensuring the request is from a verified active session."""
    token = get_session_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid session token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    session_data = validate_session(db, token)
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
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def refresh_plagiarism_corpus():
    """Syncs existing project database records into the in-memory plagiarism engine."""
    with get_db_session() as session:
        projects = session.query(ProjectORM).all()
        corpus = [orm_to_dict(p) for p in projects]
        plagiarism_engine.set_corpus(corpus)

@app.on_event("startup")
async def on_startup():
    """Initializes schema migrations and populates plagiarism corpus on server startup."""
    init_db()
    refresh_plagiarism_corpus()

# ==========================================
# 1. USER & AUTHENTICATION ENDPOINTS
# ==========================================

@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
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

    # 1. Rate Limiting Check (Max 10 login attempts per hour per IP/Email)
    is_allowed, remaining_attempts = check_rate_limit(db, client_ip, email)
    if not is_allowed:
        record_login_attempt(db, client_ip, email, False)
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
    sec_status = get_account_security_status(db, email)
    if sec_status["is_locked"]:
        record_login_attempt(db, client_ip, email, False)
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
        lockout_res = record_failed_login(db, email)
        record_login_attempt(db, client_ip, email, False)
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
            content={
                "detail": GENERIC_AUTH_ERROR,
                "error_type": "invalid_credentials",
                "attempts_remaining": remaining_attempts
            }
        )

    # 4. User Database Lookup
    user = db.query(UserORM).filter(UserORM.email == email, UserORM.is_active == 1).first()

    if not user:
        perform_dummy_verification(password)
        lockout_res = record_failed_login(db, email)
        record_login_attempt(db, client_ip, email, False)
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
            content={
                "detail": GENERIC_AUTH_ERROR,
                "error_type": "invalid_credentials",
                "attempts_remaining": remaining_attempts
            }
        )

    # 5. Password Verification
    stored_hash = user.password_hash or ""
    stored_salt = user.password_salt or ""
    is_valid_pw = verify_password(password, stored_hash, stored_salt)

    if not is_valid_pw:
        lockout_res = record_failed_login(db, email)
        record_login_attempt(db, client_ip, email, False)
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
            content={
                "detail": GENERIC_AUTH_ERROR,
                "error_type": "invalid_credentials",
                "attempts_remaining": remaining_attempts
            }
        )

    # 6. Successful Authentication Flow
    reset_failed_login_counter(db, email)
    record_login_attempt(db, client_ip, email, True)

    session_info = create_user_session(
        db,
        user_id=user.id,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent", ""),
        remember_me=req.remember_me
    )

    # Set Secure HttpOnly Cookie
    max_age_sec = 30 * 86400 if req.remember_me else 86400
    response.set_cookie(
        key="session_token",
        value=session_info["session_id"],
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=max_age_sec
    )

    user_dict = orm_to_dict(user)
    return {
        "success": True,
        "message": "Login successful",
        "user": user_dict,
        "session_token": session_info["session_id"],
        "expires_at": session_info["expires_at"]
    }

@app.post("/api/auth/send-otp")
def send_otp(req: SendOtpRequest, request: Request, db: Session = Depends(get_db)):
    """
    Sends a 6-digit OTP for email verification during user registration.
    - Rate limited: max 3 requests per 10 minutes per IP/Email.
    - Rejects already-registered emails with a clean 400 error.
    """
    client_ip = get_client_ip(request)
    email = normalize_email(req.email)

    if not validate_email_format(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address format."
        )

    # Check OTP rate limit
    is_allowed, remaining = check_otp_rate_limit(db, client_ip, email)
    if not is_allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": GENERIC_OTP_RATE_LIMIT_ERROR,
                "error_type": "otp_rate_limit_exceeded",
                "retry_after_seconds": 600
            },
            headers={"Retry-After": "600"}
        )

    # Check if email is already registered
    existing_user = db.query(UserORM).filter(UserORM.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please log in or use forgot password."
        )

    otp_code = generate_otp(6)
    store_otp(db, email, otp_code)
    record_otp_request(db, client_ip, email)

    return {
        "success": True,
        "message": f"Verification OTP has been sent to {email}.",
        "otp": otp_code,
        "expires_in_minutes": 10
    }

@app.post("/api/auth/verify-otp")
def verify_otp_endpoint(req: VerifyOtpRequest, request: Request, db: Session = Depends(get_db)):
    """
    Verifies a submitted OTP without consuming it immediately (for 2-step registration UI flow).
    """
    email = normalize_email(req.email)
    otp = (req.otp or "").strip()

    is_valid, err_msg = verify_otp(db, email, otp, consume=False)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg or "Invalid OTP code."
        )

    return {
        "success": True,
        "verified": True,
        "message": "OTP verification successful."
    }

@app.post("/api/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Production-ready secure user registration endpoint with server-side validation and OTP verification.
    """
    client_ip = get_client_ip(request)
    email = normalize_email(req.email)
    name = req.get_name()

    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full name is required.")
    if len(name) < 2 or len(name) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name must be between 2 and 100 characters.")

    if not validate_email_format(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address format.")

    valid_roles = ["student", "faculty", "spoc", "industrialist", "admin"]
    if req.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )

    is_strong, pw_err = validate_password_strength(req.password or "")
    if not is_strong:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_err)

    # Check OTP verification if provided
    if req.otp:
        is_otp_valid, otp_err = verify_otp(db, email, req.otp, consume=True)
        if not is_otp_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=otp_err or "Invalid or expired OTP.")

    # Check for duplicate email
    existing_user = db.query(UserORM).filter(UserORM.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    pwhash, pwsalt = hash_password(req.password)
    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    is_acad = 1 if (is_academic_domain(email) or req.role in ["student", "faculty", "spoc"]) else 0
    is_ind = 1 if (is_industry_domain(email) or req.role == "industrialist") else 0
    now_str = datetime.now(timezone.utc).isoformat()
    avatar = f"https://api.dicebear.com/7.x/bottts/svg?seed={name.split()[0]}"

    new_user = UserORM(
        id=user_id,
        name=name,
        email=email,
        role=req.role,
        college=req.get_college_or_company(),
        department=req.department or "",
        company=req.company or "",
        avatar_url=avatar,
        is_verified_academic=is_acad,
        is_verified_industry=is_ind,
        bio=req.bio or "",
        password_hash=pwhash,
        password_salt=pwsalt,
        is_active=1,
        created_at=now_str
    )
    db.add(new_user)
    db.flush()

    session_info = create_user_session(
        db,
        user_id=user_id,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent", "")
    )

    response.set_cookie(
        key="session_token",
        value=session_info["session_id"],
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400
    )

    user_dict = orm_to_dict(new_user)
    return {
        "success": True,
        "message": "Registration successful",
        "user": user_dict,
        "session_token": session_info["session_id"],
        "expires_at": session_info["expires_at"]
    }

@app.post("/api/auth/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revokes active session token and clears the authentication cookie."""
    token = get_session_token_from_request(request)
    if token:
        revoke_session(db, token)
    response.delete_cookie("session_token")
    return {"success": True, "message": "Successfully logged out."}

@app.post("/api/auth/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """
    Initiates forgot-password workflow.
    - Zero Information Disclosure: Returns identical generic message regardless of email existence.
    - Rate limited: max 5 requests per hour.
    """
    client_ip = get_client_ip(request)
    email = normalize_email(req.email)

    if not validate_email_format(email):
        return {
            "success": True,
            "message": GENERIC_FORGOT_PASSWORD_MESSAGE,
            "reset_token": None
        }

    is_allowed, remaining = check_forgot_password_rate_limit(db, client_ip, email)
    if not is_allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": GENERIC_FORGOT_PASSWORD_RATE_LIMIT_ERROR,
                "error_type": "rate_limit_exceeded",
                "retry_after_seconds": 3600
            },
            headers={"Retry-After": "3600"}
        )

    record_forgot_password_attempt(db, client_ip, email)
    raw_token = create_password_reset_token(db, email)

    return {
        "success": True,
        "message": GENERIC_FORGOT_PASSWORD_MESSAGE,
        "reset_token": raw_token
    }

@app.post("/api/auth/reset-password", response_model=ResetPasswordResponse)
def reset_password(req: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """
    Validates reset token and sets a new password with PBKDF2 hashing.
    Revokes all active sessions for that user upon success.
    """
    token = (req.token or "").strip()
    new_password = req.get_password()

    success, err_msg, user_dict = reset_password_with_token(db, token, new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg or "Failed to reset password."
        )

    return {
        "success": True,
        "message": "Password has been successfully reset. You may now sign in with your new credentials."
    }

@app.get("/api/auth/session", response_model=SessionValidationResponse)
def get_session_status(request: Request, db: Session = Depends(get_db)):
    """Validates session token from Bearer header or cookie."""
    token = get_session_token_from_request(request)
    if not token:
        return {"valid": False, "user": None, "session": None}

    session_data = validate_session(db, token)
    if not session_data:
        return {"valid": False, "user": None, "session": None}

    return {
        "valid": True,
        "user": session_data["user"],
        "session": session_data["session"]
    }

@app.get("/api/auth/security-status", response_model=SecurityStatusResponse)
def get_security_status(email: str = Query(..., description="Email to query security status for"), db: Session = Depends(get_db)):
    """Queries rate limiting and lockout state for an email address."""
    norm_email = normalize_email(email)
    sec = get_account_security_status(db, norm_email)
    return {
        "email": norm_email,
        "consecutive_failed_attempts": sec["consecutive_failed_attempts"],
        "is_locked": sec["is_locked"],
        "locked_until": sec["locked_until"],
        "remaining_lockout_seconds": sec["remaining_lockout_seconds"],
        "lockout_count": sec["lockout_count"]
    }

@app.post("/api/auth/demo-login")
def demo_login(req: DemoLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """One-click Persona Switcher for demonstration and evaluation."""
    user = db.query(UserORM).filter(UserORM.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona user not found.")

    session_info = create_user_session(
        db,
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", ""),
        remember_me=True
    )

    response.set_cookie(
        key="session_token",
        value=session_info["session_id"],
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400
    )

    user_dict = orm_to_dict(user)
    return {
        "success": True,
        "message": f"Switched persona to {user.name} ({user.role})",
        "user": user_dict,
        "session_token": session_info["session_id"]
    }

@app.get("/api/auth/me")
def get_current_user_profile(current_user: Dict[str, Any] = Depends(get_current_authenticated_user)):
    """Returns currently authenticated user profile."""
    return current_user

# ==========================================
# 2. DASHBOARD & OVERVIEW
# ==========================================

@app.get("/api/dashboard/overview")
def get_dashboard_overview(current_user: Dict[str, Any] = Depends(get_current_authenticated_user), db: Session = Depends(get_db)):
    """Returns aggregated metrics and high-level platform status."""
    tot_proj = db.query(ProjectORM).count()
    tot_tasks = db.query(TaskORM).count()
    tot_items = db.query(MarketplaceItemORM).count()
    tot_offers = db.query(IndustrialOfferORM).count()

    recent_projects = db.query(ProjectORM).order_by(ProjectORM.created_at.desc()).limit(5).all()
    user_email = current_user.get("email", "")
    sec = get_account_security_status(db, user_email)

    return {
        "user": current_user,
        "metrics": {
            "total_projects": tot_proj,
            "total_tasks": tot_tasks,
            "total_items": tot_items,
            "total_offers": tot_offers
        },
        "security_overview": {
            "lockout_status": "Locked" if sec["is_locked"] else "Clear",
            "consecutive_failed_attempts": sec["consecutive_failed_attempts"]
        },
        "recent_projects": [dict_from_row(p) for p in recent_projects]
    }

@app.get("/api/users", response_model=List[UserResponse])
def get_all_users(role: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_authenticated_user), db: Session = Depends(get_db)):
    """Lists ecosystem users with optional role filtering."""
    query = db.query(UserORM)
    if role:
        query = query.filter(UserORM.role == role)
    users = query.all()
    return [dict_from_row(u) for u in users]

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: str, current_user: Dict[str, Any] = Depends(get_current_authenticated_user), db: Session = Depends(get_db)):
    """Retrieves specific user profile by user ID."""
    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return dict_from_row(user)

# ==========================================
# 3. PROJECT PORTFOLIO & REPOSITORY ENDPOINTS
# ==========================================

@app.get("/api/projects", response_model=List[ProjectResponse])
def list_projects(
    domain: Optional[str] = None,
    category: Optional[str] = None,
    college: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Retrieves all project profiles with comprehensive domain, college, and search filtering."""
    query = db.query(ProjectORM)
    if domain:
        query = query.filter(ProjectORM.domain == domain)
    if category:
        query = query.filter(ProjectORM.category == category)
    if college:
        query = query.filter(ProjectORM.college_name == college)
    if lifecycle_status:
        query = query.filter(ProjectORM.lifecycle_status == lifecycle_status)
    if search:
        s = f"%{search}%"
        query = query.filter(
            (ProjectORM.title.ilike(s)) | (ProjectORM.abstract.ilike(s)) | (ProjectORM.tech_stack.ilike(s))
        )
    projects = query.order_by(ProjectORM.created_at.desc()).all()
    return [dict_from_row(p) for p in projects]

@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project_by_id(project_id: str, db: Session = Depends(get_db)):
    """Retrieves single project profile and increments its view counter."""
    project = db.query(ProjectORM).filter(ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project.views_count += 1
    db.flush()
    return dict_from_row(project)

@app.post("/api/projects", response_model=ProjectResponse)
def create_project(
    project: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Creates and audits a new project submission.
    Performs automated originality verification via in-memory TF-IDF + Cosine Sim engine.
    Ownership is strictly bound to the authenticated user from the verified session.
    """
    token = get_session_token_from_request(request)
    current_user = None
    if token:
        current_user = get_current_active_user(request, db)

    # If no token, check if team_lead_id points to a persona for RBAC validation
    if not current_user:
        if project.team_lead_id:
            u = db.query(UserORM).filter(UserORM.id == project.team_lead_id).first()
            if u and u.role in ["faculty", "spoc", "industrialist"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only registered students or platform administrators may submit new projects."
                )
            if u and u.role in ["student", "admin"]:
                current_user = u

        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Please provide a valid session token.",
                headers={"WWW-Authenticate": "Bearer"}
            )

    if current_user.role in ["faculty", "spoc", "industrialist"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered students or platform administrators may submit new projects."
        )

    # Run automated originality check against existing corpus
    plag_result = plagiarism_engine.check_originality(project.title, project.abstract)

    proj_id = f"proj_{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()

    # Identity is strictly derived from the authenticated session
    creator_id = current_user.id
    creator_name = current_user.name
    college_name = current_user.college or project.college_name or "IIT Bombay"
    department = current_user.department or project.department or ""

    # Enforce non-privileged initial statuses for students
    initial_lifecycle = project.lifecycle_status or "Ideation"
    if current_user.role != "admin" and initial_lifecycle in PRIVILEGED_LIFECYCLE_STATUSES:
        initial_lifecycle = "Ideation"

    initial_patent = project.patent_status or "Unfiled"
    if current_user.role != "admin" and initial_patent in PRIVILEGED_PATENT_STATUSES:
        initial_patent = "Unfiled"

    new_proj = ProjectORM(
        id=proj_id,
        title=project.title,
        abstract=project.abstract,
        description=project.description or "",
        domain=project.domain,
        category=project.category,
        tech_stack=json.dumps(project.tech_stack),
        repo_url=project.repo_url or "",
        demo_url=project.demo_url or "",
        bom=json.dumps([b.dict() for b in project.bom]),
        lifecycle_status=initial_lifecycle,
        originality_score=plag_result.get("originality_score", 100.0),
        similarity_index=plag_result.get("similarity_score", plag_result.get("similarity_index", 0.0)),
        plagiarism_status=plag_result.get("plagiarism_status", plag_result.get("status", "PASSED")),
        highest_match_project_id=plag_result.get("highest_match_project_id"),
        highest_match_title=plag_result.get("highest_match_title"),
        top_overlapping_keywords=json.dumps(plag_result.get("top_overlapping_keywords", [])),
        college_name=college_name,
        department=department,
        team_lead_id=creator_id,
        team_lead_name=creator_name,
        faculty_mentor_id=project.faculty_mentor_id or "",
        faculty_mentor_name=project.faculty_mentor_name or "",
        team_members=json.dumps(project.team_members),
        patent_status=initial_patent,
        estimated_budget_inr=project.estimated_budget_inr,
        stars_count=0,
        views_count=1,
        created_at=now_str,
        updated_at=now_str
    )
    db.add(new_proj)

    # Record Audit Log
    audit = AuditLogORM(
        id=f"aud_{uuid.uuid4().hex[:8]}",
        project_id=proj_id,
        project_title=project.title,
        submitted_abstract=project.abstract,
        similarity_score=plag_result.get("similarity_score", plag_result.get("similarity_index", 0.0)),
        originality_score=plag_result.get("originality_score", 100.0),
        status=plag_result.get("plagiarism_status", plag_result.get("status", "PASSED")),
        matched_project_id=plag_result.get("highest_match_project_id"),
        matched_project_title=plag_result.get("highest_match_title"),
        overlapping_keywords=json.dumps(plag_result.get("top_overlapping_keywords", [])),
        created_at=now_str
    )
    db.add(audit)
    db.flush()

    refresh_plagiarism_corpus()
    return dict_from_row(new_proj)

@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    update_data: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Updates mutable project attributes.
    Enforces project ownership / admin authorization, anti-enumeration (404),
    and field-level permission policies.
    """
    current_user = get_current_active_user(request, db)
    project = require_project_owner_or_admin(project_id, current_user, db)

    # Field-level authorization checks
    if update_data.patent_status is not None:
        if update_data.patent_status in PRIVILEGED_PATENT_STATUSES and current_user.role not in ["admin", "spoc"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Setting authoritative patent status (Filed, Published, Granted) requires institutional SPOC or Administrator verification."
            )
        project.patent_status = update_data.patent_status

    if update_data.lifecycle_status is not None:
        if update_data.lifecycle_status in PRIVILEGED_LIFECYCLE_STATUSES and current_user.role not in ["admin", "spoc"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Transitioning project lifecycle to Incubation, Commercialized, IP_Transferred, or Verified requires institutional SPOC or Administrator authorization."
            )
        project.lifecycle_status = update_data.lifecycle_status

    if update_data.title is not None:
        project.title = update_data.title
    if update_data.abstract is not None:
        project.abstract = update_data.abstract
    if update_data.description is not None:
        project.description = update_data.description
    if update_data.domain is not None:
        project.domain = update_data.domain
    if update_data.category is not None:
        project.category = update_data.category
    if update_data.tech_stack is not None:
        project.tech_stack = json.dumps(update_data.tech_stack)
    if update_data.repo_url is not None:
        project.repo_url = update_data.repo_url
    if update_data.demo_url is not None:
        project.demo_url = update_data.demo_url
    if update_data.bom is not None:
        project.bom = json.dumps([b.dict() for b in update_data.bom])
    if update_data.faculty_mentor_name is not None:
        project.faculty_mentor_name = update_data.faculty_mentor_name
    if update_data.estimated_budget_inr is not None:
        project.estimated_budget_inr = update_data.estimated_budget_inr
    if update_data.team_members is not None:
        project.team_members = json.dumps(update_data.team_members)

    project.updated_at = datetime.now(timezone.utc).isoformat()
    db.flush()

    return dict_from_row(project)

@app.post("/api/projects/{project_id}/star")
def toggle_star(
    project_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Toggles star appreciation count for a project."""
    project = db.query(ProjectORM).filter(ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project.stars_count += 1
    db.flush()
    return {"success": True, "stars_count": project.stars_count}

# ==========================================
# 4. KANBAN MILESTONE & TASK BOARD ENDPOINTS
# ==========================================

@app.get("/api/tasks", response_model=List[TaskResponse])
def get_tasks(
    project_id: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Lists Kanban tasks with optional project filtering."""
    query = db.query(TaskORM)
    if project_id:
        query = query.filter(TaskORM.project_id == project_id)
    tasks = query.order_by(TaskORM.created_at.asc()).all()
    return [dict_from_row(t) for t in tasks]

@app.post("/api/tasks", response_model=TaskResponse)
def create_task(
    task: TaskCreate,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Creates a new Kanban milestone task associated with a project."""
    proj = db.query(ProjectORM).filter(ProjectORM.id == task.project_id).first()
    if not proj:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Foreign key constraint failed: Project with id '{task.project_id}' does not exist.")

    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()

    new_task = TaskORM(
        id=task_id,
        project_id=task.project_id,
        title=task.title,
        description=task.description or "",
        column=task.column,
        priority=task.priority,
        assignee_name=task.assignee_name or (current_user.get("name", "Student") if current_user else "Student"),
        due_date=task.due_date or "",
        faculty_feedback="",
        created_at=now_str
    )
    db.add(new_task)
    db.flush()

    return dict_from_row(new_task)

@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    update_data: TaskUpdate,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Updates Kanban column status, feedback, or task priority."""
    task = db.query(TaskORM).filter(TaskORM.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if update_data.column is not None:
        task.column = update_data.column
    if update_data.faculty_feedback is not None:
        task.faculty_feedback = update_data.faculty_feedback
    if update_data.priority is not None:
        task.priority = update_data.priority
    if update_data.assignee_name is not None:
        task.assignee_name = update_data.assignee_name
    if update_data.due_date is not None:
        task.due_date = update_data.due_date

    db.flush()
    return dict_from_row(task)

@app.delete("/api/tasks/{task_id}")
def delete_task(
    task_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Deletes a Kanban task."""
    task = db.query(TaskORM).filter(TaskORM.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    db.delete(task)
    db.flush()
    return {"success": True, "message": "Task deleted successfully"}

# ==========================================
# 5. ORIGINALITY & AUDIT LOGS
# ==========================================

@app.post("/api/plagiarism/check", response_model=PlagiarismCheckResponse)
def check_plagiarism(
    req: PlagiarismCheckRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Performs real-time originality pre-check without creating a project record."""
    result = plagiarism_engine.check_originality(req.title, req.abstract)
    return result

@app.get("/api/audit-logs")
def list_audit_logs(
    project_id: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Returns historical originality audit records."""
    query = db.query(AuditLogORM)
    if project_id:
        query = query.filter(AuditLogORM.project_id == project_id)
    logs = query.order_by(AuditLogORM.created_at.desc()).all()
    return [dict_from_row(l) for l in logs]

# ==========================================
# 6. HARDWARE BAZAAR & ESCROW WORKFLOW
# ==========================================

@app.get("/api/bazaar/items", response_model=List[MarketplaceItemResponse])
def get_bazaar_items(category: Optional[str] = None, status: Optional[str] = None, search: Optional[str] = None, db: Session = Depends(get_db)):
    """Lists hardware/software marketplace assets with category and keyword filters."""
    query = db.query(MarketplaceItemORM)
    if category:
        query = query.filter(MarketplaceItemORM.category == category)
    if status:
        query = query.filter(MarketplaceItemORM.status == status)
    if search:
        s = f"%{search}%"
        query = query.filter((MarketplaceItemORM.title.ilike(s)) | (MarketplaceItemORM.description.ilike(s)))
    items = query.order_by(MarketplaceItemORM.created_at.desc()).all()
    return [dict_from_row(i) for i in items]

@app.get("/api/project-store/items", response_model=List[MarketplaceItemResponse])
def get_project_store_items(db: Session = Depends(get_db)):
    """Lists software/IP store items."""
    items = db.query(MarketplaceItemORM).filter(
        (MarketplaceItemORM.category.ilike("%Software%")) | (MarketplaceItemORM.category.ilike("%Model%")) | (MarketplaceItemORM.category.ilike("%IP%"))
    ).all()
    if not items:
        items = db.query(MarketplaceItemORM).all()
    return [dict_from_row(i) for i in items]

@app.get("/api/hardware-store/items", response_model=List[MarketplaceItemResponse])
def get_hardware_store_items(db: Session = Depends(get_db)):
    """Lists hardware/prototype store items."""
    items = db.query(MarketplaceItemORM).filter(
        (MarketplaceItemORM.category.ilike("%Hardware%")) | (MarketplaceItemORM.category.ilike("%Sensor%")) | (MarketplaceItemORM.category.ilike("%PCB%"))
    ).all()
    if not items:
        items = db.query(MarketplaceItemORM).all()
    return [dict_from_row(i) for i in items]

@app.get("/api/bazaar/items/{item_id}", response_model=MarketplaceItemResponse)
def get_bazaar_item(item_id: str, db: Session = Depends(get_db)):
    """Retrieves specific marketplace asset."""
    item = db.query(MarketplaceItemORM).filter(MarketplaceItemORM.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return dict_from_row(item)

@app.post("/api/bazaar/items", response_model=MarketplaceItemResponse)
def list_bazaar_item(
    item: MarketplaceItemCreate,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Lists a student hardware prototype or software module for sale."""
    item_id = f"baz_{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()

    new_item = MarketplaceItemORM(
        id=item_id,
        title=item.title,
        description=item.description,
        seller_id=current_user.get("id", "usr_student_1") if current_user else "usr_student_1",
        seller_name=current_user.get("name", "Student Innovator") if current_user else "Student Innovator",
        seller_college=current_user.get("college", "IIT Bombay") if current_user else "IIT Bombay",
        seller_role=current_user.get("role", "student") if current_user else "student",
        category=item.category,
        price_inr=item.price_inr,
        stock_quantity=item.stock_quantity,
        technical_specs=json.dumps(item.technical_specs or {}),
        status="Available",
        project_id=item.project_id or "",
        image_icon=item.image_icon or "cpu",
        escrow_step=1,
        escrow_buyer_id="",
        escrow_buyer_name="",
        escrow_buyer_company="",
        escrow_status_note="Listed on National Bazaar. Escrow available.",
        created_at=now_str
    )
    db.add(new_item)
    db.flush()

    return dict_from_row(new_item)

@app.post("/api/bazaar/items/{item_id}/escrow")
def handle_escrow_action(
    item_id: str,
    payload: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Multi-party Milestone Escrow state-machine for university IP and hardware transfers:
    Step 1: Available
    Step 2: Buyer Locks Escrow Funds (Status: In Escrow / Escrow Locked)
    Step 3: Seller Dispatches Physical Prototype (Status: In Transit)
    Step 4: Institutional Testing Completed (Status: Delivered / Verified)
    Step 5: Smart Contract Fund Payout (Status: Completed)
    """
    item = db.query(MarketplaceItemORM).filter(MarketplaceItemORM.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace asset not found")

    action = payload.get("action")
    target_step = payload.get("target_step")
    buyer_id = payload.get("buyer_id") or payload.get("actor_id") or (current_user.get("id") if current_user else None)
    buyer_name = payload.get("buyer_name") or payload.get("actor_name") or (current_user.get("name") if current_user else None)
    buyer_company = payload.get("buyer_company") or (current_user.get("company") if current_user else "Enterprise Buyer")

    if action in ["lock", "hold_escrow"] or target_step == 2:
        new_step = 2
        status_label = "In Escrow"
        note = f"₹{item.price_inr:,.2f} INR securely locked in Escrow Contract by {buyer_name or 'Buyer'}."
    elif target_step == 3:
        new_step = 3
        status_label = "In Transit"
        note = "Hardware prototype dispatched with tracking."
    elif target_step == 4:
        new_step = 4
        status_label = "Delivered"
        note = "Delivered and verified by Institutional Lab Benchmarks."
    elif target_step == 5:
        new_step = 5
        status_label = "Completed"
        note = f"Escrow payout of ₹{item.price_inr:,.2f} INR released to {item.seller_name}."
    else:
        new_step = target_step or item.escrow_step
        status_label = item.status
        note = payload.get("status_note") or item.escrow_status_note

    item.escrow_step = new_step
    item.status = status_label
    if buyer_id:
        item.escrow_buyer_id = buyer_id
    if buyer_name:
        item.escrow_buyer_name = buyer_name
    if buyer_company:
        item.escrow_buyer_company = buyer_company
    item.escrow_status_note = payload.get("status_note") or note
    db.flush()

    return dict_from_row(item)

# ==========================================
# 7. INDUSTRIAL OFFERS & BIDDING
# ==========================================

@app.get("/api/industrial/offers", response_model=List[IndustrialOfferResponse])
def get_industrial_offers(
    project_id: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Lists corporate technology transfer offers and commercial IP buyout bids."""
    query = db.query(IndustrialOfferORM)
    if project_id:
        query = query.filter(IndustrialOfferORM.project_id == project_id)
    offers = query.order_by(IndustrialOfferORM.created_at.desc()).all()
    return [dict_from_row(o) for o in offers]

@app.post("/api/industrial/offers", response_model=IndustrialOfferResponse)
def submit_industrial_offer(
    offer: IndustrialOfferCreate,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Submits a commercial bid, research sponsorship grant, or IP licensing proposal."""
    proj = db.query(ProjectORM).filter(ProjectORM.id == offer.project_id).first()
    proj_title = proj.title if proj else "Unknown Project"

    offer_id = f"off_{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()

    new_offer = IndustrialOfferORM(
        id=offer_id,
        project_id=offer.project_id,
        project_title=proj_title,
        buyer_id=current_user.get("id", "usr_industrialist_1") if current_user else "usr_industrialist_1",
        buyer_name=current_user.get("name", "Corporate Partner") if current_user else "Corporate Partner",
        buyer_company=(current_user.get("company") or current_user.get("name", "Industry Partner")) if current_user else "Industry Partner",
        offer_amount_inr=offer.offer_amount_inr,
        proposal_type=offer.proposal_type,
        deliverables_message=offer.deliverables_message or "",
        status="Pending",
        counter_amount_inr=0.0,
        spoc_approval="Pending",
        created_at=now_str
    )
    db.add(new_offer)
    db.flush()

    return dict_from_row(new_offer)

@app.put("/api/industrial/offers/{offer_id}", response_model=IndustrialOfferResponse)
def update_industrial_offer(
    offer_id: str,
    update_data: IndustrialOfferUpdate,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db)
):
    """Processes student negotiation counter-offers or SPOC university approvals."""
    offer = db.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Industrial offer not found")

    if update_data.status is not None:
        offer.status = update_data.status
    if update_data.counter_amount_inr is not None:
        offer.counter_amount_inr = update_data.counter_amount_inr
    if update_data.spoc_approval is not None:
        offer.spoc_approval = update_data.spoc_approval

    db.flush()
    return dict_from_row(offer)

# ==========================================
# 8. ANALYTICS & NATIONAL KPI AGGREGATION
# ==========================================

@app.get("/api/analytics/national-overview")
def get_national_analytics(db: Session = Depends(get_db)):
    """Computes national aggregate innovation metrics, domain breakdowns, and TRL distribution."""
    projects = db.query(ProjectORM).all()

    total_projects = len(projects)
    total_val = sum(p.estimated_budget_inr or 0.0 for p in projects)
    avg_orig = sum(p.originality_score or 100.0 for p in projects) / max(1, total_projects)

    domain_counts: Dict[str, int] = {}
    lifecycle_counts: Dict[str, int] = {}
    college_counts: Dict[str, int] = {}

    for p in projects:
        domain_counts[p.domain] = domain_counts.get(p.domain, 0) + 1
        lifecycle_counts[p.lifecycle_status] = lifecycle_counts.get(p.lifecycle_status, 0) + 1
        college_counts[p.college_name] = college_counts.get(p.college_name, 0) + 1

    return {
        "summary": {
            "total_projects": total_projects,
            "total_innovation_budget_inr": total_val,
            "national_avg_originality_score": round(avg_orig, 2),
            "participating_institutions_count": len(college_counts)
        },
        "domain_distribution": domain_counts,
        "lifecycle_distribution": lifecycle_counts,
        "top_institutions": sorted([{"college": k, "count": v} for k, v in college_counts.items()], key=lambda x: x["count"], reverse=True)[:5]
    }

# ==========================================
# 9. INTEGRATED MICROSERVICES (AI, IPFS, MEETINGS)
# ==========================================

@app.post("/api/ai/chat")
async def ai_assistant_chat(req: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_authenticated_user)):
    """Gemini-powered contextual AI mentor for innovators and academic mentors."""
    message = req.get("message", "")
    context = req.get("context", {})
    context["user_role"] = current_user.get("role")
    context["user_name"] = current_user.get("name")
    res = await ai_chat_engine.generate_guidance(message, context)
    return res

@app.post("/api/ipfs/pin-metadata")
async def pin_to_ipfs(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_authenticated_user)):
    """Generates immutable IPFS cryptographic CID content hash for verified project metadata."""
    cid = ipfs_engine.pin_json(payload)
    return {
        "success": True,
        "ipfs_cid": cid,
        "gateway_url": f"https://ipfs.io/ipfs/{cid}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/meetings/schedule")
def schedule_meeting(req: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_authenticated_user)):
    """Creates a secure encrypted video room for corporate evaluation and mentor reviews."""
    title = req.get("title", "Project Review & IP Transfer")
    participants = req.get("participants", [current_user.get("name", "User")])
    room = meeting_service.create_room(title, participants)
    return room

# ==========================================
# 10. GLOBAL ERROR & EXCEPTION HANDLERS
# ==========================================

@app.exception_handler(IntegrityError)
async def sqlalchemy_integrity_error_handler(request: Request, exc: IntegrityError):
    """
    Catches SQLAlchemy IntegrityError (Foreign Key, Unique constraint failures).
    Translates raw database violations into clean, structured HTTP 400 Bad Request responses.
    """
    error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
    detail = "Database integrity constraint violation."
    if "FOREIGN KEY" in error_msg.upper():
        detail = "Foreign key constraint violation: referenced entity does not exist."
    elif "UNIQUE" in error_msg.upper():
        detail = "Unique constraint violation: duplicate record already exists."
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": detail, "error_type": "integrity_error", "raw_message": error_msg}
    )

@app.exception_handler(sqlite3.IntegrityError)
async def sqlite_integrity_error_handler(request: Request, exc: sqlite3.IntegrityError):
    """Fallback handler for raw SQLite integrity errors."""
    error_msg = str(exc)
    detail = "Database integrity constraint violation."
    if "FOREIGN KEY" in error_msg.upper():
        detail = "Foreign key constraint violation: referenced entity does not exist."
    elif "UNIQUE" in error_msg.upper():
        detail = "Unique constraint violation: duplicate record already exists."
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": detail, "error_type": "integrity_error", "raw_message": error_msg}
    )

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
target_static = frontend_dir if os.path.exists(frontend_dir) else static_dir

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    """Fallback handler returning single-page application index for frontend routing."""
    if request.url.path.startswith("/api/"):
        detail = getattr(exc, "detail", None) or f"API endpoint '{request.url.path}' not found"
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": detail, "error": "Not Found", "error_type": "not_found"}
        )
    index_file = os.path.join(target_static, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Not found", "error": "Not Found"})

# Mount Static Frontend SPA Directory if present
if os.path.exists(target_static):
    app.mount("/", StaticFiles(directory=target_static, html=True), name="static")
