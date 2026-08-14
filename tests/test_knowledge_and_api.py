"""
test_knowledge_and_api.py — content integrity and the HTTP layer.

Two jobs.

**Knowledge integrity.** The knowledge base is hand-written prose and data, which
means the failure mode isn't an exception — it's a missing citation, a nutrient
with no food sources, or a "why" panel that's silently empty. These tests assert
the *shape* of the content everywhere, so the "every number gets an explanation
and a source" promise is enforced mechanically rather than by memory.

**API contract.** Endpoint status codes, validation, and the client/measurement
lifecycle against a throwaway database.
"""

import os
import tempfile

import pytest

# The app resolves its SQLite path at import time, so TOOLKIT_DB has to be set
# before `app.main` is imported — hence this sitting above the app imports.
#
# COACH_PASSWORD is different: it's read from the environment on every check, and
# every test module in this suite sets it during collection. The module collected
# last therefore owns it by the time any test actually runs, which is why the
# re-logins further down ask the app which password is currently in force rather
# than assuming it's this file's.
_tmp_db = os.path.join(tempfile.mkdtemp(), "test_toolkit.db")
os.environ["TOOLKIT_DB"] = _tmp_db
TEST_PASSWORD = "test-coach-password"
os.environ["COACH_PASSWORD"] = TEST_PASSWORD

from fastapi.testclient import TestClient          # noqa: E402

from app import engine, security                    # noqa: E402
from app.knowledge import explanations, foods, micronutrients, sources  # noqa: E402
from app.main import app                            # noqa: E402

# Two clients on purpose, so a test can't accidentally prove that a protected
# endpoint works while actually being logged in:
#   `public`  — never authenticates. Used for the calculator and to assert that
#               client-data endpoints reject anonymous callers.
#   `client`  — logged in as the coach. Used for everything behind the gate.
public = TestClient(app)
client = TestClient(app)
assert client.post("/api/login", json={"password": TEST_PASSWORD}).status_code == 200


# ===========================================================================
#  KNOWLEDGE INTEGRITY
# ===========================================================================

def test_every_source_key_referenced_anywhere_actually_exists():
    """
    A typo in a source key would silently drop a citation from the UI —
    `sources.resolve()` skips unknown keys by design so one typo can't 500 a
    whole assessment. This is the test that catches the typo instead.
    """
    referenced = set()

    for m in micronutrients.MICRONUTRIENTS:
        referenced.update(m["source_keys"])
    for note in explanations.BODYFAT_METHOD_NOTES.values():
        referenced.update(note["source_keys"])

    # The macro explanation builders need a context dict, so build each with a
    # realistic one and harvest the keys it declares.
    ctx = dict(
        grams=160, g_per_kg_bw=2.0, g_per_kg_lbm=2.4, lbm_kg=66, goal="cut",
        deficit_pct=20, kcal=640, pct_kcal=29, in_issn_range=True,
        floor_g=40, floor_pct=20, below_floor=False, low_warning=False,
        training_days=1.0, per_1000_kcal=14, total_ml=4000, total_l=4.0,
        baseline_ml=2800, training_ml=600, climate_ml=600, protein_ml=0,
        per_kg=35, training_hours=1.0, climate="hot", weight_kg=80,
        target=2300, tdee=2900, bmr_used=1800, bmr_method="Katch–McArdle",
        delta=-600, delta_pct=20, rate_kg_per_week=0.55, rate_pct_bw=0.7,
    )
    for builder in (explanations.protein, explanations.fat, explanations.carbs,
                    explanations.fibre, explanations.water, explanations.calories):
        referenced.update(builder(ctx)["source_keys"])

    missing = sources.validate_keys(sorted(referenced))
    assert missing == [], f"Unknown source keys referenced: {missing}"


def test_every_source_has_the_required_fields():
    for key, s in sources.SOURCES.items():
        for field in ("org", "label", "title", "url", "note"):
            assert s.get(field), f"{key} is missing '{field}'"
        assert s["url"].startswith("http"), f"{key} has a malformed URL"


