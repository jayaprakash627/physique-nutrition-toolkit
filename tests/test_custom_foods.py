"""
test_custom_foods.py — foods the coach adds themselves.

Two things are being protected.

**The curated knowledge base stays curated.** `app/knowledge/foods.py` is cited to
IFCT 2017 and USDA and carries a promise that a dietitian can verify every number
in it without reading application code. Custom foods are merged in at request
time and must never be written into it — a file holding verified and unverified
numbers side by side, with nothing to tell them apart, would end that promise
silently.

**A mistyped food is caught at the door.** It would otherwise poison every plan
it appears in and every grocery bill derived from one, and nothing downstream
would look wrong.
"""

import os
import tempfile

import pytest
from pydantic import ValidationError

os.environ.setdefault("TOOLKIT_DB", os.path.join(tempfile.mkdtemp(), "custom.db"))

from app import catalog, costing, planner                 # noqa: E402
from app.knowledge import foods                           # noqa: E402
from app.models import CustomFoodIn                       # noqa: E402

RAGI = dict(
    name="Ragi (finger millet)", household="1 katori cooked", portion_grams=150,
    category="plant", kcal_100g=336, protein_100g=7.3, carb_100g=72,
    fat_100g=1.3, fibre_100g=11.5, unit="kg", price=70, raw_factor=0.4,
)


def _record(**over):
    payload = CustomFoodIn(**{**RAGI, **over})
    return catalog.to_record(payload, catalog.make_key(payload.name, set()))


# ===========================================================================
#  THE CURATED LIST IS NEVER TOUCHED
# ===========================================================================

def test_merging_does_not_mutate_the_cited_knowledge_base():
    """The whole reason custom foods live in a table and not in that file."""
    before_all = len(foods.ALL_FOODS)
    before_keys = set(foods.BY_KEY)

    merged = catalog.by_key([_record()])

    assert len(merged) == before_all + 1
    assert len(foods.ALL_FOODS) == before_all, "the curated list was appended to"
    assert set(foods.BY_KEY) == before_keys, "the curated index was mutated"


def test_a_custom_food_is_marked_as_the_coachs_own():
    """A coach has to be able to tell a checked number from one they typed."""
    assert _record()["is_custom"] is True
    assert all(not f.get("is_custom") for f in foods.ALL_FOODS)


def test_custom_keys_cannot_collide_with_curated_ones():
    key = catalog.make_key("chicken breast", set(foods.BY_KEY))
    assert key not in foods.BY_KEY
    assert key.startswith(catalog.CUSTOM_PREFIX)


def test_two_foods_with_the_same_name_both_survive():
    """Silently overwriting the first would look exactly like the save failing."""
    first = catalog.make_key("Protein bar", set())
    second = catalog.make_key("Protein bar", {first})
    assert first != second


def test_custom_foods_make_no_micronutrient_claims():
    """
    The curated entries list only nutrients a food is a genuinely good source of,
    from a published table. Letting a coach assert that from memory would put
    unverifiable claims into the panel that tells a vegan where to get B12.
    """
    assert _record()["micros"] == []


# ===========================================================================
#  A MISTYPED FOOD IS REFUSED
# ===========================================================================

def test_calories_that_disagree_with_the_macros_are_refused():
    with pytest.raises(ValidationError) as e:
        CustomFoodIn(**{**RAGI, "kcal_100g": 33})       # a stray zero
    assert "don't add up" in str(e.value)


def test_macros_that_exceed_the_hundred_grams_they_are_in_are_refused():
    with pytest.raises(ValidationError) as e:
        CustomFoodIn(**{**RAGI, "protein_100g": 73})    # 73 + 72 + 1.3 > 100
    assert "more than" in str(e.value)


def test_label_rounding_is_tolerated():
    """
    Labels round, fibre is counted differently by different manufacturers, and
    sugar alcohols don't carry 4 kcal. Rejecting a small disagreement would be
    pedantic and would block real foods.
    """
    CustomFoodIn(**{**RAGI, "kcal_100g": 329})          # implied ~329, stated 336 nearby
    CustomFoodIn(**{**RAGI, "kcal_100g": 350})


