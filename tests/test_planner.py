"""
test_planner.py — the diet builder, and the arithmetic it shows the coach.

Two things are being protected here, and they fail in different ways.

The **shown working** must never disagree with the plan it describes. It's the
feature's whole promise: a coach can check the numbers by hand. If `macro_math`
ever drifts from `formulas.macros`, the tool starts confidently explaining an
answer it didn't give, and nothing on the screen would reveal it. Those tests
assert the two agree, rather than asserting either against a hardcoded figure —
a hardcoded expectation would pass while both drifted together.

The **plan itself** must land near its targets. That's asserted against the
bands the module publishes, across diets, budgets and goals, because the failure
mode isn't a crash — it's a plan that looks fine and is 400 kcal out.

Run with:  pytest -q
"""

import importlib
import os
import tempfile

import pytest

# Must be set before app.main is imported — and `setdefault`, not assignment,
# because another test module may already have imported it. Overwriting the
# password here would leave app.security holding the earlier value while this
# module's fixtures logged in with the later one, and every coach test would fail
# with a 401 that had nothing to do with the code under test.
_tmp_db = os.path.join(tempfile.mkdtemp(), "planner_toolkit.db")
os.environ.setdefault("TOOLKIT_DB", _tmp_db)
PASSWORD = os.environ.setdefault("COACH_PASSWORD", "planner-test-password-9f3a")

from fastapi.testclient import TestClient              # noqa: E402

from app import formulas as f                          # noqa: E402
from app import planner, security                      # noqa: E402
from app.knowledge import foods                        # noqa: E402
from app.main import app                               # noqa: E402


@pytest.fixture
def coach():
    """
    A logged-in coach.

    The password is read here rather than captured at import. Test modules are
    all imported before any of them run, and a later one assigns COACH_PASSWORD
    outright — so a constant captured at import time is stale by the time this
    fixture uses it, and every coach test fails with a 401 that has nothing to do
    with the code being tested.
    """
    security._attempts.clear()
    c = TestClient(app)
    password = os.environ["COACH_PASSWORD"]
    assert c.post("/api/login", json={"password": password}).status_code == 200
    return c


BASE = {
    "sex": "male", "age": 28, "weight_kg": 75, "height_cm": 178,
    "goal": "cut", "activity": "moderate", "diet": "omnivore", "meals": 4,
}


# ===========================================================================
#  THE SHOWN WORKING MUST MATCH THE REAL CALCULATION
# ===========================================================================

@pytest.mark.parametrize("goal", ["cut", "maintain", "bulk"])
@pytest.mark.parametrize("kcal,lbm", [(1500, 45.0), (2000, 60.0), (3200, 70.0)])
def test_the_working_reports_the_same_grams_the_engine_uses(goal, kcal, lbm):
    """
    The point of the feature: what the coach is shown is what was computed.

    Compared against `formulas.macros` rather than a fixed number on purpose. If
    someone changes a protein coefficient, this test should keep passing — it's
    guarding the link between the two, not the value.
    """
    m = planner.macro_math(kcal=kcal, weight_kg=80, lbm_kg=lbm, goal=goal)
    real = f.macros(kcal=kcal, weight_kg=80, lbm_kg=lbm, goal=goal)

    by_macro = {s["macro"]: s for s in m["steps"]}
    assert by_macro["Protein"]["grams"] == real["protein"]["grams"]
    assert by_macro["Fat"]["grams"] == real["fat"]["grams"]
    assert by_macro["Carbs"]["grams"] == real["carbs"]["grams"]
    assert by_macro["Protein"]["kcal"] == real["protein"]["kcal"]
    assert by_macro["Fat"]["kcal"] == real["fat"]["kcal"]
    assert by_macro["Carbs"]["kcal"] == real["carbs"]["kcal"]


@pytest.mark.parametrize("kcal", [1400, 1800, 2093, 2600, 3400])
def test_the_three_macros_add_back_to_the_calorie_target(kcal):
    """
    The check line at the bottom of the working has to actually check out.

    A coach will total that column. If it doesn't come to the number in the
    header, they stop trusting every other number on the page — and they'd be
    right to.
    """
    m = planner.macro_math(kcal=kcal, weight_kg=75, lbm_kg=58.0, goal="cut")
    total = sum(s["kcal"] for s in m["steps"])

    assert m["check"]["sum_kcal"] == total
    assert m["check"]["matches"], m["check"]["working"]
    # Rounding grams to whole numbers can move the total a few kcal. More than
    # that means a real arithmetic error, not rounding.
    assert abs(total - kcal) <= 12