@pytest.mark.parametrize("builder", [
    explanations.protein, explanations.fat, explanations.carbs,
    explanations.fibre, explanations.water, explanations.calories,
])
def test_every_explanation_is_complete(builder):
    """
    The product promise, enforced structurally: a number without the physiology,
    both failure directions, and a citation is not shippable.
    """
    ctx = dict(
        grams=160, g_per_kg_bw=2.0, g_per_kg_lbm=2.4, lbm_kg=66, goal="cut",
        deficit_pct=20, kcal=640, pct_kcal=29, in_issn_range=True,
        floor_g=40, floor_pct=20, below_floor=False, low_warning=False,
        training_days=1.0, per_1000_kcal=14, total_ml=4000, total_l=4.0,
        baseline_ml=2800, training_ml=600, climate_ml=600, protein_ml=250,
        per_kg=35, training_hours=1.0, climate="hot", weight_kg=80,
        target=2300, tdee=2900, bmr_used=1800, bmr_method="Katch–McArdle",
        delta=-600, delta_pct=20, rate_kg_per_week=0.55, rate_pct_bw=0.7,
    )
    e = builder(ctx)

    assert e["id"] and e["title"] and e["headline"]
    assert len(e["why_this_much"]) > 200, "the reasoning should be substantial"
    assert len(e["what_it_does"]) >= 3, "at least three physiological jobs"
    assert all(j["label"] and len(j["text"]) > 60 for j in e["what_it_does"])
    assert len(e["too_little"]) >= 3
    assert len(e["too_much"]) >= 2
    assert len(e["source_keys"]) >= 2


def test_protein_explanation_changes_with_the_goal():
    """
    Cutting, maintaining and bulking need genuinely different reasoning — a
    generic paragraph with the goal name swapped in would be the lazy version.
    """
    base = dict(grams=160, g_per_kg_bw=2.0, g_per_kg_lbm=2.4, lbm_kg=66,
                deficit_pct=20, kcal=640, pct_kcal=29, in_issn_range=True)
    texts = {
        g: explanations.protein({**base, "goal": g})["why_this_much"]
        for g in ("cut", "maintain", "bulk")
    }
    assert len({*texts.values()}) == 3
    assert "deficit" in texts["cut"].lower()
    assert "surplus" in texts["bulk"].lower()


def test_fat_explanation_warns_when_below_floor():
    ctx = dict(grams=40, g_per_kg_bw=0.5, pct_kcal=16, floor_g=45,
               floor_pct=20, below_floor=True, kcal=360)
    text = explanations.fat(ctx)["why_this_much"]
    assert "⚠" in text and "floor" in text.lower()


def test_every_micronutrient_is_complete():
    for m in micronutrients.MICRONUTRIENTS:
        assert m["key"] and m["name"] and m["unit"]
        assert len(m["what_it_does"]) > 100, f"{m['key']}: thin 'what it does'"
        assert len(m["why_short"]) > 80, f"{m['key']}: thin 'why short'"
        assert len(m["deficiency_signs"]) >= 3, f"{m['key']}: too few signs"
        assert len(m["upper_limit"]) > 40, f"{m['key']}: no upper-limit guidance"
        assert len(m["athlete_note"]) > 60, f"{m['key']}: no training angle"
        assert m["source_keys"], f"{m['key']}: uncited"
        # At least one reference set must give a number.
        assert m["icmr"] or m["western"], f"{m['key']}: no target at all"


def test_micronutrient_keys_are_unique():
    keys = [m["key"] for m in micronutrients.MICRONUTRIENTS]
    assert len(keys) == len(set(keys))


def test_the_required_micronutrients_are_all_covered():
    """The list the tool promises to cover."""
    required = {
        "vitamin_d", "b12", "iron", "calcium", "magnesium", "zinc",
        "potassium", "sodium", "omega3", "vitamin_a", "vitamin_c",
        "vitamin_e", "vitamin_k",
    }
    assert required <= set(micronutrients.BY_KEY)


