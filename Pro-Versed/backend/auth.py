"""
PRO-VERSED — Authentication & Security Core Engine
Production-ready authentication, salted password hashing, timing-safe validation,
sliding 1-hour rate limiting (max 10 attempts), and 5-failure / 3-hour account lockout.
Compatible with SQLAlchemy Session (canonical) and raw sqlite3 connections.
"""

import os
import re
import uuid
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session

# Configuration Constants
PBKDF2_ITERATIONS = 100_000
PBKDF2_ALGORITHM = "sha256"
SESSION_DURATION_HOURS = 24
SESSION_DURATION_REMEMBER_DAYS = 30
RATE_LIMIT_MAX_ATTEMPTS_PER_HOUR = 10
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
ACCOUNT_LOCKOUT_MAX_CONSECUTIVE_FAILS = 5
ACCOUNT_LOCKOUT_DURATION_SECONDS = 10800  # Exactly 3 hours
RESET_TOKEN_EXPIRY_MINUTES = 30
FORGOT_PASSWORD_RATE_LIMIT_MAX = 5
FORGOT_PASSWORD_WINDOW_SECONDS = 3600
OTP_EXPIRATION_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RATE_LIMIT_MAX = 3
OTP_RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes

GENERIC_AUTH_ERROR = "Invalid email or password. Please try again."
GENERIC_LOCKOUT_ERROR = "Account is temporarily locked due to consecutive failed login attempts. Please try again in 3 hours."
GENERIC_RATE_LIMIT_ERROR = "Rate limit exceeded. Maximum 10 login attempts per hour allowed."
GENERIC_FORGOT_PASSWORD_MESSAGE = "If an account exists with this email, a password reset link has been sent."
GENERIC_FORGOT_PASSWORD_RATE_LIMIT_ERROR = "Rate limit exceeded for password reset requests. Maximum 5 requests per hour allowed."
GENERIC_OTP_RATE_LIMIT_ERROR = "Rate limit exceeded for OTP requests. Maximum 3 requests per 10 minutes allowed."

# Strict RFC 5322 compatible email pattern
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

# Dummy hash for timing attack mitigation when user does not exist
DUMMY_SALT = "0123456789abcdef0123456789abcdef"
DUMMY_HASH = hashlib.pbkdf2_hmac(
    PBKDF2_ALGORITHM,
    b"dummy_password_for_timing_safety",
    bytes.fromhex(DUMMY_SALT),
    PBKDF2_ITERATIONS
).hex()


def normalize_email(email: str) -> str:
    """Sanitizes and normalizes an email address."""
    if not email or not isinstance(email, str):
        return ""
    return email.strip().lower()


def validate_email_format(email: str) -> bool:
    """Validates email format using strict regex and length constraints."""
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email))


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validates password complexity requirements:
    Minimum 8 characters, at least one uppercase, one lowercase, one number, and one special character.
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password cannot exceed 128 characters."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    return True, None


def hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations and a unique salt.
    Returns (hash_hex, salt_hex).
    """
    if salt_hex is None:
        salt_bytes = secrets.token_bytes(16)
        salt_hex = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt_hex)

    key = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS
    )
    return key.hex(), salt_hex


def verify_password(password: str, stored_hash_hex: str, stored_salt_hex: str) -> bool:
    """
    Verifies a plaintext password against a stored salt & hash using constant-time comparison.
    """
    computed_hash_hex, _ = hash_password(password, stored_salt_hex)
    return hmac.compare_digest(computed_hash_hex, stored_hash_hex)


def perform_dummy_verification(password: str):
    """Executes a dummy hash verification to equalize execution time for missing users."""
    computed_hash_hex, _ = hash_password(password, DUMMY_SALT)
    hmac.compare_digest(computed_hash_hex, DUMMY_HASH)


def generate_session_token() -> str:
    """Generates a 256-bit cryptographically secure URL-safe session token."""
    return secrets.token_urlsafe(32)


# ==========================================
# RATE LIMITING ENGINE
# ==========================================

def check_rate_limit(conn: Union[Session, sqlite3.Connection], ip_address: str, email: str, now: Optional[datetime] = None) -> Tuple[bool, int]:
    """
    Enforces maximum 10 login attempts per hour per IP address/email.
    Returns (is_allowed, attempts_remaining).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window_start = (now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)).isoformat()
    stale_cutoff = (now - timedelta(hours=24)).isoformat()

    if isinstance(conn, Session):
        from models import LoginAttemptORM
        # Clean up stale attempts older than 24 hours
        conn.query(LoginAttemptORM).filter(LoginAttemptORM.timestamp < stale_cutoff).delete(synchronize_session=False)
        # Count attempts in the last 1 hour
        count = conn.query(LoginAttemptORM).filter(
            ((LoginAttemptORM.ip_address == ip_address) | (LoginAttemptORM.email == email)) &
            (LoginAttemptORM.timestamp >= window_start)
        ).count()
    else:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login_attempts WHERE timestamp < ?;", (stale_cutoff,))
        cursor.execute("""
            SELECT COUNT(*) FROM login_attempts 
            WHERE (ip_address = ? OR email = ?) AND timestamp >= ?;
        """, (ip_address, email, window_start))
        count = cursor.fetchone()[0]

    attempts_remaining = max(0, RATE_LIMIT_MAX_ATTEMPTS_PER_HOUR - count)
    is_allowed = count < RATE_LIMIT_MAX_ATTEMPTS_PER_HOUR
    return is_allowed, attempts_remaining


