"""
security.py — coach authentication, sessions, and hardening.

Written because this app is going on a public URL and Coach mode holds other
people's health data. Until now every client endpoint was open: anyone who found
the address could read every client's weight history. That's the difference
between a laptop tool and a deployed one.

Design decisions and why:

**Fail closed.** If COACH_PASSWORD isn't set, coach endpoints return 503 with
setup instructions instead of being open. A missing config must never mean "no
lock on the door" — that's how the original version would have leaked.

**Server-side sessions, not signed cookies.** A dict of token → expiry. It means
a restart logs you out, which is a feature: there's no long-lived credential
floating around, and revoking everything is a restart. No JWT to get wrong.

**Rate-limited login.** One password protecting all client data is a brute-force
target the moment it's on the internet. Failed attempts per IP, with a lockout.

**No password in the database.** The secret lives in the environment. There's no
user table to leak, and rotating it is an env change plus a restart.

The public calculator stays completely open — it stores nothing and it's the
lead magnet. Only the routes that touch saved client data are gated.
"""

from __future__ import annotations

import os
import secrets
import time

from fastapi import HTTPException, Request, Response

# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------

COOKIE_NAME = "pnt_session"
SESSION_TTL_SECONDS = 12 * 60 * 60          # a working day, then log in again

# Brute-force protection. Deliberately strict: there is exactly one password and
# it guards medical-adjacent data, so a slow attacker should be stopped early.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
ATTEMPT_WINDOW_SECONDS = 15 * 60


def coach_password() -> str | None:
    """
    The coach password, from the environment.

    Returns None when unset, which callers treat as "coach mode not configured"
    and refuse — never as "no password needed".
    """
    pw = os.environ.get("COACH_PASSWORD", "").strip()
    return pw or None


def is_configured() -> bool:
    return coach_password() is not None


# ---------------------------------------------------------------------------
#  Sessions
# ---------------------------------------------------------------------------

# token -> expiry timestamp. In-memory on purpose: see the module docstring.
_sessions: dict[str, float] = {}


def _prune_sessions() -> None:
    now = time.time()
    for token in [t for t, exp in _sessions.items() if exp <= now]:
        _sessions.pop(token, None)


def create_session() -> tuple[str, int]:
    """Issue a session token. Returns (token, max_age_seconds)."""
    _prune_sessions()
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_TTL_SECONDS
    return token, SESSION_TTL_SECONDS


def destroy_session(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)


def session_valid(token: str | None) -> bool:
    if not token:
        return False
    expiry = _sessions.get(token)
    if expiry is None:
        return False
    if expiry <= time.time():
        _sessions.pop(token, None)
        return False
    return True



# ---------------------------------------------------------------------------
#  Login throttling
# ---------------------------------------------------------------------------

# ip -> (failure_count, first_failure_at, locked_until)
_attempts: dict[str, tuple[int, float, float]] = {}


def _client_ip(request: Request) -> str:
    """
    Best-effort client IP.

    Behind a reverse proxy (Render, Railway, nginx) the socket address is the
    proxy, so the forwarded header is the real client. Spoofable if the app is
    exposed directly — which is why this only ever *restricts* access and is
    never trusted for authorisation.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def lockout_remaining(request: Request) -> int:
    """Seconds until this IP may try again, or 0 if it's free to try."""
    ip = _client_ip(request)
    record = _attempts.get(ip)
    if not record:
        return 0
    _, _, locked_until = record
    remaining = locked_until - time.time()
    return int(remaining) if remaining > 0 else 0


def register_failure(request: Request) -> int:
    """Record a failed login. Returns attempts remaining before lockout."""
    ip = _client_ip(request)
    now = time.time()
    count, first_at, _ = _attempts.get(ip, (0, now, 0.0))

    # Old failures expire, so an honest typo months ago doesn't count.
    if now - first_at > ATTEMPT_WINDOW_SECONDS:
        count, first_at = 0, now

    count += 1
    locked_until = now + LOCKOUT_SECONDS if count >= MAX_FAILED_ATTEMPTS else 0.0
    _attempts[ip] = (count, first_at, locked_until)
    return max(0, MAX_FAILED_ATTEMPTS - count)


def clear_failures(request: Request) -> None:
    _attempts.pop(_client_ip(request), None)


def check_password(submitted: str) -> bool:
    """
    Compare in constant time.

    A plain `==` on strings can leak length and prefix through timing. The
    difference is small over a network but the fix is one function call.
    """
    expected = coach_password()
    if not expected:
        return False
    return secrets.compare_digest(submitted.encode(), expected.encode())


# ---------------------------------------------------------------------------
#  Cookies
# ---------------------------------------------------------------------------

def _https(request: Request) -> bool:
    """
    Is this request actually over HTTPS?

    Checked so the Secure flag can be set when deployed without breaking
    http://localhost during development. Hosting platforms terminate TLS at the
    proxy, so the forwarded header is what tells us.
    """
    if os.environ.get("PNT_FORCE_SECURE_COOKIE") == "1":
        return True
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return (proto or request.url.scheme) == "https"


def set_session_cookie(response: Response, request: Request,
                       token: str, max_age: int) -> None:
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=max_age,
        httponly=True,                  # JavaScript can't read it, so XSS can't steal it
        samesite="lax",                 # blocks cross-site request forgery on state changes
        secure=_https(request),         # never sent over plain HTTP once deployed
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


# ---------------------------------------------------------------------------
#  The dependency that guards coach routes
# ---------------------------------------------------------------------------

NOT_CONFIGURED_MESSAGE = (
    "Coach mode is locked because no password is set. This is deliberate — it "
    "holds client health data, so it refuses to run unprotected. Set the "
    "COACH_PASSWORD environment variable and restart:\n\n"
    '    COACH_PASSWORD="something-long-and-unique" uvicorn app.main:app\n\n'
    "The public calculator works without it."
)


def require_coach(request: Request) -> None:
    """
    FastAPI dependency. Attach to every route that reads or writes client data.

    Three outcomes:
      503 — no password configured (fail closed, with setup instructions)
      401 — not logged in, or the session expired
      pass through — valid session
    """
    if not is_configured():
        raise HTTPException(503, NOT_CONFIGURED_MESSAGE)

    token = request.cookies.get(COOKIE_NAME)
    if not session_valid(token):
        raise HTTPException(401, "Please log in to Coach mode.")


# ---------------------------------------------------------------------------
#  Response hardening
# ---------------------------------------------------------------------------

# Client intake links carry an unguessable token in the URL. Without a referrer
# policy that token would be sent to any external site linked from the page —
# and the citation links go to pubmed, WHO and the rest. This stops the leak.
SECURITY_HEADERS = {
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Fonts come from Google; everything else is same-origin. 'unsafe-inline' is
    # needed because the pages use inline styles and event-free inline scripts —
    # tightening that would mean a build step, which this project deliberately
    # avoids.
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


def apply_security_headers(response: Response) -> None:
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)


def no_store(response: Response) -> None:
    """
    Stop caches keeping client health data.

    Applied to coach and intake responses. Without it a shared or proxy cache
    could hold someone's measurements after logout.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