def test_indian_iron_and_zinc_rdas_exceed_western_ones():
    """
    Not a rounding difference — ICMR-NIN sets these higher because phytates in a
    cereal-and-pulse diet block absorption. If this ever inverts, the data is
    wrong.
    """
    iron = micronutrients.BY_KEY["iron"]
    zinc = micronutrients.BY_KEY["zinc"]
    assert iron["icmr"]["male"] > iron["western"]["male"]
    assert iron["icmr"]["female"] > iron["western"]["female"]
    assert zinc["icmr"]["male"] > zinc["western"]["male"]


def test_female_iron_rda_exceeds_male():
    iron = micronutrients.BY_KEY["iron"]
    assert iron["icmr"]["female"] > iron["icmr"]["male"]


def test_risk_profile_flags_vegans_for_b12_and_calcium():
    tags = micronutrients.build_risk_profile(
        diet="vegan", sex="male", deficit_pct=10, climate="temperate",
        training_hours=1.0, goal="maintain", carb_g_per_kg=3.0, fat_g_per_kg=1.0,
    )
    assert "vegan" in tags and "no_dairy" in tags

    panel = micronutrients.panel_for(tags, "male")
    by_key = {p["key"]: p for p in panel}
    assert by_key["b12"]["priority"] == "high"
    assert by_key["calcium"]["flagged_by"]


def test_risk_profile_flags_a_deep_cut():
    tags = micronutrients.build_risk_profile(
        diet="omnivore", sex="male", deficit_pct=25, climate="hot",
        training_hours=2.0, goal="cut", carb_g_per_kg=1.5, fat_g_per_kg=0.6,
    )
    assert {"deep_cut", "heavy_sweater", "low_carb", "low_fat"} <= set(tags)


def test_panel_is_ordered_priority_first():
    tags = micronutrients.build_risk_profile(
        diet="vegan", sex="female", deficit_pct=26, climate="very_hot",
        training_hours=2.0, goal="cut", carb_g_per_kg=1.5, fat_g_per_kg=0.6,
    )
    panel = micronutrients.panel_for(tags, "female")
    rank = {"high": 0, "watch": 1, "standard": 2}
    order = [rank[p["priority"]] for p in panel]
    assert order == sorted(order)


def test_every_food_has_complete_macros():
    for f in foods.ALL_FOODS:
        for field in ("key", "name", "household", "grams", "kcal",
                      "protein_g", "carb_g", "fat_g", "fibre_g", "tags"):
            assert field in f, f"{f.get('key')} missing {field}"
        assert f["kcal"] > 0
        assert f["tags"], f"{f['key']} has no diet tags"


def test_food_calories_roughly_match_their_macros():
    """
    Sanity check against typos: protein·4 + carbs·4 + fat·9 should land within
    ~20% of the stated calories. Wide tolerance on purpose — real food tables
    include fibre, alcohol and rounding effects.
    """
    for f in foods.ALL_FOODS:
        computed = f["protein_g"] * 4 + f["carb_g"] * 4 + f["fat_g"] * 9
        if computed < 20:
            continue        # tiny portions like a 5 g tsp of ghee
        ratio = computed / f["kcal"]
        assert 0.8 <= ratio <= 1.2, (
            f"{f['key']}: macros imply {computed:.0f} kcal but says {f['kcal']}"
        )


def test_food_keys_are_unique():
    keys = [f["key"] for f in foods.ALL_FOODS]
    assert len(keys) == len(set(keys))


def test_diet_filtering_is_strict():
    chicken = foods.BY_KEY["chicken_breast"]
    eggs = foods.BY_KEY["eggs_whole"]
    paneer = foods.BY_KEY["paneer"]
    dal = foods.BY_KEY["toor_dal"]

    assert foods.diet_ok(chicken, "omnivore")
    assert not foods.diet_ok(chicken, "eggetarian")
    assert not foods.diet_ok(chicken, "vegetarian")

    assert foods.diet_ok(eggs, "eggetarian")
    assert not foods.diet_ok(eggs, "vegetarian")

    assert foods.diet_ok(paneer, "vegetarian")
    assert not foods.diet_ok(paneer, "vegan")     # dairy

    assert foods.diet_ok(dal, "vegan")


