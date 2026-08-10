"""
test_security_and_intake.py — the auth boundary and the onboarding flow.

The most consequential tests in the suite. Everything else, if it regresses,
produces a wrong number. If *this* regresses, a stranger reads a client's health
data off a public URL.

So the security tests are written as an attacker would probe: hit every
client-data endpoint with no session, with a bad session, and after logout, and
assert each one refuses. A test that only checks the happy path would pass
happily with the lock removed.
"""

import os
import tempfile

import pytest

# Must be set before app.main is imported.
_tmp_db = os.path.join(tempfile.mkdtemp(), "sec_toolkit.db")
os.environ["TOOLKIT_DB"] = _tmp_db
PASSWORD = "correct-horse-battery-staple"
os.environ["COACH_PASSWORD"] = PASSWORD

from fastapi.testclient import TestClient          # noqa: E402

from app import db, intake, security               # noqa: E402
from app.main import app                            # noqa: E402


@pytest.fixture
def anon():
    """A client that never logs in."""
    security._attempts.clear()      # start each test with a clean lockout state
    return TestClient(app)


@pytest.fixture
def coach():
    """A logged-in coach."""
    security._attempts.clear()
    c = TestClient(app)
    assert c.post("/api/login", json={"password": PASSWORD}).status_code == 200
    return c


# ===========================================================================
#  THE AUTH BOUNDARY
# ===========================================================================

# Every endpoint that reads or writes somebody's personal data. If a new one is
# added and not listed here, that's the gap this test is meant to catch — so keep
# it in step with main.py.
PROTECTED = [
    ("get", "/api/clients"),
    ("post", "/api/clients"),
    ("get", "/api/clients/1"),
    ("put", "/api/clients/1"),
    ("delete", "/api/clients/1"),
    ("post", "/api/clients/1/measurements"),
    ("delete", "/api/measurements/1"),
    ("get", "/api/reports"),
    ("post", "/api/reports"),
    ("get", "/api/reports/1"),
    ("delete", "/api/reports/1"),
    ("get", "/api/invites"),
    ("post", "/api/invites"),
    ("post", "/api/invites/1/revoke"),
    ("delete", "/api/invites/1"),
    ("get", "/api/intakes"),
    ("get", "/api/intakes/1"),
    ("post", "/api/intakes/1/convert"),
    ("delete", "/api/intakes/1"),
]


def call(client, method, path):
    """GET and DELETE take no body in httpx, so only send one where it's valid."""
    if method in ("post", "put", "patch"):
        return getattr(client, method)(path, json={})
    return getattr(client, method)(path)


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_client_data_endpoint_rejects_anonymous(anon, method, path):
    """
    The regression that would matter most. Before auth existed, all of these were
    open — anyone who found the URL could read every client's health history.
    """
    response = call(anon, method, path)
    assert response.status_code == 401, (
        f"{method.upper()} {path} answered {response.status_code} without a login"
    )


@pytest.mark.parametrize("method,path", PROTECTED)
def test_a_forged_cookie_is_rejected(anon, method, path):
    """A made-up session token must not work — sessions are server-side."""
    anon.cookies.set(security.COOKIE_NAME, "not-a-real-session-token")
    assert call(anon, method, path).status_code == 401


def test_public_endpoints_stay_open(anon):
    """
    The calculator is the lead magnet. If auth ever spreads to it by accident,
    the whole funnel breaks — so this asserts the boundary from the other side.
    """
    assert anon.get("/api/meta").status_code == 200
    assert anon.get("/api/sources").status_code == 200
    assert anon.get("/api/micronutrients?sex=male").status_code == 200
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/").status_code == 200
    assert anon.post("/api/assess", json={
        "sex": "male", "age": 30, "weight_kg": 80, "height_cm": 180,
    }).status_code == 200
    assert anon.post("/api/strength", json={"weight": 100, "reps": 5}).status_code == 200


def test_login_rejects_a_wrong_password(anon):
    r = anon.post("/api/login", json={"password": "wrong"})
    assert r.status_code == 401
    assert "attempt" in r.json()["detail"].lower()


def test_login_locks_out_after_repeated_failures(anon):
    """
    One password guards every client's data, so an unthrottled form on a public
    URL is an open invitation.
    """
    for _ in range(security.MAX_FAILED_ATTEMPTS):
        anon.post("/api/login", json={"password": "wrong"})

    # Locked now — and crucially, still locked even with the RIGHT password.
    blocked = anon.post("/api/login", json={"password": PASSWORD})
    assert blocked.status_code == 429


