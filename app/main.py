"""
main.py — the FastAPI server.

Thin by design. Every endpoint validates with a Pydantic model, calls into
`engine.py` or `db.py`, and returns the result. No calculation and no nutrition
content lives here — that way the interesting logic stays testable without
starting a server, and this file stays readable as a map of the API.

Endpoints
    GET   /                              the app UI
    GET   /api/meta                      dropdown options, disclaimers, food DB
    GET   /api/sources                   the full citation registry
    GET   /api/micronutrients            the reference panel, no client needed

    POST  /api/assess                    the main assessment (everything)
    POST  /api/bodyfat                   body-fat method comparison only
    POST  /api/prep-plan                 contest / goal prep planner
    POST  /api/strength                  1RM, % table, DOTS/Wilks

    GET   /api/clients                   list saved clients
    POST  /api/clients                   create a client
    GET   /api/clients/{id}              one client + measurements + progress
    PUT   /api/clients/{id}              update a client
    DELETE /api/clients/{id}             delete a client (cascades)
    POST  /api/clients/{id}/measurements add a measurement
    DELETE /api/measurements/{id}        delete a measurement

    POST  /api/reports                   save an assessment snapshot
    GET   /api/reports                   list snapshots (optional ?client_id=)
    GET   /api/reports/{id}              load one snapshot
    DELETE /api/reports/{id}             delete a snapshot

Run it with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, engine
from . import formulas as f
from .knowledge import foods, micronutrients, sources
from .models import (
    AssessmentIn,
    BodyfatIn,
    ClientIn,
    MeasurementIn,
    PrepPlanIn,
    StrengthIn,
)

app = FastAPI(
    title="Physique & Nutrition Coaching Toolkit",
    description=(
        "Evidence-based physique and nutrition calculations that explain "
        "themselves. Every number returns with the physiology behind it, what "
        "goes wrong at too little or too much, real food portions to hit it, and "
        "the published standard it came from."
    ),
    version="1.0.0",
)

db.init_db()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


@app.exception_handler(sqlite3.Error)
def sqlite_error_handler(request: Request, exc: sqlite3.Error):
    """
    Turn a database failure into something the user can act on.

    `db()` now recreates a missing schema on its own, so this should be rare —
    but "Request failed (500)" tells nobody anything. A disk-full error, a
    read-only file, or a locked database all deserve a message that names the
    file and says what to try.
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
#  UI
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ---------------------------------------------------------------------------
#  Reference data — everything the frontend needs to build its forms
# ---------------------------------------------------------------------------

@app.get("/api/meta")
def meta():
    """
    One call that gives the frontend every option list and every disclaimer.

    Keeping these server-side means the labels ("Moderate — training 3–5
    days/week") are defined once, next to the factor they describe, instead of
    being duplicated in the HTML and drifting out of sync.
    """
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
    """The full citation registry — every standard this app leans on."""
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
    """
    The micronutrient panel with no client context — a plain reference table.

    The personalised, risk-ordered version comes back inside /api/assess.
    """
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


# ---------------------------------------------------------------------------
#  Calculators
# ---------------------------------------------------------------------------

@app.post("/api/assess")
def assess(payload: AssessmentIn):
    """
    The main event: a complete assessment with every explanation attached.

    Needs enough measurement data to estimate body fat — girths, skinfolds, or a
    figure you already know. Deurenberg can run on height/weight/age alone, so
    this rarely fails, but the error message says what to add if it does.
    """
    try:
        return engine.assess(payload.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/bodyfat")
def bodyfat(payload: BodyfatIn):
    """Body-fat methods compared, with the spread and what to trust."""
    data = payload.model_dump()
    # bodyfat_report reads these keys; supply the defaults it expects.
    data.setdefault("bodyfat_pct", None)
    return engine.bodyfat_report(data)


@app.post("/api/prep-plan")
def prep_plan(payload: PrepPlanIn):
    """Contest / goal prep planner — week-by-week, with a verdict on the rate."""
    return engine.prep_report(payload.model_dump())


@app.post("/api/strength")
def strength(payload: StrengthIn):
    """1RM estimate, % of 1RM loading table, and DOTS/Wilks if a total is given."""
    return engine.strength_report(payload.model_dump())


# ---------------------------------------------------------------------------
#  Clients
# ---------------------------------------------------------------------------

@app.get("/api/clients")
def clients():
    return {"clients": db.list_clients()}


@app.post("/api/clients", status_code=201)
def create_client(payload: ClientIn):
    return db.create_client(payload.model_dump())


@app.get("/api/clients/{client_id}")
def client_detail(client_id: int):
    """One client, with their full measurement history and progress summary."""
    c = db.get_client(client_id)
    if not c:
        raise HTTPException(404, "Client not found")
    return {
        "client": c,
        "measurements": db.list_measurements(client_id),
        "progress": db.progress_summary(client_id),
        "reports": db.list_reports(client_id),
    }


@app.put("/api/clients/{client_id}")
def update_client(client_id: int, payload: ClientIn):
    updated = db.update_client(client_id, payload.model_dump())
    if not updated:
        raise HTTPException(404, "Client not found")
    return updated


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int):
    if not db.delete_client(client_id):
        raise HTTPException(404, "Client not found")
    return {"deleted": client_id}


@app.post("/api/clients/{client_id}/measurements", status_code=201)
def add_measurement(client_id: int, payload: MeasurementIn):
    if not db.get_client(client_id):
        raise HTTPException(404, "Client not found")
    return db.add_measurement(client_id, payload.model_dump())


@app.delete("/api/measurements/{measurement_id}")
def delete_measurement(measurement_id: int):
    if not db.delete_measurement(measurement_id):
        raise HTTPException(404, "Measurement not found")
    return {"deleted": measurement_id}


# ---------------------------------------------------------------------------
#  Saved reports
# ---------------------------------------------------------------------------

@app.post("/api/reports", status_code=201)
def save_report(payload: AssessmentIn, client_id: int | None = None):
    """
    Run an assessment and snapshot it.

    Stores the full report including the explanation wording, so a summary handed
    to a client six months ago still reads exactly as it did then — even after the
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


@app.get("/api/reports")
def list_reports(client_id: int | None = None):
    return {"reports": db.list_reports(client_id)}


@app.get("/api/reports/{report_id}")
def get_report(report_id: int):
    r = db.get_report(report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    return r


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: int):
    if not db.delete_report(report_id):
        raise HTTPException(404, "Report not found")
    return {"deleted": report_id}


# ---------------------------------------------------------------------------
#  Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """Liveness check plus a count of what's loaded, useful after a deploy."""
    return {
        "status": "ok",
        "sources_loaded": len(sources.SOURCES),
        "micronutrients_loaded": len(micronutrients.MICRONUTRIENTS),
        "foods_loaded": len(foods.ALL_FOODS),
    }


# Mounted last so it doesn't shadow the API routes above.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