def test_sample_plate_lands_near_the_target_without_overshooting_badly():
    for diet in ("omnivore", "eggetarian", "vegetarian", "vegan"):
        plate = foods.sample_plate(160, diet)
        total = sum(x["protein_g"] for x in plate)
        assert plate, f"{diet}: produced an empty plate"
        assert 130 <= total <= 185, f"{diet}: plate totals {total} g against 160 g"


def test_vegan_has_no_whole_food_b12_source():
    """
    The absence is the information — it's exactly why a vegan needs a supplement,
    and the UI surfaces that rather than inventing a weak source.
    """
    assert foods.sources_for_micro("b12", "vegan") == []
    assert foods.sources_for_micro("b12", "omnivore")


def test_fibre_picks_respect_diet():
    for diet in ("omnivore", "vegetarian", "vegan"):
        picks = foods.high_fibre_picks(diet)
        assert picks
        assert all("name" in p and "fibre_g" in p for p in picks)


# ===========================================================================
#  API
# ===========================================================================

VALID = {
    "sex": "male", "age": 26, "weight_kg": 78, "height_cm": 176,
    "goal": "cut", "activity": "moderate", "diet": "omnivore",
    "climate": "hot", "training_hours": 1.5, "meals": 4,
    "girths": {"neck": 39, "waist": 82},
}


def test_health_reports_loaded_content():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["sources_loaded"] > 20
    assert body["micronutrients_loaded"] >= 13
    assert body["foods_loaded"] > 30


def test_index_serves_the_app():
    r = client.get("/")
    assert r.status_code == 200
    assert "Physique" in r.text


def test_meta_returns_every_option_list():
    body = client.get("/api/meta").json()
    for key in ("activity_levels", "goals", "diets", "climates",
                "bodyfat_bands", "measurement_help", "foods", "disclaimer"):
        assert key in body
    assert len(body["goals"]) == 4
    assert "not medical advice" in body["disclaimer"].lower()


def test_sources_endpoint():
    body = client.get("/api/sources").json()
    assert body["count"] == len(sources.SOURCES)
    assert all("url" in s for s in body["sources"])


def test_micronutrient_reference_endpoint_per_sex():
    male = client.get("/api/micronutrients?sex=male").json()
    female = client.get("/api/micronutrients?sex=female").json()
    m_iron = next(m for m in male["panel"] if m["key"] == "iron")
    f_iron = next(m for m in female["panel"] if m["key"] == "iron")
    assert f_iron["target_icmr"] > m_iron["target_icmr"]


def test_micronutrient_endpoint_rejects_bad_sex():
    assert client.get("/api/micronutrients?sex=alien").status_code == 400


def test_assess_happy_path_returns_the_full_report():
    r = client.post("/api/assess", json=VALID)
    assert r.status_code == 200
    body = r.json()
    for section in ("bodyfat", "composition", "energy", "nutrition",
                    "micronutrients", "safety", "disclaimer"):
        assert section in body


def test_every_assess_target_carries_an_explanation_and_sources():
    """The end-to-end version of the product promise."""
    body = client.post("/api/assess", json=VALID).json()
    for key in ("kcal", "protein", "fat", "carbs", "fibre", "water"):
        block = body["nutrition"][key]
        assert block["number"] > 0
        assert block["unit"]
        assert block["why"]["why_this_much"]
        assert block["why"]["what_it_does"]
        assert block["why"]["too_little"] and block["why"]["too_much"]
        assert block["sources"], f"{key} came back with no citation"


def test_assess_rejects_height_in_metres():
    r = client.post("/api/assess", json={**VALID, "height_cm": 1.76})
    assert r.status_code == 422


