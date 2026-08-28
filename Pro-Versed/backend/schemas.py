"""
Pydantic Schemas for Pro-Versed REST API.
Compatible with Pydantic v1 and v2.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# --- User Schemas ---
class UserBase(BaseModel):
    name: str
    email: str
    role: str
    college: Optional[str] = ""
    department: Optional[str] = ""
    company: Optional[str] = ""
    avatar_url: Optional[str] = ""
    bio: Optional[str] = ""

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: str
    is_verified_academic: int = 0
    is_verified_industry: int = 0
    created_at: str

    class Config:
        from_attributes = True
        orm_mode = True

class DemoLoginRequest(BaseModel):
    user_id: str

# --- Authentication & Security Schemas ---
class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    remember_me: Optional[bool] = False

class RegisterRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    fullName: Optional[str] = Field(None, max_length=100)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    role: Optional[str] = "student"
    college: Optional[str] = ""
    department: Optional[str] = ""
    company: Optional[str] = ""
    collegeCompany: Optional[str] = ""
    bio: Optional[str] = ""
    otp: Optional[str] = Field(None, description="6-digit verification OTP")

    def get_name(self) -> str:
        return (self.fullName or self.name or "").strip()

    def get_college_or_company(self) -> str:
        return (self.college or self.collegeCompany or self.company or "").strip()

class SendOtpRequest(BaseModel):
    email: str = Field(..., max_length=254, description="User email for OTP verification")

class SendOtpResponse(BaseModel):
    message: str = "Verification OTP has been sent to your email."
    success: bool = True
    otp: Optional[str] = None  # Populated during development/local testing

class VerifyOtpRequest(BaseModel):
    email: str = Field(..., max_length=254)
    otp: str = Field(..., min_length=4, max_length=10)

class VerifyOtpResponse(BaseModel):
    message: str = "Email address verified successfully."
    success: bool = True
    verified: bool = True

class AuthResponse(BaseModel):
    user: UserResponse
    session_token: str
    expires_at: str
    message: str = "Authentication successful"

class SessionValidationResponse(BaseModel):
    valid: bool
    user: Optional[UserResponse] = None
    session: Optional[Dict[str, Any]] = None

class SecurityStatusResponse(BaseModel):
    email: str
    attempts_remaining_this_hour: int
    consecutive_failed_attempts: int
    is_locked: bool
    locked_until: Optional[str] = None
    remaining_lockout_seconds: int

class LogoutResponse(BaseModel):
    message: str = "Session successfully invalidated."
    success: bool = True

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=254, description="User email address for password recovery")

class ForgotPasswordResponse(BaseModel):
    message: str = "If an account exists with this email, a password reset link has been sent."
    success: bool = True
    reset_token: Optional[str] = None  # Populated during development/local testing

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: Optional[str] = Field(None, max_length=128, description="New password (snake_case)")
    newPassword: Optional[str] = Field(None, max_length=128, description="New password (camelCase)")

    def get_password(self) -> str:
        return self.new_password or self.newPassword or ""

class ResetPasswordResponse(BaseModel):
    message: str = "Password has been successfully reset. You may now sign in with your new credentials."
    success: bool = True

# --- Project Schemas ---
class BOMItem(BaseModel):
    item: str
    specs: str
    qty: int = 1
    unit_cost: float = 0.0
    source: Optional[str] = ""

class ProjectCreate(BaseModel):
    title: str
    abstract: str
    description: Optional[str] = ""
    domain: str
    category: str  # Software, Hardware, Hybrid
    tech_stack: List[str]
    repo_url: Optional[str] = ""
    demo_url: Optional[str] = ""
    bom: List[BOMItem] = []
    lifecycle_status: Optional[str] = "Ideation"
    college_name: str
    department: Optional[str] = ""
    team_lead_id: str
    team_lead_name: str
    faculty_mentor_id: Optional[str] = ""
    faculty_mentor_name: Optional[str] = ""
    team_members: Optional[List[str]] = []
    patent_status: Optional[str] = "None"
    estimated_budget_inr: Optional[float] = 0.0

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    repo_url: Optional[str] = None
    demo_url: Optional[str] = None
    bom: Optional[List[BOMItem]] = None
    lifecycle_status: Optional[str] = None
    patent_status: Optional[str] = None
    faculty_mentor_name: Optional[str] = None
    estimated_budget_inr: Optional[float] = None

class ProjectResponse(BaseModel):
    id: str
    title: str
    abstract: str
    description: Optional[str] = ""
    domain: str
    category: str
    tech_stack: List[str]
    repo_url: Optional[str] = ""
    demo_url: Optional[str] = ""
    bom: List[Dict[str, Any]]
    lifecycle_status: str
    originality_score: float
    similarity_index: float
    plagiarism_status: str
    highest_match_project_id: Optional[str] = None
    highest_match_title: Optional[str] = None
    top_overlapping_keywords: Optional[List[str]] = []
    college_name: str
    department: Optional[str] = ""
    team_lead_id: str
    team_lead_name: str
    faculty_mentor_id: Optional[str] = None
    faculty_mentor_name: Optional[str] = None
    team_members: Optional[List[str]] = []
    patent_status: str
    estimated_budget_inr: float
    stars_count: int
    views_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
        orm_mode = True

# --- Kanban Task Schemas ---
class TaskCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = ""
    column: Optional[str] = "backlog"
    priority: Optional[str] = "Medium"
    assignee_name: Optional[str] = ""
    due_date: Optional[str] = ""
    faculty_feedback: Optional[str] = ""

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    column: Optional[str] = None
    priority: Optional[str] = None
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None
    faculty_feedback: Optional[str] = None

class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str] = ""
    column: str
    priority: str
    assignee_name: Optional[str] = ""
    due_date: Optional[str] = ""
    faculty_feedback: Optional[str] = ""
    created_at: str

    class Config:
        from_attributes = True
        orm_mode = True

# --- Marketplace (Bazaar) Schemas ---
class MarketplaceItemCreate(BaseModel):
    title: str
    description: str
    seller_id: str
    seller_name: str
    seller_college: Optional[str] = ""
    seller_role: Optional[str] = "Student Innovator"
    category: str
    price_inr: float
    stock_quantity: Optional[int] = 1
    technical_specs: Optional[Dict[str, Any]] = {}
    project_id: Optional[str] = None
    image_icon: Optional[str] = "cpu"

class EscrowAdvanceRequest(BaseModel):
    action: str  # e.g., "advance", "clear_mentor", "dispatch", "release_payout", "cancel", "lock", "buy_now", "hold_escrow", "confirm_delivery"
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    actor_name: Optional[str] = None
    actor_college: Optional[str] = None
    buyer_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_company: Optional[str] = None
    buyer_college: Optional[str] = None
    note: Optional[str] = None


class MarketplaceItemResponse(BaseModel):
    id: str
    title: str
    description: str
    seller_id: str
    seller_name: str
    seller_college: Optional[str] = ""
    seller_role: Optional[str] = ""
    category: str
    price_inr: float
    stock_quantity: int
    technical_specs: Optional[Dict[str, Any]] = {}
    status: str
    project_id: Optional[str] = None
    image_icon: str
    escrow_step: int
    escrow_buyer_id: Optional[str] = None
    escrow_buyer_name: Optional[str] = None
    escrow_buyer_company: Optional[str] = None
    escrow_status_note: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True
        orm_mode = True

# --- Industrial Offer Schemas ---
class IndustrialOfferCreate(BaseModel):
    project_id: str
    project_title: str
    buyer_id: str
    buyer_name: str
    buyer_company: str
    offer_amount_inr: float
    proposal_type: str
    deliverables_message: Optional[str] = ""

class IndustrialOfferUpdate(BaseModel):
    status: Optional[str] = None  # Pending, Accepted, Countered, Rejected
    counter_amount_inr: Optional[float] = None
    spoc_approval: Optional[str] = None  # Pending, Approved, Denied

class IndustrialOfferResponse(BaseModel):
    id: str
    project_id: str
    project_title: str
    buyer_id: str
    buyer_name: str
    buyer_company: str
    offer_amount_inr: float
    proposal_type: str
    deliverables_message: Optional[str] = ""
    status: str
    counter_amount_inr: Optional[float] = None
    spoc_approval: str
    created_at: str

    class Config:
        from_attributes = True
        orm_mode = True

# --- Plagiarism Pre-check Schemas ---
class PlagiarismCheckRequest(BaseModel):
    abstract: str
    title: Optional[str] = ""
    description: Optional[str] = ""
    exclude_project_id: Optional[str] = None

class PlagiarismCheckResponse(BaseModel):
    similarity_score: float
    originality_score: float
    plagiarism_status: str
    highest_match_project_id: Optional[str] = None
    highest_match_title: Optional[str] = None
    matched_college: Optional[str] = None
    top_overlapping_keywords: List[str] = []
    audit_summary: str