def test_the_working_shows_the_fat_floor_when_it_binds():
    """
    A very low calorie target drives the fat percentage under the floor.

    When that happens the plan silently uses the floor instead, and the working
    has to say so — otherwise the arithmetic on screen (25% of calories) doesn't
    produce the grams next to it, and it looks like a bug.
    """
    m = planner.macro_math(kcal=1200, weight_kg=95, lbm_kg=60.0, goal="cut")
    fat_step = next(s for s in m["steps"] if s["macro"] == "Fat")
    real = f.macros(kcal=1200, weight_kg=95, lbm_kg=60.0, goal="cut")

    assert real["fat"]["below_floor"], "expected this case to hit the floor"
    assert "floor" in fat_step["working"]
    assert fat_step["grams"] == real["fat"]["grams"]


def test_fibre_is_derived_from_calories_not_invented():
    m = planner.macro_math(kcal=2000, weight_kg=75, lbm_kg=60.0, goal="cut")
    assert m["fibre"]["grams"] == f.fibre_target(kcal=2000)["grams"]


# ===========================================================================
#  THE PLAN LANDS ON ITS TARGETS
# ===========================================================================

SCENARIOS = [
    ("omnivore", "moderate", "cut", 2093, 60.0),
    ("omnivore", "flexible", "bulk", 3000, 58.0),
    ("omnivore", "tight", "maintain", 2200, 55.0),
    ("eggetarian", "tight", "maintain", 1800, 40.0),
    ("vegetarian", "tight", "cut", 1600, 42.0),
    ("vegetarian", "moderate", "bulk", 2700, 50.0),
    ("vegan", "moderate", "maintain", 2400, 62.0),
    ("vegan", "tight", "bulk", 3200, 52.0),
]


@pytest.mark.parametrize("diet,budget,goal,kcal,lbm", SCENARIOS)
def test_the_plan_lands_inside_the_published_bands(diet, budget, goal, kcal, lbm):
    """
    Every macro within the tolerance the module publishes.

    The bands are asymmetric and that's deliberate — see BANDS in planner.py.
    Reading them from the module rather than restating them here means the test
    can't quietly disagree with what the UI tells the coach.
    """
    inp = {**BASE, "diet": diet}
    day = planner.plan(inp, kcal=kcal, lbm_kg=lbm, goal=goal, budget=budget)["day"]

    off = {k: v["off_by_pct"] for k, v in day["totals"].items() if not v["close_enough"]}
    assert day["all_close"], f"{diet}/{budget}/{goal} missed: {off}"


@pytest.mark.parametrize("diet,budget,goal,kcal,lbm", SCENARIOS)
def test_the_food_actually_adds_up_to_the_reported_totals(diet, budget, goal, kcal, lbm):
    """
    The totals row must be the sum of the items above it.

    Easy to get wrong once portions are fractional, and invisible if it is —
    the numbers would still look plausible.
    """
    inp = {**BASE, "diet": diet}
    day = planner.plan(inp, kcal=kcal, lbm_kg=lbm, goal=goal, budget=budget)["day"]

    for field in ("kcal", "protein_g", "carb_g", "fat_g", "fibre_g"):
        summed = sum(i[field] for i in day["items"])
        assert summed == pytest.approx(day["totals"][field]["planned"], abs=1.0), field


@pytest.mark.parametrize("diet", ["omnivore", "eggetarian", "vegetarian", "vegan"])
def test_the_plan_never_breaks_the_clients_diet(diet):
    """A vegan plan containing eggs isn't a near miss, it's a broken promise."""
    inp = {**BASE, "diet": diet}
    day = planner.plan(inp, kcal=2200, lbm_kg=55.0, goal="maintain")["day"]

    assert day["items"], "expected a plan to be produced"
    for item in day["items"]:
        assert foods.diet_ok(foods.BY_KEY[item["key"]], diet), \
            f"{item['key']} is not allowed on a {diet} diet"


