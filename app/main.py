"""
main.py — the FastAPI server.

Thin by design. Every endpoint validates with a Pydantic model, calls into
`engine.py`, `intake.py` or `db.py`, and returns the result. No calculation and
no nutrition content lives here.

Three surfaces, three levels of access:

  **Public** — the calculator. Open, stores nothing. It's the lead magnet, and
  the honest disclaimers it carries are what make a coach look worth hiring.

  **Token-gated** — client onboarding at /start/<token>. No login, because a new
  client shouldn't have to make an account to fill in a form. Privacy comes from
  the token being unguessable and single-use.

  **Coach-only** — everything that reads or writes saved client data. Requires a
  session. Fails closed if no password is configured.

That middle tier is the part worth being careful about: it's reachable by anyone
holding a link, so it validates hard and it's the only public write path.

Run it with:
    COACH_PASSWORD="…" uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, engine, intake, security
from . import formulas as f
from .knowledge import foods, micronutrients, sources
from .models import (
    AssessmentIn,
    BodyfatIn,
    ClientIn,
    IntakeIn,
    InviteIn,
    LoginIn,
    MeasurementIn,
    PrepPlanIn,
    StrengthIn,
)

app = FastAPI(
    title="Physique & Nutrition Coaching Toolkit",
    description=(
        "Evidence-based physique and nutrition calculations that explain "
        "themselves, plus a private client onboarding and tracking workspace."
    ),
    version="2.0.0",
)

db.init_db()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

# Paths whose responses must never be cached — they carry client health data.
PRIVATE_PREFIXES = ("/api/clients", "/api/measurements", "/api/reports",
                    "/api/invites", "/api/intakes", "/api/intake", "/start")


@app.middleware("http")
async def harden(request: Request, call_next):
    """
    Apply security headers to every response.

    The Referrer-Policy matters more than usual here: intake URLs carry a secret
    token, and the pages link out to PubMed, WHO and other citation sources.
    Without it, that token would be handed to every one of them in the Referer
    header.
    """
    response = await call_next(request)
    security.apply_security_headers(response)
    if request.url.path.startswith(PRIVATE_PREFIXES):
        security.no_store(response)
    return response


@app.exception_handler(sqlite3.Error)
def sqlite_error_handler(request: Request, exc: sqlite3.Error):
    """
    Turn a database failure into something actionable.

    `db()` recreates a missing schema on its own, so this should be rare — but
    "Request failed (500)" tells nobody anything. A disk-full error, a read-only
    file or a locked database each deserve a message naming the file.
    """
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                f"Couldn't reach the database ({exc}). The store is a single "
                f"file at {os.path.abspath(db.DB_PATH)} — check it exists and is "
                "writable, then reload. Your saved clients live in that file, so "
                "if it's been moved, put it back rather than starting fresh."
            )
        },
    )


# ---------------------------------------------------------------------------
#  Pages
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/start/{token}", include_in_schema=False)
def onboarding_page(token: str):
    """
    The client onboarding page.

    Serves the same static page whatever the token's state, and lets the page ask
    the API about it. That keeps the HTML static and cacheable, and means an
    expired or already-used link gets a friendly explanation instead of a 404 the
    client would read as "he sent me a broken link".
    """
    return FileResponse(os.path.join(STATIC_DIR, "start.html"))


# ---------------------------------------------------------------------------
#  COACH AUTH
# ---------------------------------------------------------------------------

@app.get("/api/session")
def session_status(request: Request):
    """
    Is the coach logged in? Used by the UI to decide between the login form and
    the workspace. Safe to call unauthenticated — it only ever reports state.
    """
    token = request.cookies.get(security.COOKIE_NAME)
    return {
        "configured": security.is_configured(),
        "logged_in": security.session_valid(token),
        "setup_hint": None if security.is_configured() else security.NOT_CONFIGURED_MESSAGE,
    }


@app.post("/api/login")
def login(payload: LoginIn, request: Request, response: Response):
    """
    Log the coach in.

    Rate-limited per IP: one password guards every client's health data, so an
    unthrottled login form on a public URL is an open invitation. The error
    messages deliberately don't distinguish "wrong password" from anything else
    beyond what's useful to a legitimate user.
    """
    if not security.is_configured():
        raise HTTPException(503, security.NOT_CONFIGURED_MESSAGE)

    locked = security.lockout_remaining(request)
    if locked:
        raise HTTPException(
            429,
            f"Too many failed attempts. Try again in {locked // 60 + 1} minute(s).",
        )

    if not security.check_password(payload.password):
        remaining = security.register_failure(request)
        if remaining:
            raise HTTPException(401, f"Incorrect password. {remaining} attempt(s) left.")
        raise HTTPException(429, "Too many failed attempts. Locked for 15 minutes.")

    security.clear_failures(request)
    token, max_age = security.create_session()
    security.set_session_cookie(response, request, token, max_age)
    return {"logged_in": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    security.destroy_session(request.cookies.get(security.COOKIE_NAME))
    security.clear_session_cookie(response)
    return {"logged_in": False}


# ---------------------------------------------------------------------------
#  PUBLIC reference data & calculators — open, and they store nothing
# ---------------------------------------------------------------------------

@app.get("/api/meta")
def meta():
    """Every option list and disclaimer the frontend needs, defined once here."""
    return {
        "activity_levels": f.ACTIVITY_LEVELS,
        "goals": {
            "cut": "Cut — lose fat (20% deficit)",
            "aggressive_cut": "Aggressive cut — faster, with trade-offs (25% deficit)",
            "maintain": "Maintain — hold weight, train and recover",
            "bulk": "Lean bulk — build muscle (10% surplus)",
        },
        "diets": {
            "omnivore": "Omnivore — everything",
            "eggetarian": "Eggetarian — no meat or fish, eggs and dairy fine",
            "vegetarian": "Vegetarian — no meat, fish or egg; dairy fine",
            "vegan": "Vegan — no animal products at all",
        },
        "climates": {
            "temperate": "Temperate — mild, air-conditioned most of the day",
            "warm": "Warm — 25–30°C",
            "hot": "Hot — 30–38°C (most of India, most of the year)",
            "very_hot": "Very hot / humid — above 38°C, or high humidity",
        },
        "bodyfat_bands": f.BODYFAT_BANDS,
        "bodyfat_floors": f.SAFE_BODYFAT_FLOOR,
        "measurement_help": {
            "girths": {
                "neck": "Just below the larynx, tape sloping slightly down at the front",
                "waist": "Men: at the navel. Women: at the narrowest point. Relaxed, end of a normal exhale",
                "hip": "Widest point of the glutes — required for the Navy method in women",
            },
            "skinfolds": {
                "chest": "Diagonal fold, halfway between nipple and armpit",
                "abdomen": "Vertical fold, 2 cm to the right of the navel",
                "thigh": "Vertical fold, midway between hip and knee cap, front of thigh",
                "triceps": "Vertical fold, back of the arm, midway between shoulder and elbow",
                "suprailiac": "Diagonal fold, just above the hip bone",
                "subscapular": "Diagonal fold, just below the shoulder blade",
                "midaxillary": "Vertical fold, on the mid-line of the side of the torso",
            },
            "technique": (
                "Consistency beats precision. Same person, same sites, same time "
                "of day — ideally morning, before eating, after using the "
                "bathroom. A trend measured the same way every time is real "
                "information; a single reading is not."
            ),
        },
        "foods": {
            "protein": foods.PROTEIN_FOODS,
            "carbs": foods.CARB_FOODS,
            "fats": foods.FAT_FOODS,
            "fibre": foods.FIBRE_FOODS,
        },
        "pct_1rm_table": f.PCT_1RM_TABLE,
        "disclaimer": sources.DISCLAIMER,
        "safeguarding": sources.SAFEGUARDING_NOTE,
    }


@app.get("/api/sources")
def all_sources():
    return {
        "sources": [{"key": k, **v} for k, v in sources.SOURCES.items()],
        "count": len(sources.SOURCES),
        "note": (
            "Every number this toolkit produces traces back to one of these. If a "
            "figure here disagrees with your dietitian, this list is what makes "
            "that conversation possible — check the standard, not the calculator."
        ),
    }


@app.get("/api/micronutrients")
def micronutrient_reference(sex: str = "male"):
    if sex not in ("male", "female"):
        raise HTTPException(400, "sex must be 'male' or 'female'")
    panel = micronutrients.panel_for([], sex)
    for row in panel:
        row["sources"] = sources.resolve(*row["source_keys"])
    return {
        "panel": panel,
        "risk_definitions": micronutrients.RISK_DEFINITIONS,
        "sex": sex,
    }


@app.post("/api/assess")
def assess(payload: AssessmentIn):
    """The main assessment. Public and stateless — nothing is stored."""
    try:
        return engine.assess(payload.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/bodyfat")
def bodyfat(payload: BodyfatIn):
    data = payload.model_dump()
    data.setdefault("bodyfat_pct", None)
    return engine.bodyfat_report(data)


@app.post("/api/prep-plan")
def prep_plan(payload: PrepPlanIn):
    return engine.prep_report(payload.model_dump())


@app.post("/api/strength")
def strength(payload: StrengthIn):
    return engine.strength_report(payload.model_dump())


# ---------------------------------------------------------------------------
#  CLIENT ONBOARDING — token-gated, no login
#
#  The only public write path in the app, so it validates hard.
# ---------------------------------------------------------------------------

INVITE_STATE_MESSAGES = {
    "missing": "This link isn't valid. Please ask your coach for a new one.",
    "revoked": "This link has been cancelled. Please ask your coach for a new one.",
    "used": "This form has already been filled in. If you need to change an "
            "answer, message your coach — there's no need to fill it in again.",
    "expired": "This link has expired. Ask your coach for a fresh one — it only "
               "takes them a moment.",
}


@app.get("/api/intake/{token}")
def intake_schema(token: str):
    """
    The questionnaire for one invite link.

    Returns the invite's state so the page can explain a dead link in plain words
    rather than showing a form that will fail on submit. Deliberately reveals
    nothing about the coach or other clients — an attacker with a random token
    learns only that it isn't valid.
    """
    invite = db.get_invite_by_token(token)
    state = db.invite_state(invite)

    if state != "ok":
        return {
            "usable": False,
            "state": state,
            "message": INVITE_STATE_MESSAGES.get(state, INVITE_STATE_MESSAGES["missing"]),
        }

    return {
        "usable": True,
        "state": "ok",
        "sections": intake.SECTIONS,
        "consent": intake.CONSENT,
        "intro": {
            "heading": "Let's build your plan properly",
            "body": (
                "These questions take about eight minutes. They go further than a "
                "typical trainer's form on purpose — the more I know about how you "
                "actually live, the less of your plan is guesswork.\n\n"
                "Every question explains why I'm asking. Nothing here is "
                "compulsory except the few marked required, and \"I don't know\" "
                "is a perfectly good answer."
            ),
        },
        # Shown before they start, because handing over health information to a
        # web form deserves an upfront answer about what happens to it.
        "privacy_summary": (
            "Your answers go only to your coach, are stored privately, and are "
            "never sold or shared. You can ask for a copy or ask for them to be "
            "deleted at any time."
        ),
    }


@app.post("/api/intake/{token}")
def submit_intake(token: str, payload: IntakeIn):
    """
    Accept a submission and burn the link.

    Required fields are checked against `intake.SECTIONS` rather than a Pydantic
    model, so the questionnaire stays defined in one place — see IntakeIn for the
    reasoning.
    """
    invite = db.get_invite_by_token(token)
    state = db.invite_state(invite)
    if state != "ok":
        raise HTTPException(
            410 if state in ("used", "expired", "revoked") else 404,
            INVITE_STATE_MESSAGES.get(state, INVITE_STATE_MESSAGES["missing"]),
        )

    answers = payload.answers
    missing = [
        field["key"] for field in intake.flatten_fields()
        if field.get("required")
        and not str(answers.get(field["key"], "") or "").strip()
    ]
    if missing:
        labels = {fi["key"]: fi["label"] for fi in intake.flatten_fields()}
        raise HTTPException(
            422,
            "Please fill in: " + ", ".join(labels.get(k, k) for k in missing),
        )

    db.create_intake(
        invite_id=invite["id"],
        answers=answers,
        consent_version=intake.CONSENT_VERSION,
    )

    # What the client sees immediately: proof their answers were read, and the
    # reason to have the conversation. Deliberately no calorie or macro numbers —
    # those are the coaching deliverable.
    return {
        "received": True,
        "closing": intake.closing_message(answers),
        "priorities": intake.derive_priorities(answers),
    }


# ---------------------------------------------------------------------------
#  COACH: invite links
# ---------------------------------------------------------------------------

@app.post("/api/invites", status_code=201, dependencies=[Depends(security.require_coach)])
def create_invite(payload: InviteIn, request: Request):
    """
    Mint an onboarding link to send a client.

    The absolute URL is built from the request so it's correct whether you're on
    localhost or a deployed domain — no base-URL config to forget.
    """
    invite = db.create_invite(payload.label, payload.ttl_days)
    base = str(request.base_url).rstrip("/")
    return {**invite, "url": f"{base}/start/{invite['token']}"}


@app.get("/api/invites", dependencies=[Depends(security.require_coach)])
def list_invites(request: Request):
    base = str(request.base_url).rstrip("/")
    return {
        "invites": [
            {**inv, "url": f"{base}/start/{inv['token']}"} for inv in db.list_invites()
        ]
    }


@app.post("/api/invites/{invite_id}/revoke", dependencies=[Depends(security.require_coach)])
def revoke_invite(invite_id: int):
    if not db.revoke_invite(invite_id):
        raise HTTPException(404, "Link not found, or already cancelled.")
    return {"revoked": invite_id}


@app.delete("/api/invites/{invite_id}", dependencies=[Depends(security.require_coach)])
def delete_invite(invite_id: int):
    if not db.delete_invite(invite_id):
        raise HTTPException(404, "Link not found")
    return {"deleted": invite_id}


# ---------------------------------------------------------------------------
#  COACH: submitted intakes
# ---------------------------------------------------------------------------

@app.get("/api/intakes", dependencies=[Depends(security.require_coach)])
def list_intakes():
    return {"intakes": db.list_intakes()}


@app.get("/api/intakes/{intake_id}", dependencies=[Depends(security.require_coach)])
def get_intake(intake_id: int):
    """One submission, with the coach-facing read of it."""
    row = db.get_intake(intake_id)
    if not row:
        raise HTTPException(404, "Submission not found")
    return {
        **row,
        "priorities": intake.derive_priorities(row["answers"]),
        "sections": intake.SECTIONS,      # so the UI can label answers properly
    }


@app.get("/api/intakes/{intake_id}/csv", dependencies=[Depends(security.require_coach)])
def export_intake_csv(intake_id: int):
    """
    Download one submission as CSV.

    Two real uses: handing a client's answers to a dietitian or doctor when the
    health section says you should, and giving the client a copy of their own data
    if they ask for one — which the consent screen promises.
    """
    row = db.get_intake(intake_id)
    if not row:
        raise HTTPException(404, "Submission not found")

    csv_text = intake.to_csv(row["answers"], meta={
        "Submitted": row.get("created_at") or "",
        "Consent recorded": row.get("consent_at") or "",
        "Consent version": row.get("consent_version") or "",
    })

    # A filename built from the client's name, stripped to characters that are
    # safe in a Content-Disposition header and on every filesystem.
    raw_name = (row.get("full_name") or f"intake-{intake_id}")
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "" for ch in raw_name).strip()
    safe = (safe.replace(" ", "-") or f"intake-{intake_id}")[:40]

    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}-intake.csv"',
            # This is somebody's health data leaving the app — never cache it.
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/intakes/{intake_id}/convert", status_code=201,
          dependencies=[Depends(security.require_coach)])
def convert_intake(intake_id: int):
    """
    Turn a submission into a tracked client.

    Saves the coach re-typing what the client already told us, and links the two
    so the questionnaire stays reachable from the client record.
    """
    row = db.get_intake(intake_id)
    if not row:
        raise HTTPException(404, "Submission not found")
    if row.get("client_id"):
        raise HTTPException(409, "This submission is already linked to a client.")

    a = row["answers"]

    def num(key, default):
        try:
            return float(a.get(key) or default)
        except (TypeError, ValueError):
            return default

    # The intake offers "recomp" as a goal; the planner has no such mode, so it
    # maps to maintain — that is genuinely what recomposition eats at.
    goal = a.get("goal") if a.get("goal") in ("cut", "maintain", "bulk") else "maintain"

    client = db.create_client({
        "name": (a.get("full_name") or "Unnamed client").strip()[:80],
        "sex": a.get("sex") if a.get("sex") in ("male", "female") else "male",
        "age": int(num("age", 30)),
        "height_cm": num("height_cm", 170),
        "diet": a.get("diet") if a.get("diet") in
                ("omnivore", "eggetarian", "vegetarian", "vegan") else "omnivore",
        "goal": goal,
        "notes": f"Created from onboarding form #{intake_id}. Contact: "
                 f"{a.get('contact') or '—'}",
    })
    db.link_intake_to_client(intake_id, client["id"])

    # Their starting weight is already known, so seed the tracking series with it
    # rather than making the coach type it again.
    weight = num("weight_kg", 0)
    if weight:
        from datetime import date
        db.add_measurement(client["id"], {
            "taken_on": date.today().isoformat(),
            "weight_kg": weight,
            "note": "From onboarding form",
        })

    return {"client": client, "intake_id": intake_id}


@app.delete("/api/intakes/{intake_id}", dependencies=[Depends(security.require_coach)])
def delete_intake(intake_id: int):
    """Hard delete — this is how a client's right to erasure is honoured."""
    if not db.delete_intake(intake_id):
        raise HTTPException(404, "Submission not found")
    return {"deleted": intake_id}