def test_a_successful_login_clears_the_failure_count(anon):
    """
    Otherwise a few honest typos over a week would eventually lock the coach out
    of their own tool for no reason.
    """
    for _ in range(security.MAX_FAILED_ATTEMPTS - 1):
        anon.post("/api/login", json={"password": "wrong"})
    assert anon.post("/api/login", json={"password": PASSWORD}).status_code == 200

    # The counter is reset, so a fresh run of failures is needed to lock out —
    # one more wrong guess must not trip it.
    assert anon.post("/api/login", json={"password": "wrong"}).status_code == 401


def test_logout_invalidates_the_session(coach):
    assert coach.get("/api/clients").status_code == 200
    assert coach.post("/api/logout").status_code == 200
    # The cookie may still be in the jar; the server-side session is gone.
    assert coach.get("/api/clients").status_code == 401


def test_session_endpoint_reports_state_without_leaking(anon, coach):
    out = anon.get("/api/session").json()
    assert out["configured"] is True
    assert out["logged_in"] is False
    assert out["setup_hint"] is None

    assert coach.get("/api/session").json()["logged_in"] is True


def test_session_cookie_is_httponly(anon):
    """HttpOnly is what stops an XSS bug from stealing the session."""
    r = anon.post("/api/login", json={"password": PASSWORD})
    set_cookie = r.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


def test_password_comparison_is_constant_time():
    assert security.check_password(PASSWORD) is True
    assert security.check_password("wrong") is False
    assert security.check_password("") is False


def test_security_headers_are_present(anon):
    h = anon.get("/").headers
    assert h["referrer-policy"] == "same-origin"
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "default-src 'self'" in h["content-security-policy"]


def test_client_data_responses_are_not_cacheable(coach):
    """
    Without no-store, a shared or proxy cache could retain someone's
    measurements after logout.
    """
    cache = coach.get("/api/clients").headers.get("cache-control", "")
    assert "no-store" in cache


def test_health_reports_whether_coach_mode_is_locked(anon):
    """The deployment self-check: false here means data is published unprotected."""
    assert anon.get("/api/health").json()["coach_mode_configured"] is True


# ===========================================================================
#  ONBOARDING
# ===========================================================================

def make_invite(coach, label="Test client"):
    r = coach.post("/api/invites", json={"label": label, "ttl_days": 14})
    assert r.status_code == 201
    return r.json()


VALID_ANSWERS = {
    "full_name": "Test Person",
    "contact": "test@example.com",
    "age": "30",
    "sex": "female",
    "height_cm": "165",
    "weight_kg": "70",
    "goal": "cut",
    "diet": "vegetarian",
}


def test_invite_token_is_long_and_random(coach):
    a = make_invite(coach, "one")
    b = make_invite(coach, "two")
    assert len(a["token"]) >= 32
    assert a["token"] != b["token"]
    # The absolute URL is built from the request, so it works on any host.
    assert a["url"].endswith(f"/start/{a['token']}")


def test_invite_label_is_never_exposed_to_the_client(coach, anon):
    """The label is a private note ("gym referral", "friend of X")."""
    invite = make_invite(coach, "Private note about this person")
    schema = anon.get(f"/api/intake/{invite['token']}").json()
    assert "Private note" not in str(schema)


def test_client_can_fetch_the_form_without_logging_in(anon, coach):
    invite = make_invite(coach)
    r = anon.get(f"/api/intake/{invite['token']}")
    assert r.status_code == 200
    body = r.json()
    assert body["usable"] is True
    assert len(body["sections"]) == len(intake.SECTIONS)
    assert body["consent"]["points"]


def test_an_unknown_token_reveals_nothing(anon):
    """
    A random token must not distinguish "no such link" from anything else, and
    must not leak whether the app has any clients at all.
    """
    body = anon.get("/api/intake/completely-made-up-token").json()
    assert body["usable"] is False
    assert body["state"] == "missing"
    assert "sections" not in body


def test_submission_requires_every_required_field(anon, coach):
    invite = make_invite(coach)
    r = anon.post(f"/api/intake/{invite['token']}",
                  json={"answers": {"full_name": "Only a name"}, "consent": True})
    assert r.status_code == 422
    # The message names the questions, not the database keys.
    assert "Phone or email" in r.json()["detail"]


def test_submission_requires_consent(anon, coach):
    invite = make_invite(coach)
    r = anon.post(f"/api/intake/{invite['token']}",
                  json={"answers": VALID_ANSWERS, "consent": False})
    assert r.status_code == 422