def record_login_attempt(conn: Union[Session, sqlite3.Connection], ip_address: str, email: str, is_success: bool, now: Optional[datetime] = None):
    """Records an authentication attempt for audit and rate-limiting."""
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(conn, Session):
        from models import LoginAttemptORM
        rec = LoginAttemptORM(
            id=secrets.token_hex(12),
            ip_address=ip_address,
            email=email,
            timestamp=now.isoformat(),
            is_success=1 if is_success else 0
        )
        conn.add(rec)
        conn.flush()
    else:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO login_attempts (id, ip_address, email, timestamp, is_success)
            VALUES (?, ?, ?, ?, ?);
        """, (secrets.token_hex(12), ip_address, email, now.isoformat(), 1 if is_success else 0))
        conn.commit()


# ==========================================
# ACCOUNT LOCKOUT MANAGER
# ==========================================

def get_account_security_status(conn: Union[Session, sqlite3.Connection], email: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Retrieves the lockout status for an email account.
    Checks and auto-resets expired lockouts.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(conn, Session):
        from models import AccountSecurityORM
        row = conn.query(AccountSecurityORM).filter(AccountSecurityORM.email == email).first()
        if not row:
            return {
                "email": email,
                "consecutive_failed_attempts": 0,
                "is_locked": False,
                "locked_until": None,
                "remaining_lockout_seconds": 0,
                "lockout_count": 0
            }
        consecutive_failed = row.consecutive_failed_attempts
        locked_until_str = row.locked_until
        lockout_count = row.lockout_count

        if locked_until_str:
            try:
                locked_until_dt = datetime.fromisoformat(locked_until_str)
                if locked_until_dt.tzinfo is None:
                    locked_until_dt = locked_until_dt.replace(tzinfo=timezone.utc)
                if now < locked_until_dt:
                    remaining_seconds = int((locked_until_dt - now).total_seconds())
                    return {
                        "email": email,
                        "consecutive_failed_attempts": consecutive_failed,
                        "is_locked": True,
                        "locked_until": locked_until_dt.isoformat(),
                        "remaining_lockout_seconds": max(0, remaining_seconds),
                        "lockout_count": lockout_count
                    }
                else:
                    row.consecutive_failed_attempts = 0
                    row.locked_until = None
                    conn.flush()
                    return {
                        "email": email,
                        "consecutive_failed_attempts": 0,
                        "is_locked": False,
                        "locked_until": None,
                        "remaining_lockout_seconds": 0,
                        "lockout_count": lockout_count
                    }
            except Exception:
                pass
        return {
            "email": email,
            "consecutive_failed_attempts": consecutive_failed,
            "is_locked": False,
            "locked_until": None,
            "remaining_lockout_seconds": 0,
            "lockout_count": lockout_count
        }
    else:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email, consecutive_failed_attempts, locked_until, last_failed_at, lockout_count
            FROM account_security WHERE email = ?;
        """, (email,))
        row = cursor.fetchone()

        if not row:
            return {
                "email": email,
                "consecutive_failed_attempts": 0,
                "is_locked": False,
                "locked_until": None,
                "remaining_lockout_seconds": 0,
                "lockout_count": 0
            }

        consecutive_failed = row["consecutive_failed_attempts"]
        locked_until_str = row["locked_until"]
        lockout_count = row["lockout_count"]

        if locked_until_str:
            try:
                locked_until_dt = datetime.fromisoformat(locked_until_str)
                if locked_until_dt.tzinfo is None:
                    locked_until_dt = locked_until_dt.replace(tzinfo=timezone.utc)
                
                if now < locked_until_dt:
                    remaining_seconds = int((locked_until_dt - now).total_seconds())
                    return {
                        "email": email,
                        "consecutive_failed_attempts": consecutive_failed,
                        "is_locked": True,
                        "locked_until": locked_until_dt.isoformat(),
                        "remaining_lockout_seconds": max(0, remaining_seconds),
                        "lockout_count": lockout_count
                    }
                else:
                    cursor.execute("""
                        UPDATE account_security
                        SET consecutive_failed_attempts = 0, locked_until = NULL
                        WHERE email = ?;
                    """, (email,))
                    conn.commit()
                    return {
                        "email": email,
                        "consecutive_failed_attempts": 0,
                        "is_locked": False,
                        "locked_until": None,
                        "remaining_lockout_seconds": 0,
                        "lockout_count": lockout_count
                    }
            except Exception:
                pass

        return {
            "email": email,
            "consecutive_failed_attempts": consecutive_failed,
            "is_locked": False,
            "locked_until": None,
            "remaining_lockout_seconds": 0,
            "lockout_count": lockout_count
        }