def test_a_tight_budget_excludes_the_expensive_proteins():
    day = planner.plan({**BASE}, kcal=2200, lbm_kg=58.0, goal="cut",
                       budget="tight")["day"]
    used = {i["key"] for i in day["items"]}
    assert not (used & planner.PRICEY), f"tight budget reached for {used & planner.PRICEY}"


def test_a_flexible_budget_is_allowed_to_use_them():
    """The counterpart to the test above — otherwise it would pass with the pool empty."""
    plans = [
        planner.plan({**BASE}, kcal=k, lbm_kg=lbm, goal="cut", budget="flexible")["day"]
        for k, lbm in [(1900, 65.0), (2200, 58.0), (2600, 70.0)]
    ]
    assert any({i["key"] for i in d["items"]} & planner.PRICEY for d in plans)


def test_a_disliked_food_stays_out_of_the_plan():
    day = planner.plan({**BASE}, kcal=2100, lbm_kg=60.0, goal="cut",
                       dislikes="I can't stand eggs")["day"]
    assert "eggs_whole" not in {i["key"] for i in day["items"]}
    assert "eggs_whole" in day["excluded"]


def test_an_allergy_stays_out_of_the_plan():
    day = planner.plan({**BASE}, kcal=2100, lbm_kg=60.0, goal="cut",
                       allergies="peanuts")["day"]
    used = {i["key"] for i in day["items"]}
    assert "peanuts" not in used and "peanut_butter" not in used


def test_excluding_food_does_not_quietly_wreck_the_targets():
    """
    Removing options should cost accuracy slowly, not fall off a cliff.

    The plan still has to be usable for someone who won't eat eggs or dairy.
    """
    day = planner.plan({**BASE}, kcal=2100, lbm_kg=60.0, goal="cut",
                       dislikes="eggs, milk, curd")["day"]
    assert day["totals"]["kcal"]["close_enough"]
    assert day["totals"]["protein_g"]["planned"] > 0


# ===========================================================================
#  MEALS
# ===========================================================================

@pytest.mark.parametrize("meals", [1, 2, 3, 4, 5, 6])
def test_the_day_splits_into_the_requested_number_of_meals(meals):
    inp = {**BASE, "meals": meals}
    day = planner.plan(inp, kcal=2400, lbm_kg=60.0, goal="maintain")["day"]
    assert len(day["meals"]) == meals


def test_no_meal_is_left_without_protein():
    """
    Total daily protein is what drives the result, so this isn't arithmetic.

    It's about whether the plan gets followed: a meal with no protein in it is
    the one that gets skipped or swapped for whatever's nearby.
    """
    day = planner.plan({**BASE, "meals": 4}, kcal=2400, lbm_kg=60.0,
                       goal="maintain")["day"]
    for meal in day["meals"]:
        assert meal["protein_g"] > 0, f"{meal['label']} has no protein in it"


def test_meals_are_roughly_even_in_size():
    """
    An 839 kcal meal next to a 157 kcal one is a plan nobody follows.

    That was the real behaviour before the day was split into half portions
    before being dealt out, so this test is guarding a fix, not a preference.
    """
    day = planner.plan({**BASE, "meals": 4}, kcal=2400, lbm_kg=60.0,
                       goal="maintain")["day"]
    sizes = [m["kcal"] for m in day["meals"]]
    assert min(sizes) >= 0.55 * max(sizes), f"meals too uneven: {sizes}"


def test_the_meals_contain_every_item_from_the_day():
    """Nothing may be dropped or duplicated on the way into the meal split."""
    day = planner.plan({**BASE, "meals": 3}, kcal=2200, lbm_kg=58.0,
                       goal="cut")["day"]

    for field in ("kcal", "protein_g"):
        in_meals = sum(i[field] for m in day["meals"] for i in m["items"])
        in_items = sum(i[field] for i in day["items"])
        assert in_meals == pytest.approx(in_items, abs=2.0), field


# ===========================================================================
#  WHEN IT CAN'T HIT THE TARGET, IT SAYS SO
# ===========================================================================