def test_assess_rejects_out_of_range_values():
    assert client.post("/api/assess", json={**VALID, "age": 5}).status_code == 422
    assert client.post("/api/assess", json={**VALID, "weight_kg": 500}).status_code == 422
    assert client.post("/api/assess", json={**VALID, "sex": "other"}).status_code == 422


def test_assess_works_with_no_measurements_at_all():
    """Deurenberg needs only height, weight and age — so this must not fail."""
    minimal = {"sex": "female", "age": 30, "weight_kg": 62, "height_cm": 163}
    r = client.post("/api/assess", json=minimal)
    assert r.status_code == 200
    assert r.json()["bodyfat"]["chosen"]["method"] == "deurenberg"


def test_supplied_bodyfat_overrides_the_estimates():
    r = client.post("/api/assess", json={**VALID, "bodyfat_pct": 14.2})
    body = r.json()
    assert body["bodyfat"]["chosen"]["method"] == "supplied"
    assert body["composition"]["bodyfat_pct"] == 14.2


def test_bodyfat_endpoint_compares_methods():
    body = client.post("/api/bodyfat", json={
        "sex": "male", "age": 25, "weight_kg": 80, "height_cm": 180,
        "girths": {"neck": 40, "waist": 84},
        "skinfolds": {"chest": 9, "abdomen": 17, "thigh": 11},
    }).json()
    methods = {m["method"] for m in body["methods"]}
    assert {"navy", "jp3", "deurenberg"} <= methods
    assert body["spread"] > 0
    assert body["spread_note"]


def test_prep_plan_endpoint():
    body = client.post("/api/prep-plan", json={
        "sex": "male", "weight_kg": 85, "current_bodyfat_pct": 20,
        "target_bodyfat_pct": 12, "weeks": 16,
    }).json()
    assert len(body["plan"]["projection"]) == 17
    assert body["plan"]["verdict"]
    assert body["sources"]


def test_strength_endpoint_with_and_without_a_total():
    plain = client.post("/api/strength", json={"weight": 140, "reps": 5}).json()
    assert plain["one_rm"]["average"] > 140
    assert len(plain["table"]) == 10
    assert plain["scores"] is None

    scored = client.post("/api/strength", json={
        "weight": 140, "reps": 5, "sex": "male",
        "bodyweight_kg": 83, "total_kg": 520,
    }).json()
    assert scored["scores"]["dots"] > 0
    assert scored["scores"]["wilks"] > 0


def test_strength_rejects_impossible_reps():
    assert client.post("/api/strength", json={"weight": 100, "reps": 0}).status_code == 422
    assert client.post("/api/strength", json={"weight": 100, "reps": 40}).status_code == 422


# ---------------------------------------------------------------------------
#  Client lifecycle
# ---------------------------------------------------------------------------

def test_client_and_measurement_lifecycle():
    created = client.post("/api/clients", json={
        "name": "Test Client", "sex": "female", "age": 29,
        "height_cm": 165, "diet": "vegetarian", "goal": "cut",
    })
    assert created.status_code == 201
    body = created.json()
    # The regression that shipped once: create_client read on a second
    # connection before its own transaction committed and returned null.
    assert body is not None, "create must return the created row, not null"
    assert body["id"] and body["name"] == "Test Client"
    cid = body["id"]

    for date, weight, bf in [("2026-06-01", 68.0, 30.0),
                             ("2026-07-01", 66.0, 28.4),
                             ("2026-08-01", 64.5, 27.0)]:
        r = client.post(f"/api/clients/{cid}/measurements", json={
            "taken_on": date, "weight_kg": weight, "bodyfat_pct": bf,
            "waist_cm": 78 - (68 - weight),
        })
        assert r.status_code == 201

    detail = client.get(f"/api/clients/{cid}").json()
    assert len(detail["measurements"]) == 3
    p = detail["progress"]
    assert p["entries"] == 3
    assert p["weight_change_kg"] == -3.5
    # Fat mass should fall and lean mass should be roughly held.
    assert p["fat_mass_change_kg"] < 0

    # Measurements must come back in date order for the chart.
    dates = [m["taken_on"] for m in detail["measurements"]]
    assert dates == sorted(dates)

    # Deleting the client cascades to their measurements.
    assert client.delete(f"/api/clients/{cid}").status_code == 200
    assert client.get(f"/api/clients/{cid}").status_code == 404