def test_a_food_sold_by_the_piece_needs_a_piece_weight():
    with pytest.raises(ValidationError) as e:
        CustomFoodIn(**{**RAGI, "unit": "piece", "piece_grams": None})
    assert "one piece weighs" in str(e.value).lower()


# ===========================================================================
#  PER 100 G IN, PER PORTION OUT
# ===========================================================================

def test_the_portion_is_derived_from_the_label_figures():
    """A coach types what the packet says; the app does the arithmetic."""
    r = _record()                                        # 150 g portion
    assert r["kcal"] == round(336 * 1.5)
    assert r["protein_g"] == pytest.approx(7.3 * 1.5, abs=0.1)
    assert r["fibre_g"] == pytest.approx(11.5 * 1.5, abs=0.1)


def test_the_category_becomes_the_right_diet_tags():
    """A coach picks "plant" or "dairy" — the tag vocabulary is internal."""
    assert foods.diet_ok(_record(category="plant"), "vegan")
    assert not foods.diet_ok(_record(category="dairy"), "vegan")
    assert not foods.diet_ok(_record(category="egg"), "vegetarian")
    assert not foods.diet_ok(_record(category="meat_fish"), "eggetarian")


# ===========================================================================
#  THE PLANNER AND THE BILL BOTH SEE IT
# ===========================================================================

def test_the_planner_can_use_a_custom_food():
    """
    Added and then never reachable would be the worst outcome: the coach sees it
    listed and silently never gets it in a plan.
    """
    # Something protein-dense enough that the search has a reason to pick it.
    powder = _record(name="House protein blend", portion_grams=30, category="plant",
                     kcal_100g=380, protein_100g=80, carb_100g=8, fat_100g=4,
                     fibre_100g=0, price=1500)
    book = catalog.by_key([powder])
    day = planner.plan({"weight_kg": 75, "diet": "vegan", "meals": 4},
                       kcal=2200, lbm_kg=60.0, goal="cut", book=book)["day"]
    assert any(i["key"] == powder["key"] for i in day["items"]), \
        f"custom food never used: {[i['key'] for i in day['items']]}"


def test_a_custom_food_is_priced_rather_than_left_off_the_bill():
    ragi = _record()
    book = catalog.by_key([ragi])
    day = {"items": [{"key": ragi["key"], "name": ragi["name"], "grams": 300}]}

    c = costing.cost_day(day, catalog.custom_prices([ragi]),
                         table=catalog.purchase([ragi]), book=book)
    assert not c["unpriced"], "a custom food fell off the bill"
    assert c["items"][0]["cost"] > 0
    # Its buying multiplier is honoured like any curated food's.
    assert c["items"][0]["raw_factor"] == 0.4
    assert c["items"][0]["buy"] == "120 g"               # 300 g eaten × 0.4


def test_a_custom_food_respects_the_clients_diet():
    """Adding a fish must not make it appear in a vegetarian's plan."""
    fish = _record(name="Seer fish", category="meat_fish", kcal_100g=110,
                   protein_100g=22, carb_100g=0, fat_100g=2.5, fibre_100g=0, price=700)
    book = catalog.by_key([fish])
    day = planner.plan({"weight_kg": 75, "diet": "vegetarian", "meals": 4},
                       kcal=2200, lbm_kg=58.0, goal="cut", book=book)["day"]
    assert all(i["key"] != fish["key"] for i in day["items"])


def test_a_disliked_custom_food_is_excluded_like_any_other():
    ragi = _record()
    book = catalog.by_key([ragi])
    day = planner.plan({"weight_kg": 75, "diet": "vegetarian", "meals": 4},
                       kcal=2200, lbm_kg=58.0, goal="cut",
                       dislikes="ragi", book=book)["day"]
    assert all(i["key"] != ragi["key"] for i in day["items"])


def test_plans_still_work_with_no_custom_foods_at_all():
    """The common case, and the one a regression here would break."""
    day = planner.plan({"weight_kg": 75, "diet": "omnivore", "meals": 4},
                       kcal=2093, lbm_kg=61.0, goal="cut", book=catalog.by_key([]))["day"]
    assert day["items"] and day["all_close"]