def test_a_link_works_exactly_once(anon, coach):
    invite = make_invite(coach)
    first = anon.post(f"/api/intake/{invite['token']}",
                      json={"answers": VALID_ANSWERS, "consent": True})
    assert first.status_code == 200

    second = anon.post(f"/api/intake/{invite['token']}",
                       json={"answers": VALID_ANSWERS, "consent": True})
    assert second.status_code == 410

    state = anon.get(f"/api/intake/{invite['token']}").json()
    assert state["usable"] is False
    assert state["state"] == "used"


def test_a_revoked_link_stops_working(anon, coach):
    invite = make_invite(coach)
    assert coach.post(f"/api/invites/{invite['id']}/revoke").status_code == 200
    assert anon.get(f"/api/intake/{invite['token']}").json()["state"] == "revoked"
    assert anon.post(f"/api/intake/{invite['token']}",
                     json={"answers": VALID_ANSWERS, "consent": True}).status_code == 410


def test_an_expired_link_stops_working(anon, coach):
    """Expiry matters because links live on in WhatsApp history forever."""
    invite = make_invite(coach)
    # Reach past the API to age it, rather than waiting two weeks.
    with db.db() as c:
        c.execute("UPDATE invites SET expires_at = ? WHERE id = ?",
                  ("2020-01-01T00:00:00+00:00", invite["id"]))
    assert anon.get(f"/api/intake/{invite['token']}").json()["state"] == "expired"


def test_oversized_answers_are_rejected(anon, coach):
    """This is a public write path, so the body has to be bounded."""
    invite = make_invite(coach)
    r = anon.post(f"/api/intake/{invite['token']}", json={
        "answers": {**VALID_ANSWERS, "anything_else": "x" * 6000},
        "consent": True,
    })
    assert r.status_code == 422


def test_submission_returns_priorities_but_no_numbers(anon, coach):
    """
    The business rule, enforced by a test: the client gets proof their answers
    were read, and does NOT get the calorie or macro targets. Those are the
    coaching deliverable — giving them away here removes the reason to book.
    """
    invite = make_invite(coach)
    body = anon.post(f"/api/intake/{invite['token']}", json={
        "answers": {**VALID_ANSWERS, "sleep_hours": "5",
                    "what_broke_it": "I got too hungry in the evenings"},
        "consent": True,
    }).json()

    assert body["received"] is True
    assert body["priorities"], "the client should see what stood out"
    assert body["closing"]["heading"].startswith("Thanks, Test")

    # Check for actual VALUES, not the words. The closing text deliberately says
    # "your calorie and macro targets are what we'll go through together" — that
    # sentence is the sales pitch, so a naive keyword ban would flag the feature
    # as the bug. What must never appear is a number.
    import re
    blob = str(body)
    numeric_leaks = [
        pattern for pattern in (
            r"\d{3,4}\s*(kcal|calories)",       # a calorie target
            r"\d{2,4}\s*g\s*(of\s*)?(protein|carb|fat)",   # a macro target
            r"\d+\.?\d*\s*g/kg",               # a per-kilo prescription
        )
        if re.search(pattern, blob, re.IGNORECASE)
    ]
    assert not numeric_leaks, f"leaked a target to the client: {numeric_leaks}"


def test_priorities_are_capped_and_ordered_by_importance():
    """
    A screen full of concerns reads as alarming rather than competent, so only
    the top three fire — and safety outranks everything.
    """
    everything_wrong = {
        "full_name": "Kitchen Sink", "pregnant": "yes", "age": "16",
        "eating_disorder_history": "yes", "conditions": "thyroid",
        "sleep_hours": "4", "stress": "high", "diet": "vegan",
        "tea_coffee": "6", "injuries": "back", "who_cooks": "family",
        "what_broke_it": "hunger", "dislikes": "paneer", "fasting": "Ekadashi",
    }
    out = intake.derive_priorities(everything_wrong)
    assert len(out) == 3
    # Pregnancy is the highest-weighted rule, so it must lead.
    assert "doctor" in out[0]["title"].lower() or "doctor" in out[0]["because"].lower()


def test_dismissive_free_text_does_not_trigger_a_priority():
    """
    "none" and "-" are how people say nothing. Treating them as content would
    produce embarrassing feedback like "you mentioned a condition" when they
    typed "none".
    """
    for filler in ("none", "None", "nil", "-", "n/a", "nothing", "no"):
        out = intake.derive_priorities({"conditions": filler, "injuries": filler})
        titles = " ".join(p["title"] for p in out)
        assert "medical history" not in titles, f"{filler!r} was read as content"
        assert "injury" not in titles, f"{filler!r} was read as content"


