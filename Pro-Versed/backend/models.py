"""
SQLAlchemy 2.0 ORM Models and Data Mapping Entities for PRO-VERSED.
Canonical PostgreSQL Schema with support for SQLite in testing.
"""

import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Text, Boolean, ForeignKey, Index

class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    college: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_verified_academic: Mapped[int] = mapped_column(Integer, default=0)
    is_verified_industry: Mapped[int] = mapped_column(Integer, default=0)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_salt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reset_password_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reset_password_expires: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)

    sessions: Mapped[List["SessionORM"]] = relationship("SessionORM", back_populates="user", cascade="all, delete-orphan")


class SessionORM(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(64), nullable=False)
    last_activity: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["UserORM"] = relationship("UserORM", back_populates="sessions")


class LoginAttemptORM(Base):
    __tablename__ = "login_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_success: Mapped[int] = mapped_column(Integer, nullable=False)


class PasswordResetAttemptORM(Base):
    __tablename__ = "password_reset_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class OtpVerificationORM(Base):
    __tablename__ = "otp_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class OtpRequestORM(Base):
    __tablename__ = "otp_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class AccountSecurityORM(Base):
    __tablename__ = "account_security"

    email: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    consecutive_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_failed_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lockout_count: Mapped[int] = mapped_column(Integer, default=0)


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tech_stack: Mapped[str] = mapped_column(Text, nullable=False)
    repo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    demo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    bom: Mapped[str] = mapped_column(Text, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    originality_score: Mapped[float] = mapped_column(Float, default=100.0)
    similarity_index: Mapped[float] = mapped_column(Float, default=0.0)
    plagiarism_status: Mapped[str] = mapped_column(String(50), default="PASSED")
    highest_match_project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    highest_match_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    top_overlapping_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    college_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    team_lead_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    team_lead_name: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty_mentor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    faculty_mentor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    team_members: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    patent_status: Mapped[str] = mapped_column(String(50), default="None")
    estimated_budget_inr: Mapped[float] = mapped_column(Float, default=0.0)
    stars_count: Mapped[int] = mapped_column(Integer, default=0)
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    tasks: Mapped[List["TaskORM"]] = relationship("TaskORM", back_populates="project", cascade="all, delete-orphan")


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    column: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    assignee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    faculty_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)

    project: Mapped["ProjectORM"] = relationship("ProjectORM", back_populates="tasks")


class MarketplaceItemORM(Base):
    __tablename__ = "marketplace_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    seller_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    seller_name: Mapped[str] = mapped_column(String(255), nullable=False)
    seller_college: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seller_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    price_inr: Mapped[float] = mapped_column(Float, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=1)
    technical_specs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Available", index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    image_icon: Mapped[str] = mapped_column(String(100), default="cpu")
    escrow_step: Mapped[int] = mapped_column(Integer, default=1)
    escrow_buyer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    escrow_buyer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    escrow_buyer_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    escrow_status_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class IndustrialOfferORM(Base):
    __tablename__ = "industrial_offers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_title: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    buyer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_company: Mapped[str] = mapped_column(String(255), nullable=False)
    offer_amount_inr: Mapped[float] = mapped_column(Float, nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    deliverables_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Pending", index=True)
    counter_amount_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spoc_approval: Mapped[str] = mapped_column(String(50), default="Pending")
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditLogORM(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    project_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    submitted_abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    originality_score: Mapped[float] = mapped_column(Float, default=100.0)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    matched_project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    matched_project_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    overlapping_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


def orm_to_dict(obj: Any) -> Dict[str, Any]:
    """Converts a SQLAlchemy ORM entity into a dictionary with parsed JSON fields."""
    if obj is None:
        return {}
    d = {}
    for col in obj.__table__.columns:
        d[col.name] = getattr(obj, col.name)

    json_fields = ["tech_stack", "bom", "team_members", "top_overlapping_keywords", "technical_specs", "overlapping_keywords"]
    for f in json_fields:
        if f in d and isinstance(d[f], str):
            try:
                d[f] = json.loads(d[f])
            except Exception:
                pass
    return d


def dict_from_row(row) -> Dict[str, Any]:
    """Converts an ORM entity or row dictionary into a clean dict with parsed JSON fields."""
    if row is None:
        return {}
    if hasattr(row, "__table__"):
        return orm_to_dict(row)
    d = dict(row)
    json_fields = ["tech_stack", "bom", "team_members", "top_overlapping_keywords", "technical_specs", "overlapping_keywords"]
    for f in json_fields:
        if f in d and isinstance(d[f], str):
            try:
                d[f] = json.loads(d[f])
            except Exception:
                pass
    return d
