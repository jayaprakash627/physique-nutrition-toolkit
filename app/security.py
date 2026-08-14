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

**Server-side sessions, not signed cookies.** Token → expiry, held in the
database. No JWT to get wrong, and revoking every session is one DELETE.

These used to live in a module-level dict, and the docstring here argued that
losing them on restart was a feature: no long-lived credential floating around.
That argument was made on a laptop. In production the host sleeps after ~15 idle
minutes, so "logged out on restart" meant logged out almost every time the coach
opened the app — and a security property that makes people dread logging in is
one they will work around. What's stored is a **SHA-256 of the token**, never the
token, so the table is useless to anyone who reads it: hashes can't be replayed
as cookies. Revocation is still cheap and expiry is still enforced server-side.

**Rate-limited login.** One password protecting all client data is a brute-force
target the moment it's on the internet. Failed attempts per IP, with a lockout.

**No password in the database.** The secret lives in the environment. There's no
user table to leak, and rotating it is an env change plus a restart.

The public calculator stays completely open — it stores nothing and it's the
lead magnet. Only the routes that touch saved client data are gated.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response

from . import db

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

def _fingerprint(token: str) -> str:
    """
    What gets stored instead of the token.

    Plain SHA-256 with no salt or stretching, deliberately. Those defend against
    guessing a low-entropy secret; this token is 32 bytes from `secrets`, so
    there is nothing to guess and a slow hash would only add latency to every
    authenticated request. The job here is narrow: make the stored row useless if
    someone reads the table.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_session() -> tuple[str, int]:
    """Issue a session token. Returns (token, max_age_seconds)."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)
    db.session_create(_fingerprint(token), expires.isoformat(timespec="seconds"))
    # Housekeeping on the cold path. Logins are rare; validation happens on every
    # request, and that is not the place to be deleting rows.
    db.session_prune()
    return token, SESSION_TTL_SECONDS


def destroy_session(token: str | None) -> None:
    """
    Log out.

    Failures are swallowed on purpose. The caller clears the cookie regardless,
    so the session is unusable from the browser either way, and a logout button
    that can return an error is a logout button people stop trusting. The row is
    expiry-bounded and gets pruned on the next login.
    """
    if not token:
        return
    try:
        db.session_delete(_fingerprint(token))
    except Exception:                             # noqa: BLE001
        pass


def session_valid(token: str | None) -> bool:
    """
    Is this cookie a live session?

    Fails closed. If the database can't be reached the answer is False, not an
    exception — an unreachable store must read as "not authenticated" rather than
    surfacing a 500 from inside the auth check, and a coach who can't reach the
    database has nothing to read anyway.
    """
    if not token:
        return False
    try:
        return db.session_live(_fingerprint(token))
    except Exception:                             # noqa: BLE001
        return False



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