def test_an_unreachable_protein_target_is_explained_not_hidden():
    """
    A tight-budget eggetarian cut with high lean mass genuinely can't get there.

    The right behaviour is to name the constraint and offer the lever, not to
    ship a plan that misses and stay quiet about it.
    """
    inp = {**BASE, "diet": "eggetarian", "weight_kg": 95}
    day = planner.plan(inp, kcal=2000, lbm_kg=76.0, goal="cut", budget="tight")["day"]

    protein = day["totals"]["protein_g"]
    if not protein["close_enough"] and protein["difference"] < 0:
        assert day["check"], "a missed protein target must carry an explanation"
        note = next(n for n in day["check"] if "Protein" in n["what"])
        assert note["options"], "an explanation without options isn't actionable"


def test_bands_are_published_with_the_numbers():
    """A coach can't judge "close enough" without being told what it means."""
    day = planner.plan({**BASE}, kcal=2093, lbm_kg=60.0, goal="cut")["day"]
    for value in day["totals"].values():
        assert "allowed_under_pct" in value
        assert "allowed_over_pct" in value


# ===========================================================================
#  THE ENDPOINTS
# ===========================================================================

def test_the_meal_plan_endpoint_refuses_anonymous_callers():
    """It's coach-only. This is the test that fails if the dependency is dropped."""
    anon = TestClient(app)
    r = anon.post("/api/meal-plan", json={**BASE, "budget": "moderate"})
    assert r.status_code in (401, 503)


def test_the_meal_plan_endpoint_returns_the_working_and_the_food(coach):
    r = coach.post("/api/meal-plan", json={**BASE, "budget": "moderate"})
    assert r.status_code == 200
    body = r.json()

    assert [s["macro"] for s in body["math"]["steps"]] == ["Protein", "Fat", "Carbs"]
    assert body["math"]["check"]["matches"]
    assert body["day"]["items"] and body["day"]["meals"]
    assert body["sources"], "the numbers must carry their citations"


def test_the_plan_carries_the_safety_verdict(coach):
    """
    Hitting the macros perfectly doesn't make an unsafe calorie target safe.

    The flag has to appear on this screen too — a coach working from the meal
    plan may never open the assessment.
    """
    r = coach.post("/api/meal-plan", json={
        **BASE, "sex": "female", "weight_kg": 48, "height_cm": 155,
        "goal": "aggressive_cut", "budget": "moderate",
    })
    assert r.status_code == 200
    assert "safety" in r.json()


def test_a_plan_can_be_built_straight_from_a_submitted_survey(coach):
    """
    The path that makes the questionnaire worth asking.

    Diet, budget, dislikes and allergies all come from what the client filled in,
    which is exactly where re-typing loses a detail like "no eggs".
    """
    invite = coach.post("/api/invites", json={"label": "planner test"}).json()
    token = invite["token"]

    answers = {
        "full_name": "Test Client", "contact": "test@example.com",
        "age": 30, "sex": "male", "height_cm": 175, "weight_kg": 80,
        "goal": "cut", "diet": "vegetarian", "budget": "tight",
        "dislikes": "eggs", "sessions_per_week": 4,
    }
    submitted = TestClient(app).post(
        f"/api/intake/{token}", json={"answers": answers, "consent": True},
    )
    assert submitted.status_code in (200, 201), submitted.text
    # The submit response deliberately carries no id — the client filling in the
    # form has no business holding a handle to the coach's records. So the id
    # comes from the coach's own list, which is the only place it's exposed.
    intake_id = coach.get("/api/intakes").json()["intakes"][0]["id"]

    r = coach.post(f"/api/intakes/{intake_id}/meal-plan")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["input"]["diet"] == "vegetarian"
    assert body["input"]["budget"] == "tight"
    # It used the survey, so no meat and nothing expensive.
    used = {i["key"] for i in body["day"]["items"]}
    assert not (used & planner.PRICEY)
    for key in used:
        assert foods.diet_ok(foods.BY_KEY[key], "vegetarian")
    # Defaults it had to invent are declared rather than applied silently.
    assert body["from_intake"]["assumed"]


def test_building_a_plan_from_a_missing_survey_is_a_404(coach):
    assert coach.post("/api/intakes/999999/meal-plan").status_code == 404
