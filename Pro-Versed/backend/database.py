"""
PRO-VERSED Production Database Architecture.
Canonical PostgreSQL Engine with SQLAlchemy 2.x, Connection Pooling,
Centralized Session Lifecycle, and Alembic Schema Management.
"""

import os
import tempfile
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any, List

from sqlalchemy import create_engine, event, text, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool, StaticPool

from models import Base, UserORM, ProjectORM, TaskORM, MarketplaceItemORM, IndustrialOfferORM, AuditLogORM
from auth import hash_password

_engines: Dict[str, Any] = {}
_sessionmakers: Dict[str, Any] = {}

def get_database_url() -> str:
    """
    Resolves the canonical database connection URL from environment variables.
    Defaults to PostgreSQL for production/staging, with fallback for local test runners.
    """
    if os.environ.get("DATABASE_URL"):
        url = os.environ["DATABASE_URL"]
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    if os.environ.get("PROVERSED_DB_PATH"):
        db_path = os.environ["PROVERSED_DB_PATH"]
        return f"sqlite:///{db_path}"

    default_sqlite_path = os.path.join(tempfile.gettempdir(), "proversed.db") if os.name == 'nt' else "/tmp/proversed.db"
    return f"sqlite:///{default_sqlite_path}"


def get_engine():
    """Returns the SQLAlchemy Engine for the current database configuration."""
    db_url = get_database_url()
    if db_url in _engines:
        return _engines[db_url]

    is_sqlite = db_url.startswith("sqlite")
    if is_sqlite:
        eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
                cursor.close()
    else:
        pool_size = int(os.environ.get("DB_POOL_SIZE", "20"))
        max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
        pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
        pool_recycle = int(os.environ.get("DB_POOL_RECYCLE", "3600"))

        eng = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True
        )

    _engines[db_url] = eng
    return eng


def get_sessionmaker() -> sessionmaker:
    """Returns the Session factory bound to the active engine."""
    db_url = get_database_url()
    if db_url in _sessionmakers:
        return _sessionmakers[db_url]

    eng = get_engine()
    sm = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    _sessionmakers[db_url] = sm
    return sm