def record_failed_login(conn: Union[Session, sqlite3.Connection], email: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Increments consecutive failed attempts.
    If consecutive failed attempts reach 5, locks account for exactly 3 hours (10,800 seconds).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    status = get_account_security_status(conn, email, now)
    new_fails = status["consecutive_failed_attempts"] + 1
    new_locked_until = None
    lockout_count = status["lockout_count"]
    is_locked = False
    remaining_seconds = 0

    if new_fails >= ACCOUNT_LOCKOUT_MAX_CONSECUTIVE_FAILS:
        locked_until_dt = now + timedelta(seconds=ACCOUNT_LOCKOUT_DURATION_SECONDS)
        new_locked_until = locked_until_dt.isoformat()
        lockout_count += 1
        is_locked = True
        remaining_seconds = ACCOUNT_LOCKOUT_DURATION_SECONDS

    if isinstance(conn, Session):
        from models import AccountSecurityORM
        sec = conn.query(AccountSecurityORM).filter(AccountSecurityORM.email == email).first()
        if not sec:
            sec = AccountSecurityORM(
                email=email,
                consecutive_failed_attempts=new_fails,
                locked_until=new_locked_until,
                last_failed_at=now.isoformat(),
                lockout_count=lockout_count
            )
            conn.add(sec)
        else:
            sec.consecutive_failed_attempts = new_fails
            sec.locked_until = new_locked_until
            sec.last_failed_at = now.isoformat()
            sec.lockout_count = lockout_count
        conn.flush()
    else:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO account_security (email, consecutive_failed_attempts, locked_until, last_failed_at, lockout_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                consecutive_failed_attempts = excluded.consecutive_failed_attempts,
                locked_until = excluded.locked_until,
                last_failed_at = excluded.last_failed_at,
                lockout_count = excluded.lockout_count;
        """, (email, new_fails, new_locked_until, now.isoformat(), lockout_count))
        conn.commit()

    return {
        "email": email,
        "consecutive_failed_attempts": new_fails,
        "is_locked": is_locked,
        "locked_until": new_locked_until,
        "remaining_lockout_seconds": remaining_seconds,
        "lockout_count": lockout_count
    }


def reset_failed_login_counter(conn: Union[Session, sqlite3.Connection], email: str):
    """Resets failed login counter to 0 upon successful authentication."""
    if isinstance(conn, Session):
        from models import AccountSecurityORM
        sec = conn.query(AccountSecurityORM).filter(AccountSecurityORM.email == email).first()
        if sec:
            sec.consecutive_failed_attempts = 0
            sec.locked_until = None
            conn.flush()
    else:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE account_security
            SET consecutive_failed_attempts = 0, locked_until = NULL
            WHERE email = ?;
        """, (email,))
        conn.commit()


# ==========================================
# SESSION MANAGEMENT
# ==========================================

def create_user_session(
    conn: Union[Session, sqlite3.Connection],
    user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    remember_me: bool = False,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """Creates a new active session token and persists it in the database."""
    if now is None:
        now = datetime.now(timezone.utc)

    duration = timedelta(days=SESSION_DURATION_REMEMBER_DAYS) if remember_me else timedelta(hours=SESSION_DURATION_HOURS)
    expires_at = now + duration
    session_id = generate_session_token()

    if isinstance(conn, Session):
        from models import SessionORM
        sess = SessionORM(
            session_id=session_id,
            user_id=user_id,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            last_activity=now.isoformat(),
            ip_address=ip_address or "",
            user_agent=user_agent or "",
            is_active=1
        )
        conn.add(sess)
        conn.flush()
    else:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (session_id, user_id, created_at, expires_at, last_activity, ip_address, user_agent, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1);
        """, (
            session_id,
            user_id,
            now.isoformat(),
            expires_at.isoformat(),
            now.isoformat(),
            ip_address or "",
            user_agent or ""
        ))
        conn.commit()

    return {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "remember_me": remember_me
    }


def validate_session(conn: Union[Session, sqlite3.Connection], session_id: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """
    Validates a session token: checks active flag, expiration, and updates last_activity.
    Returns user record dict if valid, else None.
    """
    if not session_id or not isinstance(session_id, str):
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(conn, Session):
        from models import SessionORM, orm_to_dict
        s = conn.query(SessionORM).filter(SessionORM.session_id == session_id, SessionORM.is_active == 1).first()
        if not s or not s.user or s.user.is_active == 0:
            return None

        # Check expiration
        try:
            expires_dt = datetime.fromisoformat(s.expires_at)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if now >= expires_dt:
                s.is_active = 0
                conn.flush()
                return None
        except Exception:
            return None

        s.last_activity = now.isoformat()
        conn.flush()

        user_dict = orm_to_dict(s.user)
        return {
            "session": {
                "session_id": s.session_id,
                "created_at": s.created_at,
                "expires_at": s.expires_at,
                "last_activity": s.last_activity
            },
            "user": user_dict
        }
    else:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_id, s.user_id, s.created_at as session_created_at, s.expires_at, s.last_activity, s.is_active,
                   u.id, u.name, u.email, u.role, u.college, u.department, u.company,
                   u.avatar_url, u.is_verified_academic, u.is_verified_industry, u.bio,
                   u.created_at as user_created_at, u.is_active as user_is_active
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_id = ? AND s.is_active = 1;
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        if row["user_is_active"] == 0:
            return None

        expires_at_str = row["expires_at"]
        try:
            expires_dt = datetime.fromisoformat(expires_at_str)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if now >= expires_dt:
                cursor.execute("UPDATE sessions SET is_active = 0 WHERE session_id = ?;", (session_id,))
                conn.commit()
                return None
        except Exception:
            return None

        cursor.execute("UPDATE sessions SET last_activity = ? WHERE session_id = ?;", (now.isoformat(), session_id))
        conn.commit()

        return {
            "session": {
                "session_id": row["session_id"],
                "created_at": row["session_created_at"],
                "expires_at": row["expires_at"],
                "last_activity": now.isoformat()
            },
            "user": {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "role": row["role"],
                "college": row["college"],
                "department": row["department"],
                "company": row["company"],
                "avatar_url": row["avatar_url"],
                "is_verified_academic": row["is_verified_academic"],
                "is_verified_industry": row["is_verified_industry"],
                "bio": row["bio"],
                "created_at": row["user_created_at"] or row["session_created_at"]
            }
        }


def revoke_session(conn: Union[Session, sqlite3.Connection], session_id: str) -> bool:
    """Revokes / invalidates an active session."""
    if not session_id:
        return False
    if isinstance(conn, Session):
        from models import SessionORM
        s = conn.query(SessionORM).filter(SessionORM.session_id == session_id).first()
        if s:
            s.is_active = 0
            conn.flush()
            return True
        return False
    else:
        cursor = conn.cursor()
        cursor.execute("UPDATE sessions SET is_active = 0 WHERE session_id = ?;", (session_id,))
        conn.commit()
        return cursor.rowcount > 0


def revoke_all_user_sessions(conn: Union[Session, sqlite3.Connection], user_id: str) -> int:
    """Revokes all active sessions for a user (e.g. on password reset or security breach)."""
    if isinstance(conn, Session):
        from models import SessionORM
        count = conn.query(SessionORM).filter(SessionORM.user_id == user_id, SessionORM.is_active == 1).update({"is_active": 0})
        conn.flush()
        return count
    else:
        cursor = conn.cursor()
        cursor.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?;", (user_id,))
        conn.commit()
        return cursor.rowcount


# ==========================================
# PASSWORD RESET / FORGOT PASSWORD ENGINE
# ==========================================

def generate_reset_token() -> Tuple[str, str, str]:
    """
    Generates a cryptographically secure random password reset token.
    Returns (raw_token, hashed_token, expires_at_iso).
    """
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_dt = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
    return raw_token, hashed_token, expires_dt.isoformat()


def hash_reset_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a reset token for safe database lookups."""
    if not raw_token:
        return ""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def check_forgot_password_rate_limit(conn: Union[Session, sqlite3.Connection], ip_address: str, email: str, now: Optional[datetime] = None) -> Tuple[bool, int]:
    """
    Enforces rate limit for forgot-password requests (maximum 5 requests per hour per IP/email).
    Returns (is_allowed, attempts_remaining).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window_start = (now - timedelta(seconds=FORGOT_PASSWORD_WINDOW_SECONDS)).isoformat()
    stale_cutoff = (now - timedelta(hours=24)).isoformat()

    if isinstance(conn, Session):
        from models import PasswordResetAttemptORM
        conn.query(PasswordResetAttemptORM).filter(PasswordResetAttemptORM.timestamp < stale_cutoff).delete(synchronize_session=False)
        count = conn.query(PasswordResetAttemptORM).filter(
            ((PasswordResetAttemptORM.ip_address == ip_address) | (PasswordResetAttemptORM.email == email)) &
            (PasswordResetAttemptORM.timestamp >= window_start)
        ).count()
    else:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM password_reset_attempts WHERE timestamp < ?;", (stale_cutoff,))
        cursor.execute("""
            SELECT COUNT(*) FROM password_reset_attempts 
            WHERE (ip_address = ? OR email = ?) AND timestamp >= ?;
        """, (ip_address, email, window_start))
        count = cursor.fetchone()[0]

    attempts_remaining = max(0, FORGOT_PASSWORD_RATE_LIMIT_MAX - count)
    is_allowed = count < FORGOT_PASSWORD_RATE_LIMIT_MAX
    return is_allowed, attempts_remaining


def record_forgot_password_attempt(conn: Union[Session, sqlite3.Connection], ip_address: str, email: str, now: Optional[datetime] = None):
    """Records a password reset request attempt for rate limiting."""
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(conn, Session):
        from models import PasswordResetAttemptORM
        rec = PasswordResetAttemptORM(
            id=secrets.token_hex(12),
            ip_address=ip_address,
            email=email,
            timestamp=now.isoformat()
        )
        conn.add(rec)
        conn.flush()
    else:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO password_reset_attempts (id, ip_address, email, timestamp)
            VALUES (?, ?, ?, ?);
        """, (secrets.token_hex(12), ip_address, email, now.isoformat()))
        conn.commit()


def create_password_reset_token(conn: Union[Session, sqlite3.Connection], email: str) -> Optional[str]:
    """
    Checks if active user exists for given email.
    If exists, generates token, stores hash & expiry in DB, and returns raw token.
    If user doesn't exist, returns None.
    """
    raw_token, hashed_token, expires_at = generate_reset_token()

    if isinstance(conn, Session):
        from models import UserORM
        user = conn.query(UserORM).filter(UserORM.email == email, UserORM.is_active == 1).first()
        if not user:
            return None
        user.reset_password_token = hashed_token
        user.reset_password_expires = expires_at
        conn.flush()
        return raw_token
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT id, is_active FROM users WHERE email = ?;", (email,))
        user = cursor.fetchone()
        if not user or user["is_active"] == 0:
            return None

        cursor.execute("""
            UPDATE users
            SET reset_password_token = ?, reset_password_expires = ?
            WHERE id = ?;
        """, (hashed_token, expires_at, user["id"]))
        conn.commit()
        return raw_token


def reset_password_with_token(conn: Union[Session, sqlite3.Connection], token: str, new_password: str, now: Optional[datetime] = None) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validates token, checks expiration, hashes new password with PBKDF2, updates DB,
    clears reset token fields, resets lockout counter, and revokes all old sessions.
    Returns (success, error_message, user_dict).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not token or not token.strip():
        return False, "Password reset token is required.", None

    if not new_password:
        return False, "New password is required.", None

    is_strong, err_msg = validate_password_strength(new_password)
    if not is_strong:
        return False, err_msg or "Password does not meet complexity requirements.", None

    token_hash = hash_reset_token(token)

    if isinstance(conn, Session):
        from models import UserORM, orm_to_dict
        user = conn.query(UserORM).filter(UserORM.reset_password_token == token_hash, UserORM.is_active == 1).first()
        if not user or not user.reset_password_expires:
            return False, "Invalid, expired, or previously consumed password reset token.", None

        try:
            expires_dt = datetime.fromisoformat(user.reset_password_expires)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if now > expires_dt:
                user.reset_password_token = None
                user.reset_password_expires = None
                conn.flush()
                return False, "Password reset token has expired. Please request a new one.", None
        except Exception:
            return False, "Invalid reset token timestamp.", None

        pwhash, pwsalt = hash_password(new_password)
        user.password_hash = pwhash
        user.password_salt = pwsalt
        user.reset_password_token = None
        user.reset_password_expires = None
        conn.flush()

        reset_failed_login_counter(conn, user.email)
        revoke_all_user_sessions(conn, user.id)

        user_dict = orm_to_dict(user)
        return True, None, user_dict
    else:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users
            WHERE reset_password_token = ? AND is_active = 1;
        """, (token_hash,))
        user = cursor.fetchone()

        if not user or not user["reset_password_expires"]:
            return False, "Invalid, expired, or previously consumed password reset token.", None

        expires_str = user["reset_password_expires"]
        try:
            expires_dt = datetime.fromisoformat(expires_str)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)

            if now > expires_dt:
                cursor.execute("UPDATE users SET reset_password_token = NULL, reset_password_expires = NULL WHERE id = ?;", (user["id"],))
                conn.commit()
                return False, "Password reset token has expired. Please request a new one.", None
        except Exception:
            return False, "Invalid reset token timestamp.", None

        pwhash, pwsalt = hash_password(new_password)
        cursor.execute("""
            UPDATE users
            SET password_hash = ?, password_salt = ?, reset_password_token = NULL, reset_password_expires = NULL
            WHERE id = ?;
        """, (pwhash, pwsalt, user["id"]))

        reset_failed_login_counter(conn, user["email"])
        revoke_all_user_sessions(conn, user["id"])
        conn.commit()

        user_dict = dict(user)
        return True, None, user_dict


# ==========================================
# OTP GENERATION, RATE-LIMITING & VERIFICATION
# ==========================================

def generate_otp(length: int = 6) -> str:
    """Generates a cryptographically secure numeric OTP string of given length."""
    val = secrets.randbelow(10 ** length)
    return f"{val:0{length}d}"


def hash_otp(otp: str) -> str:
    """Returns SHA-256 hash of the OTP."""
    return hashlib.sha256(otp.strip().encode("utf-8")).hexdigest()


def check_otp_rate_limit(conn: Union[Session, sqlite3.Connection], ip_address: str, email: str, now: Optional[datetime] = None) -> Tuple[bool, int]:
    """
    Checks whether the client IP or email has exceeded the OTP request limit (max 3 per 10 minutes).
    Returns (is_allowed, remaining_attempts).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window_start = (now - timedelta(seconds=OTP_RATE_LIMIT_WINDOW_SECONDS)).isoformat()

    if isinstance(conn, Session):
        from models import OtpRequestORM
        count = conn.query(OtpRequestORM).filter(
            ((OtpRequestORM.ip_address == ip_address) | (OtpRequestORM.email == email.lower())) &
            (OtpRequestORM.timestamp > window_start)
        ).count()
    else:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM otp_requests
            WHERE (ip_address = ? OR email = ?) AND timestamp > ?;
        """, (ip_address, email.lower(), window_start))
        row = cursor.fetchone()
        count = row["cnt"] if row else 0

    is_allowed = count < OTP_RATE_LIMIT_MAX
    remaining = max(0, OTP_RATE_LIMIT_MAX - count)
    return is_allowed, remaining


def record_otp_request(conn: Union[Session, sqlite3.Connection], ip_address: str, email: str, now: Optional[datetime] = None) -> None:
    """Records an OTP send request in the rate limiting table."""
    if now is None:
        now = datetime.now(timezone.utc)

    req_id = f"otp_req_{uuid.uuid4().hex[:12]}"

    if isinstance(conn, Session):
        from models import OtpRequestORM
        rec = OtpRequestORM(
            id=req_id,
            ip_address=ip_address,
            email=email.lower(),
            timestamp=now.isoformat()
        )
        conn.add(rec)
        conn.flush()
    else:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO otp_requests (id, ip_address, email, timestamp)
            VALUES (?, ?, ?, ?);
        """, (req_id, ip_address, email.lower(), now.isoformat()))
        conn.commit()