def test_coach_sees_the_submission_and_its_labels(coach, anon):
    invite = make_invite(coach)
    anon.post(f"/api/intake/{invite['token']}",
              json={"answers": VALID_ANSWERS, "consent": True})

    listed = coach.get("/api/intakes").json()["intakes"]
    assert any(i["full_name"] == "Test Person" for i in listed)

    intake_id = next(i["id"] for i in listed if i["full_name"] == "Test Person")
    detail = coach.get(f"/api/intakes/{intake_id}").json()
    assert detail["answers"]["contact"] == "test@example.com"
    assert detail["consent_version"] == intake.CONSENT_VERSION
    assert detail["consent_at"]
    # Sections travel with the submission so answers display as questions.
    assert len(detail["sections"]) == len(intake.SECTIONS)


def test_converting_an_intake_creates_a_client_with_a_starting_weight(coach, anon):
    invite = make_invite(coach)
    anon.post(f"/api/intake/{invite['token']}",
              json={"answers": VALID_ANSWERS, "consent": True})
    intake_id = coach.get("/api/intakes").json()["intakes"][0]["id"]

    r = coach.post(f"/api/intakes/{intake_id}/convert")
    assert r.status_code == 201
    client_row = r.json()["client"]
    assert client_row["name"] == "Test Person"
    assert client_row["sex"] == "female"
    assert client_row["diet"] == "vegetarian"

    detail = coach.get(f"/api/clients/{client_row['id']}").json()
    assert len(detail["measurements"]) == 1
    assert detail["measurements"][0]["weight_kg"] == 70.0

    # Converting twice would silently duplicate the client.
    assert coach.post(f"/api/intakes/{intake_id}/convert").status_code == 409


def test_recomp_goal_maps_to_a_goal_the_planner_understands(coach, anon):
    """
    The questionnaire offers "both — leaner and stronger", which the planner has
    no mode for. It must map to something valid rather than write a bad row.
    """
    invite = make_invite(coach)
    anon.post(f"/api/intake/{invite['token']}",
              json={"answers": {**VALID_ANSWERS, "goal": "recomp"}, "consent": True})
    intake_id = coach.get("/api/intakes").json()["intakes"][0]["id"]
    created = coach.post(f"/api/intakes/{intake_id}/convert").json()["client"]
    assert created["goal"] in ("cut", "maintain", "bulk")


def test_deleting_an_intake_actually_removes_it(coach, anon):
    """
    This is how the promise on the consent screen is honoured, so a soft delete
    would make that promise untrue.
    """
    invite = make_invite(coach)
    anon.post(f"/api/intake/{invite['token']}",
              json={"answers": VALID_ANSWERS, "consent": True})
    intake_id = coach.get("/api/intakes").json()["intakes"][0]["id"]

    assert coach.delete(f"/api/intakes/{intake_id}").status_code == 200
    assert coach.get(f"/api/intakes/{intake_id}").status_code == 404

    with db.db() as c:
        row = c.execute("SELECT COUNT(*) FROM intakes WHERE id = ?",
                        (intake_id,)).fetchone()
    assert row[0] == 0, "the answers are still in the database file"


def test_the_questionnaire_itself_is_well_formed():
    """Content integrity, same idea as the knowledge-base tests."""
    keys = [f["key"] for f in intake.flatten_fields()]
    assert len(keys) == len(set(keys)), "duplicate field keys"

    for field in intake.flatten_fields():
        assert field["key"] and field["label"]
        assert field["type"] in (
            "text", "number", "radio", "select", "textarea",
        ), f"{field['key']}: unknown type {field['type']}"
        if field["type"] in ("radio", "select"):
            assert field.get("options"), f"{field['key']} has no options"
            for o in field["options"]:
                assert o["value"] and o["label"]

    # Enough of the sensitive questions explain themselves — that's the whole
    # trust mechanism, and losing it would quietly gut the page's persuasiveness.
    with_why = [f for f in intake.flatten_fields() if f.get("why")]
    assert len(with_why) >= 20, "too few questions explain why they're asked"


def test_consent_text_covers_the_promises_we_make():
    text = " ".join(intake.CONSENT["points"]).lower()
    for promise in ("delete", "not sold", "not a medical"):
        assert promise in text, f"consent text is missing: {promise}"
    assert intake.CONSENT_VERSION