# Global alias for default engine and session factory
engine = get_engine()
SessionLocal = get_sessionmaker()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Centralized Context Manager for SQLAlchemy Session Lifecycle:
    - Automatically commits on success.
    - Automatically rolls back on any uncaught exception.
    - Closes session deterministically in finally block.
    """
    sm = get_sessionmaker()
    session = sm()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI Dependency yielding a managed SQLAlchemy Session:
    Guarantees session acquisition, rollback on exception, and cleanup on request termination.
    """
    sm = get_sessionmaker()
    session = sm()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_connection() -> sqlite3.Connection:
    """Returns a raw SQLite connection for compatibility tests."""
    db_path = os.environ.get("PROVERSED_DB_PATH", os.path.join(tempfile.gettempdir(), "proversed.db") if os.name == 'nt' else "/tmp/proversed.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


@contextmanager
def get_db_context():
    """Backward-compatible raw connection context manager."""
    conn = get_db_connection()
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def is_academic_domain(email: str) -> bool:
    """Verifies if email belongs to .ac.in or .edu.in or recognized academic domain."""
    email_lower = email.lower()
    return email_lower.endswith(".ac.in") or email_lower.endswith(".edu.in") or email_lower.endswith(".edu")


def is_industry_domain(email: str) -> bool:
    """Checks if email is a recognized corporate or research enterprise."""
    email_lower = email.lower()
    return any(domain in email_lower for domain in ["tata", "elxsi", "drdo", "isro", "lnt", "mahindra", "infosys", "tcs", "intel", "bosch", "qualcomm"])


def init_db(db: Optional[Session] = None):
    """
    Initializes database schema via SQLAlchemy metadata and seeds default ecosystem personas if empty.
    """
    eng = get_engine()
    Base.metadata.create_all(bind=eng)

    if db is None:
        with get_db_session() as session:
            seed_initial_data(session)
    else:
        seed_initial_data(db)


def seed_initial_data(db: Session):
    """Populates rich national ecosystem seed data idempotently."""
    user_count = db.query(UserORM).count()
    if user_count > 0:
        return

    default_pwhash, default_pwsalt = hash_password("Password123!")

    # Pre-seeded personas
    users = [
        UserORM(
            id="usr_student_1",
            name="Aarav Patel",
            email="aarav@cse.iitb.ac.in",
            role="student",
            college="Indian Institute of Technology (IIT) Bombay",
            department="Computer Science & Engineering",
            company="",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=Aarav",
            is_verified_academic=1,
            is_verified_industry=0,
            bio="Final year B.Tech innovator specializing in Edge-AI, Autonomous Flight, and Embedded Robotics. SIH National Winner.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2026-01-10T10:00:00"
        ),
        UserORM(
            id="usr_faculty_1",
            name="Dr. Sunita Sharma",
            email="sunita.sharma@ece.iisc.ac.in",
            role="faculty",
            college="Indian Institute of Science (IISc) Bangalore",
            department="Electrical Communication Engineering",
            company="",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=Sunita",
            is_verified_academic=1,
            is_verified_industry=0,
            bio="Professor of Robotics & Autonomous Systems. IEEE Senior Member, 14 Granted Patents, Government Grant Evaluator.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2025-11-15T09:30:00"
        ),
        UserORM(
            id="usr_sunita_raman",
            name="Dr. Sunita Raman",
            email="sunita.raman@iisc.ac.in",
            role="faculty",
            college="Indian Institute of Science (IISc) Bangalore",
            department="Electrical Communication Engineering",
            company="",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=SunitaR",
            is_verified_academic=1,
            is_verified_industry=0,
            bio="Senior Professor and Mentor.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2025-11-15T09:30:00"
        ),
        UserORM(
            id="usr_spoc_1",
            name="Prof. Rajesh Kulkarni",
            email="spoc.rnd@coep.ac.in",
            role="spoc",
            college="COEP Technological University, Pune",
            department="Dean of R&D and Innovation",
            company="",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=Rajesh",
            is_verified_academic=1,
            is_verified_industry=0,
            bio="Dean of Innovation & Institutional IPR SPOC. Mentored 40+ student startup spinouts and institutional patent filings.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2025-10-01T14:00:00"
        ),
        UserORM(
            id="usr_rk_mukherjee",
            name="Prof. R.K. Mukherjee",
            email="rk.mukherjee@nitt.edu.in",
            role="spoc",
            college="NIT Trichy",
            department="R&D Dean",
            company="",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=Mukherjee",
            is_verified_academic=1,
            is_verified_industry=0,
            bio="Institutional SPOC & Dean.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2025-10-01T14:00:00"
        ),
        UserORM(
            id="usr_industrialist_1",
            name="Vikramaditya Singhania",
            email="vikram@tataelxsi.co.in",
            role="industrialist",
            college="",
            department="",
            company="Tata Elxsi R&D Ventures",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=Vikram",
            is_verified_academic=0,
            is_verified_industry=1,
            bio="VP of Technology & Corporate Ventures. Scouting high-TRL university hardware prototypes for strategic acquisition.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2025-12-05T11:20:00"
        ),
        UserORM(
            id="usr_vikram_s",
            name="Vikram Singhania",
            email="vikram.s@tataelxsi.com",
            role="industrialist",
            college="",
            department="",
            company="Tata Elxsi",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=VikramS",
            is_verified_academic=0,
            is_verified_industry=1,
            bio="Enterprise Corporate Partner.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2025-12-05T11:20:00"
        ),
        UserORM(
            id="usr_admin_1",
            name="Platform SuperAdmin",
            email="admin@proved.gov.in",
            role="admin",
            college="National Innovation Portal (NIP)",
            department="AICTE / Ministry of Education",
            company="",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=Admin",
            is_verified_academic=1,
            is_verified_industry=1,
            bio="National Repository Director & Quality Assurance Auditor.",
            password_hash=default_pwhash,
            password_salt=default_pwsalt,
            created_at="2025-09-01T08:00:00"
        )
    ]
    for u in users:
        db.add(u)

    # Seed initial project
    proj1 = ProjectORM(
        id="proj_001",
        title="AeroGuard: Autonomous Solar-Powered UAV for Precision Agricultural Crop Health Diagnostics",
        abstract="AeroGuard integrates hyperspectral edge sensors with a custom lightweight carbon-fiber hexacopter chassis.",
        description="Equipped with onboard Nvidia Jetson Nano executing a quantized YOLOv8 neural network.",
        domain="Agriculture & Rural Development",
        category="Hardware Prototype",
        tech_stack='["Nvidia Jetson", "PyTorch", "ROS2", "Pixhawk 4", "OpenCV", "Carbon Fiber Chassis"]',
        repo_url="https://github.com/pro-versed/aeroguard-uav",
        demo_url="https://aeroguard.iitb.ac.in",
        bom='[{"name": "Pixhawk 4 Flight Controller", "qty": 1, "approx_cost_inr": 18500}, {"name": "Jetson Nano 4GB", "qty": 1, "approx_cost_inr": 14000}]',
        lifecycle_status="Prototype Ready",
        originality_score=94.5,
        similarity_index=5.5,
        plagiarism_status="PASSED",
        highest_match_project_id=None,
        highest_match_title=None,
        top_overlapping_keywords='["hyperspectral", "precision agriculture", "hexacopter"]',
        college_name="Indian Institute of Technology (IIT) Bombay",
        department="Computer Science & Engineering",
        team_lead_id="usr_student_1",
        team_lead_name="Aarav Patel",
        faculty_mentor_id="usr_faculty_1",
        faculty_mentor_name="Dr. Sunita Sharma",
        team_members='["Aarav Patel", "Rohan Verma", "Sneha Rao"]',
        patent_status="Provisional Filed",
        estimated_budget_inr=65000.0,
        stars_count=42,
        views_count=320,
        created_at="2026-01-15T12:00:00",
        updated_at="2026-02-01T15:30:00"
    )
    db.add(proj1)

    task1 = TaskORM(
        id="tsk_001",
        project_id="proj_001",
        title="Flight Stability Benchmark & Wind Resistance Testing",
        description="Measure battery draw and stability at 25km/h wind speeds.",
        column="in_progress",
        priority="High",
        assignee_name="Aarav Patel",
        due_date="2026-09-20",
        faculty_feedback="Ensure fail-safe return-to-home is calibrated.",
        created_at="2026-01-16T10:00:00"
    )
    db.add(task1)

    item1 = MarketplaceItemORM(
        id="baz_001",
        title="Custom 6-Axis Gimbal Hyperspectral Sensor Mount",
        description="Vibration-isolated carbon fiber gimbal with quick-release mount.",
        seller_id="usr_student_1",
        seller_name="Aarav Patel",
        seller_college="IIT Bombay",
        seller_role="Student Innovator",
        category="Hardware Prototype",
        price_inr=12500.0,
        stock_quantity=3,
        technical_specs='{"weight": "320g", "payload": "1.2kg", "interface": "I2C / UART"}',
        status="Available",
        project_id="proj_001",
        image_icon="cpu",
        escrow_step=1,
        escrow_buyer_id="",
        escrow_buyer_name="",
        escrow_buyer_company="",
        escrow_status_note="Available for purchase / escrow lock.",
        created_at="2026-01-20T14:00:00"
    )
    db.add(item1)

    offer1 = IndustrialOfferORM(
        id="off_001",
        project_id="proj_001",
        project_title="AeroGuard: Autonomous Solar-Powered UAV",
        buyer_id="usr_industrialist_1",
        buyer_name="Vikramaditya Singhania",
        buyer_company="Tata Elxsi R&D Ventures",
        offer_amount_inr=350000.0,
        proposal_type="Commercial IP Acquisition",
        deliverables_message="Full firmware codebase, hardware CAD files, and exclusive manufacturing rights for North India.",
        status="Pending",
        counter_amount_inr=0.0,
        spoc_approval="Pending",
        created_at="2026-02-05T16:00:00"
    )
    db.add(offer1)

    db.commit()



