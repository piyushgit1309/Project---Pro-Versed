"""
SQLAlchemy Models and Data Mapping Entities for Pro-Versed.
Provides Declarative ORM mappings for PostgreSQL/SQLite and helper serializers.
"""

import json
from typing import Dict, Any, List, Optional

# Declarative SQLAlchemy definitions (for standard SQLAlchemy / PostgreSQL deployment)
try:
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import Column, String, Integer, Float, Text, Boolean, ForeignKey
    Base = declarative_base()

    class UserORM(Base):
        __tablename__ = "users"
        id = Column(String, primary_key=True, index=True)
        name = Column(String, nullable=False)
        email = Column(String, unique=True, nullable=False, index=True)
        role = Column(String, nullable=False)
        college = Column(String, nullable=True)
        department = Column(String, nullable=True)
        company = Column(String, nullable=True)
        avatar_url = Column(String, nullable=True)
        is_verified_academic = Column(Integer, default=0)
        is_verified_industry = Column(Integer, default=0)
        bio = Column(Text, nullable=True)
        password_hash = Column(String, nullable=True)
        password_salt = Column(String, nullable=True)
        reset_password_token = Column(String, nullable=True)
        reset_password_expires = Column(String, nullable=True)
        is_active = Column(Integer, default=1)
        created_at = Column(String, nullable=False)

    class OtpVerificationORM(Base):
        __tablename__ = "otp_verifications"
        id = Column(Integer, primary_key=True, index=True, autoincrement=True)
        email = Column(String, nullable=False, index=True)
        otp_hash = Column(String, nullable=False)
        expires_at = Column(String, nullable=False)
        attempts = Column(Integer, default=0)
        created_at = Column(String, nullable=False)

    class ProjectORM(Base):
        __tablename__ = "projects"
        id = Column(String, primary_key=True, index=True)
        title = Column(String, nullable=False, index=True)
        abstract = Column(Text, nullable=False)
        description = Column(Text, nullable=True)
        domain = Column(String, nullable=False, index=True)
        category = Column(String, nullable=False)
        tech_stack = Column(Text, nullable=False)
        repo_url = Column(String, nullable=True)
        demo_url = Column(String, nullable=True)
        bom = Column(Text, nullable=False)
        lifecycle_status = Column(String, nullable=False, index=True)
        originality_score = Column(Float, default=100.0)
        similarity_index = Column(Float, default=0.0)
        plagiarism_status = Column(String, default="PASSED")
        highest_match_project_id = Column(String, nullable=True)
        highest_match_title = Column(String, nullable=True)
        top_overlapping_keywords = Column(Text, nullable=True)
        college_name = Column(String, nullable=False, index=True)
        department = Column(String, nullable=True)
        team_lead_id = Column(String, nullable=False)
        team_lead_name = Column(String, nullable=False)
        faculty_mentor_id = Column(String, nullable=True)
        faculty_mentor_name = Column(String, nullable=True)
        team_members = Column(Text, nullable=True)
        patent_status = Column(String, default="None")
        estimated_budget_inr = Column(Float, default=0.0)
        stars_count = Column(Integer, default=0)
        views_count = Column(Integer, default=0)
        created_at = Column(String, nullable=False)
        updated_at = Column(String, nullable=False)

    class TaskORM(Base):
        __tablename__ = "tasks"
        id = Column(String, primary_key=True, index=True)
        project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
        title = Column(String, nullable=False)
        description = Column(Text, nullable=True)
        column = Column(String, nullable=False, index=True)
        priority = Column(String, nullable=False)
        assignee_name = Column(String, nullable=True)
        due_date = Column(String, nullable=True)
        faculty_feedback = Column(Text, nullable=True)
        created_at = Column(String, nullable=False)

    class MarketplaceItemORM(Base):
        __tablename__ = "marketplace_items"
        id = Column(String, primary_key=True, index=True)
        title = Column(String, nullable=False)
        description = Column(Text, nullable=False)
        seller_id = Column(String, nullable=False)
        seller_name = Column(String, nullable=False)
        seller_college = Column(String, nullable=True)
        seller_role = Column(String, nullable=True)
        category = Column(String, nullable=False, index=True)
        price_inr = Column(Float, nullable=False)
        stock_quantity = Column(Integer, default=1)
        technical_specs = Column(Text, nullable=True)
        status = Column(String, default="Available", index=True)
        project_id = Column(String, nullable=True)
        image_icon = Column(String, default="cpu")
        escrow_step = Column(Integer, default=1)
        escrow_buyer_id = Column(String, nullable=True)
        escrow_buyer_name = Column(String, nullable=True)
        escrow_buyer_company = Column(String, nullable=True)
        escrow_status_note = Column(Text, nullable=True)
        created_at = Column(String, nullable=False)

    class IndustrialOfferORM(Base):
        __tablename__ = "industrial_offers"
        id = Column(String, primary_key=True, index=True)
        project_id = Column(String, nullable=False, index=True)
        project_title = Column(String, nullable=False)
        buyer_id = Column(String, nullable=False)
        buyer_name = Column(String, nullable=False)
        buyer_company = Column(String, nullable=False)
        offer_amount_inr = Column(Float, nullable=False)
        proposal_type = Column(String, nullable=False)
        deliverables_message = Column(Text, nullable=True)
        status = Column(String, default="Pending", index=True)
        counter_amount_inr = Column(Float, nullable=True)
        spoc_approval = Column(String, default="Pending")
        created_at = Column(String, nullable=False)

    class AuditLogORM(Base):
        __tablename__ = "audit_logs"
        id = Column(String, primary_key=True, index=True)
        project_id = Column(String, nullable=True)
        project_title = Column(String, nullable=True)
        submitted_abstract = Column(Text, nullable=True)
        similarity_score = Column(Float, default=0.0)
        originality_score = Column(Float, default=100.0)
        status = Column(String, nullable=True)
        matched_project_id = Column(String, nullable=True)
        matched_project_title = Column(String, nullable=True)
        overlapping_keywords = Column(Text, nullable=True)
        created_at = Column(String, nullable=False)

except Exception:
    Base = None

def dict_from_row(row) -> Dict[str, Any]:
    """Converts a SQLite row to a dictionary with parsed JSON fields."""
    if row is None:
        return {}
    d = dict(row)
    # Parse JSON list/dict fields safely
    json_fields = ["tech_stack", "bom", "team_members", "top_overlapping_keywords", "technical_specs", "overlapping_keywords"]
    for f in json_fields:
        if f in d and isinstance(d[f], str):
            try:
                d[f] = json.loads(d[f])
            except Exception:
                pass
    return d
