# Pro-Versed Production Security & Authentication Architecture

## 1. Executive Summary & Security Posture
The **Pro-Versed Authentication and Security Engine** implements a defense-in-depth security model engineered to protect academic, faculty, spoc, and industrial intellectual property against unauthorized access, credential stuffing, brute-force attacks, timing side-channels, and user enumeration.

---

## 2. Threat Model & Mitigations

| Threat | Attack Vector | Pro-Versed Mitigation |
| :--- | :--- | :--- |
| **Brute Force & Credential Stuffing** | Rapid automated password guessing | Sliding 1-hour rate limiting (max 10 attempts/hour) + 5-failure account lockout (3 hours). |
| **Timing Side-Channel Attacks** | Measuring response latency to detect valid emails vs non-existent accounts | `perform_dummy_verification()` computes full PBKDF2 hash on non-existent or invalid accounts, equalizing response time. |
| **User Enumeration** | Different error messages for "Email not found" vs "Incorrect password" | Generic, identical HTTP 401 response (`{"detail": "Invalid email or password. Please try again."}`) across all failure types. |
| **Session Hijacking & Fixation** | Stolen or predictable session identifiers | High-entropy 32-byte cryptographic tokens (`secrets.token_urlsafe(32)`), stored server-side with ISO 8601 UTC expirations and instant revocation. |
| **Cross-Site Scripting (XSS) & Clickjacking** | Malicious script execution / framing | Hardened security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`). |
| **Eavesdropping / Man-in-the-Middle** | Packet sniffing over untrusted networks | HTTPS enforcement via `Strict-Transport-Security` header, HttpOnly cookie flags, and Bearer token verification. |

---

## 3. Core Cryptographic Primitives

### 3.1 Password Hashing
- **Algorithm**: PBKDF2 (Password-Based Key Derivation Function 2)
- **Pseudorandom Function (PRF)**: HMAC-SHA256
- **Iteration Count**: 100,000 iterations (OWASP recommended minimum)
- **Salt**: 16 cryptographically secure random bytes generated per user via `secrets.token_bytes(16)`
- **Verification**: Constant-time byte comparison using `hmac.compare_digest()` to prevent CPU cache and timing leaks.

### 3.2 Dummy Hash Verification
To eliminate timing discrepancies between valid email lookups and non-existent users:
```python
DUMMY_SALT = b"\x00" * 16
DUMMY_HASH = hashlib.pbkdf2_hmac("sha256", b"dummy_password", DUMMY_SALT, 100_000)

def perform_dummy_verification(password: str) -> None:
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), DUMMY_SALT, 100_000)
    hmac.compare_digest(candidate, DUMMY_HASH)
```

---

## 4. Rate Limiting & Account Lockout Policies

### 4.1 Rate Limiting Architecture
- **Rule**: Maximum **10 login attempts per 1-hour window** (regardless of success or failure).
- **Enforcement**:
  - Sliding time window calculated from `login_attempts` table (`attempt_timestamp >= now - 3600s`).
  - Upon 11th attempt within 60 minutes: Returns **HTTP 429 Too Many Requests** with `Retry-After` header and remaining seconds.

### 4.2 Account Lockout Architecture
- **Rule**: After **5 consecutive failed login attempts**, the account is locked for **exactly 3 hours** (10,800 seconds).
- **Enforcement**:
  - Tracked in `account_security` table with `consecutive_failed_attempts` and `locked_until` (UTC ISO 8601 timestamp).
  - While locked: Returns **HTTP 423 Locked** with `remaining_lockout_seconds` and countdown metadata.
  - Automatic Expiration: When `datetime.now(timezone.utc) >= locked_until`, the account auto-unlocks and resets the failure counter to 0.
  - Successful Login Reset: Any valid authentication instantly resets `consecutive_failed_attempts = 0` and clears `locked_until`.

---

## 5. Session Management & Dual Authorization

### 5.1 Session Lifecycle
- **Token Generation**: 32-byte cryptographic random string (`secrets.token_urlsafe(32)`).
- **Storage**: Server-side `sessions` table mapping `session_id`, `user_id`, `created_at`, `expires_at`, `ip_address`, `user_agent`.
- **Duration**:
  - Standard session: 24 hours.
  - Remember-Me session: 30 days (720 hours).
- **Dual Client Transport**:
  1. `Authorization: Bearer <session_token>` header (for programmatic / SPA API calls).
  2. `session_token` cookie with `HttpOnly`, `SameSite=Lax`, and `Secure` flags.

### 5.2 Logout & Revocation
- Calling `POST /api/auth/logout` immediately deletes the session from the database and clears client-side cookies and storage.

---

## 6. Security Headers & Defense Middlewares

The FastAPI backend automatically injects the following security headers on all HTTP responses:
- `X-Content-Type-Options: nosniff` (Prevents MIME-type sniffing)
- `X-Frame-Options: DENY` (Mitigates Clickjacking attacks)
- `X-XSS-Protection: 1; mode=block` (Enforces legacy browser XSS filters)
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (Enforces HTTPS)
- `Referrer-Policy: strict-origin-when-cross-origin` (Protects sensitive URLs in referrer headers)

---

## 7. Frontend Security & Resiliency Pages

1. **Login View (`#view-login` / `/login`)**:
   - Modern glassmorphism UI with role persona quick-switchers.
   - Dynamic error banners with shake micro-animations.
   - Live lockout countdown timer (HH:MM:SS) that auto-unlocks upon expiry.
2. **Security Dashboard (`#view-dashboard` / `/dashboard`)**:
   - Protected route: Unauthenticated requests automatically redirect to `/login`.
   - Displays real-time session token viewer (with 1-click copy and masking), telemetry metrics, and security badges.
3. **404 & Diagnostics View (`#view-404` / `/404`)**:
   - Orbital animated 404 screen.
   - Live network connectivity indicator (ONLINE / OFFLINE).
   - Live API ping diagnostic tool measuring real-time latency.

---

## 8. Verification & Test Suite

The automated test suite in `tests/test_auth.py` contains 17 comprehensive test cases verifying:
- [x] Valid authentication & session creation
- [x] Wrong password handling with timing-safe comparison
- [x] Non-existent email handling with dummy verification
- [x] Uniform generic 401 error responses (zero information disclosure)
- [x] Consecutive failure tracking and 5-attempt threshold
- [x] 3-hour account lockout triggering and HTTP 423 status
- [x] Lockout automatic expiry after time elapses
- [x] Failure counter reset upon successful login
- [x] 10 attempts/hour sliding rate limit enforcement and HTTP 429 status
- [x] Rate limit sliding window expiration
- [x] Session validation and role extraction
- [x] Session revocation on logout
- [x] Protected dashboard route access control
- [x] Registration validation (email format, password complexity)
- [x] Security headers middleware injection
- [x] 404 route handling and diagnostic fallback

All 17 tests pass with 100% success rate.