# ---------------------------------------------------------------------------
#  COACH: clients
# ---------------------------------------------------------------------------

@app.get("/api/clients", dependencies=[Depends(security.require_coach)])
def clients():
    return {"clients": db.list_clients()}


@app.post("/api/clients", status_code=201, dependencies=[Depends(security.require_coach)])
def create_client(payload: ClientIn):
    return db.create_client(payload.model_dump())


@app.get("/api/clients/{client_id}", dependencies=[Depends(security.require_coach)])
def client_detail(client_id: int):
    c = db.get_client(client_id)
    if not c:
        raise HTTPException(404, "Client not found")
    return {
        "client": c,
        "measurements": db.list_measurements(client_id),
        "progress": db.progress_summary(client_id),
        "reports": db.list_reports(client_id),
    }


@app.put("/api/clients/{client_id}", dependencies=[Depends(security.require_coach)])
def update_client(client_id: int, payload: ClientIn):
    updated = db.update_client(client_id, payload.model_dump())
    if not updated:
        raise HTTPException(404, "Client not found")
    return updated


@app.delete("/api/clients/{client_id}", dependencies=[Depends(security.require_coach)])
def delete_client(client_id: int):
    if not db.delete_client(client_id):
        raise HTTPException(404, "Client not found")
    return {"deleted": client_id}