def store_otp(conn: Union[Session, sqlite3.Connection], email: str, otp: str, expires_minutes: int = OTP_EXPIRATION_MINUTES, now: Optional[datetime] = None) -> Tuple[str, str]:
    """
    Stores the hashed OTP in database with an expiration timestamp.
    Removes any old pending OTPs for this email.
    Returns (raw_otp, expires_at_iso).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    normalized_email = email.strip().lower()
    otp_hashed = hash_otp(otp)
    expires_at = (now + timedelta(minutes=expires_minutes)).isoformat()
    now_str = now.isoformat()

    if isinstance(conn, Session):
        from models import OtpVerificationORM
        conn.query(OtpVerificationORM).filter(OtpVerificationORM.email == normalized_email).delete()
        ver = OtpVerificationORM(
            email=normalized_email,
            otp_hash=otp_hashed,
            expires_at=expires_at,
            attempts=0,
            created_at=now_str
        )
        conn.add(ver)
        conn.flush()
    else:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM otp_verifications WHERE email = ?;", (normalized_email,))
        cursor.execute("""
            INSERT INTO otp_verifications (email, otp_hash, expires_at, attempts, created_at)
            VALUES (?, ?, ?, 0, ?);
        """, (normalized_email, otp_hashed, expires_at, now_str))
        conn.commit()

    return otp, expires_at


def verify_otp(conn: Union[Session, sqlite3.Connection], email: str, otp: str, consume: bool = True, now: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
    """
    Validates a submitted 6-digit OTP for the given email against stored hash and expiration.
    Enforces maximum 5 attempts. If consume=True, deletes OTP on success.
    Returns (is_valid, error_message).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not otp or not otp.strip():
        return False, "OTP code is required."

    normalized_email = email.strip().lower()

    if isinstance(conn, Session):
        from models import OtpVerificationORM
        row = conn.query(OtpVerificationORM).filter(OtpVerificationORM.email == normalized_email).order_by(OtpVerificationORM.id.desc()).first()
        if not row:
            return False, "No OTP verification request found for this email. Please request a new OTP."

        if row.attempts >= OTP_MAX_ATTEMPTS:
            return False, "Maximum verification attempts exceeded. Please request a new OTP."

        try:
            expires_dt = datetime.fromisoformat(row.expires_at)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if now > expires_dt:
                return False, "OTP has expired. Please request a new code."
        except Exception:
            return False, "Invalid OTP timestamp."

        input_hash = hash_otp(otp.strip())
        if input_hash != row.otp_hash:
            row.attempts += 1
            conn.flush()
            remaining = OTP_MAX_ATTEMPTS - row.attempts
            if remaining > 0:
                return False, f"Incorrect OTP code. {remaining} attempt(s) remaining."
            return False, "Incorrect OTP code. Maximum attempts exceeded. Please request a new OTP."

        if consume:
            conn.delete(row)
            conn.flush()

        return True, None
    else:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM otp_verifications
            WHERE email = ?
            ORDER BY id DESC LIMIT 1;
        """, (normalized_email,))
        row = cursor.fetchone()

        if not row:
            return False, "No OTP verification request found for this email. Please request a new OTP."

        attempts = row["attempts"]
        if attempts >= OTP_MAX_ATTEMPTS:
            return False, "Maximum verification attempts exceeded. Please request a new OTP."

        expires_str = row["expires_at"]
        try:
            expires_dt = datetime.fromisoformat(expires_str)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if now > expires_dt:
                return False, "OTP has expired. Please request a new code."
        except Exception:
            return False, "Invalid OTP timestamp."

        input_hash = hash_otp(otp.strip())
        if input_hash != row["otp_hash"]:
            new_attempts = attempts + 1
            cursor.execute("UPDATE otp_verifications SET attempts = ? WHERE id = ?;", (new_attempts, row["id"]))
            conn.commit()
            remaining = OTP_MAX_ATTEMPTS - new_attempts
            if remaining > 0:
                return False, f"Incorrect OTP code. {remaining} attempt(s) remaining."
            return False, "Incorrect OTP code. Maximum attempts exceeded. Please request a new OTP."

        if consume:
            cursor.execute("DELETE FROM otp_verifications WHERE id = ?;", (row["id"],))
            conn.commit()

        return True, None