def test_measurement_rejects_a_bad_date():
    c = client.post("/api/clients", json={
        "name": "Date Test", "sex": "male", "age": 30, "height_cm": 175,
    }).json()
    r = client.post(f"/api/clients/{c['id']}/measurements", json={
        "taken_on": "01-06-2026", "weight_kg": 80,
    })
    assert r.status_code == 422


def test_measurement_on_missing_client_is_404():
    r = client.post("/api/clients/999999/measurements",
                    json={"taken_on": "2026-08-01", "weight_kg": 80})
    assert r.status_code == 404


def test_missing_client_endpoints_are_404():
    assert client.get("/api/clients/999999").status_code == 404
    assert client.delete("/api/clients/999999").status_code == 404
    assert client.delete("/api/measurements/999999").status_code == 404


def test_saved_report_round_trips():
    saved = client.post("/api/reports", json=VALID)
    assert saved.status_code == 201
    rid = saved.json()["id"]

    loaded = client.get(f"/api/reports/{rid}").json()
    # The snapshot must include the explanation wording, not just the numbers —
    # that's the whole point of storing the payload verbatim.
    assert loaded["payload"]["nutrition"]["protein"]["why"]["why_this_much"]
    assert loaded["kcal"] > 0

    assert client.delete(f"/api/reports/{rid}").status_code == 200
    assert client.get(f"/api/reports/{rid}").status_code == 404


# ---------------------------------------------------------------------------
#  Database resilience
#
#  Regression: the store is a plain file, so it can vanish under a running
#  process — deleted during a tidy-up, moved, or restored from a backup. Because
#  init_db() only ran at startup, sqlite then created an empty file and every
#  Coach mode request failed with an opaque 500 that read as a broken endpoint.
# ---------------------------------------------------------------------------

def test_api_recovers_when_the_database_file_is_deleted():
    """Deleting the DB mid-run must self-heal, not 500."""
    created = client.post("/api/clients", json={
        "name": "Before Deletion", "sex": "male", "age": 30, "height_cm": 175,
    })
    assert created.status_code == 201

    os.remove(_tmp_db)
    assert not os.path.exists(_tmp_db)

    # Sessions live in the database now, so deleting it logs the coach out. That
    # is the correct outcome — the credential was in the store that just
    # vanished — and logging back in doubles as proof that the recreated schema
    # is writable, not merely present.
    assert client.post("/api/login",
                       json={"password": security.coach_password()}).status_code == 200

    # The schema is recreated on the next connection, so the endpoint works —
    # empty, because the data really was in the deleted file.
    r = client.get("/api/clients")
    assert r.status_code == 200
    assert r.json()["clients"] == []

    # And it's fully writable again, not just readable.
    again = client.post("/api/clients", json={
        "name": "After Recovery", "sex": "female", "age": 28, "height_cm": 165,
    })
    assert again.status_code == 201
    assert again.json()["name"] == "After Recovery"

    detail = client.get(f"/api/clients/{again.json()['id']}")
    assert detail.status_code == 200


def test_measurements_work_on_a_recreated_database():
    """The full schema comes back, not just the clients table."""
    os.remove(_tmp_db)
    # Same reason as the test above: the session went with the file.
    assert client.post("/api/login",
                       json={"password": security.coach_password()}).status_code == 200

    c = client.post("/api/clients", json={
        "name": "Schema Check", "sex": "male", "age": 25, "height_cm": 180,
    }).json()

    m = client.post(f"/api/clients/{c['id']}/measurements", json={
        "taken_on": "2026-08-01", "weight_kg": 80, "bodyfat_pct": 18,
    })
    assert m.status_code == 201

    # reports table too — all three tables plus the indexes.
    saved = client.post("/api/reports", json=VALID)
    assert saved.status_code == 201
