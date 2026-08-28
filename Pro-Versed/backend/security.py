"""
PRO-VERSED — Centralized Reusable Security & Authorization Layer
Provides session authentication, role-based access control, resource ownership checks,
and anti-enumeration protection.
"""

from typing import Dict, Any, Optional, List, Set
from fastapi import Request, HTTPException, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from models import UserORM, ProjectORM, IndustrialOfferORM
from auth import validate_session


PRIVILEGED_LIFECYCLE_STATUSES: Set[str] = {
    "Incubation", "Commercialized", "IP_Transferred", "Verified"
}

PRIVILEGED_PATENT_STATUSES: Set[str] = {
    "Filed", "Published", "Granted"
}

MINIMUM_OFFER_AMOUNT_INR: float = 1000.0
LEGAL_OFFER_STATUSES: Set[str] = {"Pending", "Countered", "Accepted", "Rejected", "Withdrawn"}
LEGAL_SPOC_APPROVAL_STATUSES: Set[str] = {"Pending", "Approved", "Denied"}


def get_session_token_from_request(request: Request) -> Optional[str]:
    """Extracts session token from Authorization Bearer header or HttpOnly cookie."""
    if not request:
        return None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        return cookie_token.strip()
    return None


def get_current_active_user(
    request: Request,
    db: Session = Depends(get_db)
) -> UserORM:
    """
    Guarantees caller has a valid, active session and returns the UserORM entity.
    Raises HTTP 401 Unauthorized if token is missing, invalid, expired, or user is inactive.
    """
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
            detail="Session is invalid or has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(UserORM).filter(
        UserORM.id == session_data["user"]["id"],
        UserORM.is_active == 1
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


def require_roles(*roles: str):
    """
    Dependency factory enforcing that the authenticated user possesses one of the allowed roles.
    Platform Administrators ('admin') are automatically permitted (universal override).
    """
    def role_checker(current_user: UserORM = Depends(get_current_active_user)) -> UserORM:
        if current_user.role == "admin":
            return current_user
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(roles)}."
            )
        return current_user
    return role_checker


def get_project_or_404(project_id: str, db: Session) -> ProjectORM:
    """Retrieves a ProjectORM record by ID or raises HTTP 404."""
    project = db.query(ProjectORM).filter(ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


def require_project_owner_or_admin(
    project_id: str,
    current_user: UserORM = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> ProjectORM:
    """
    Enforces project ownership for mutation operations:
    - If project does not exist -> 404
    - If caller is 'admin' -> Authorized
    - If caller is the registered team_lead_id -> Authorized
    - If caller is another authenticated user (wrong owner) -> 404 (Anti-enumeration policy)
    """
    project = db.query(ProjectORM).filter(ProjectORM.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if current_user.role == "admin":
        return project

    if project.team_lead_id != current_user.id:
        # Anti-enumeration policy: Return 404 for unauthorized authenticated users
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project


def require_project_spoc_or_admin(
    project_id: str,
    current_user: UserORM = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> ProjectORM:
    """
    Enforces institutional authority (SPOC of the project's college or Platform Admin).
    """
    project = get_project_or_404(project_id, db)

    if current_user.role == "admin":
        return project

    if current_user.role == "spoc":
        if current_user.college and project.college_name:
            if current_user.college.strip().lower() == project.college_name.strip().lower():
                return project

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the Campus SPOC for this institution or a Platform Administrator may perform this action."
    )


def get_offer_or_404(offer_id: str, db: Session) -> IndustrialOfferORM:
    """Retrieves an IndustrialOfferORM record by ID or raises HTTP 404."""
    offer = db.query(IndustrialOfferORM).filter(IndustrialOfferORM.id == offer_id).first()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Industrial offer not found"
        )
    return offer