@app.post("/api/clients/{client_id}/measurements", status_code=201,
          dependencies=[Depends(security.require_coach)])
def add_measurement(client_id: int, payload: MeasurementIn):
    if not db.get_client(client_id):
        raise HTTPException(404, "Client not found")
    return db.add_measurement(client_id, payload.model_dump())


@app.delete("/api/measurements/{measurement_id}",
            dependencies=[Depends(security.require_coach)])
def delete_measurement(measurement_id: int):
    if not db.delete_measurement(measurement_id):
        raise HTTPException(404, "Measurement not found")
    return {"deleted": measurement_id}


# ---------------------------------------------------------------------------
#  COACH: saved reports
# ---------------------------------------------------------------------------

@app.post("/api/reports", status_code=201, dependencies=[Depends(security.require_coach)])
def save_report(payload: AssessmentIn, client_id: int | None = None):
    """
    Run an assessment and snapshot it.

    Stores the full report including the explanation wording, so a summary handed
    to a client six months ago still reads exactly as it did then, even after the
    knowledge base has been updated.
    """
    if client_id is not None and not db.get_client(client_id):
        raise HTTPException(404, "Client not found")
    try:
        report = engine.assess(payload.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    saved = db.save_report(client_id, report)
    return {**saved, "report": report}


@app.get("/api/reports", dependencies=[Depends(security.require_coach)])
def list_reports(client_id: int | None = None):
    return {"reports": db.list_reports(client_id)}


@app.get("/api/reports/{report_id}", dependencies=[Depends(security.require_coach)])
def get_report(report_id: int):
    r = db.get_report(report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    return r


@app.delete("/api/reports/{report_id}", dependencies=[Depends(security.require_coach)])
def delete_report(report_id: int):
    if not db.delete_report(report_id):
        raise HTTPException(404, "Report not found")
    return {"deleted": report_id}


# ---------------------------------------------------------------------------
#  Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """
    Liveness plus a deployment self-check.

    `coach_mode_locked` is the one to watch after deploying: if it's false you've
    published client health data with no password on it.
    """
    return {
        "status": "ok",
        "sources_loaded": len(sources.SOURCES),
        "micronutrients_loaded": len(micronutrients.MICRONUTRIENTS),
        "foods_loaded": len(foods.ALL_FOODS),
        "intake_questions": len(intake.flatten_fields()),
        "coach_mode_configured": security.is_configured(),
        "coach_mode_locked": security.is_configured(),
    }


# Mounted last so it doesn't shadow the API routes above.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
