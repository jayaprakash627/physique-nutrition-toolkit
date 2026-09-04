"""
test_costing.py — the grocery cost of a plan.

The arithmetic here is easy; the units are not, and that is where a wrong number
would hide. Two conversions have to hold or every total is quietly wrong:

  * you buy in kg, litres and pieces, not in the grams the plan is written in
  * the plan is COOKED weight and you buy RAW — meat gets heavier, rice and dal
    get much lighter

Neither would raise an exception if it broke. The plan would still render, the
totals would still add up, and a coach would quote a client a food budget that is
40% out. So these tests check the conversions directly, against hand-worked
figures, rather than only checking that a number came back.
"""

import os
import tempfile

import pytest

os.environ.setdefault("TOOLKIT_DB", os.path.join(tempfile.mkdtemp(), "cost.db"))

from app import costing, planner                    # noqa: E402
from app.knowledge import foods                     # noqa: E402

BASE = {"weight_kg": 75, "diet": "omnivore", "meals": 4}


def _day(**kw):
    return planner.plan(BASE, kcal=2093, lbm_kg=61.0, goal="cut", **kw)["day"]


# ===========================================================================
#  EVERY FOOD IS PRICEABLE
# ===========================================================================

def test_every_food_the_planner_can_use_has_a_price():
    """
    A food with no purchase data drops out of the bill.

    The plan would still show it on the plate, so the coach sees the food and a
    total that doesn't include it — the worst kind of wrong, because nothing
    looks broken.
    """
    missing = [f["key"] for f in foods.ALL_FOODS if f["key"] not in costing.PURCHASE]
    assert not missing, f"no purchase data for: {missing}"


def test_purchase_rows_are_internally_consistent():
    for key, row in costing.PURCHASE.items():
        assert row["unit"] in (costing.KG, costing.LITRE, costing.PIECE), key
        assert row["unit_grams"] > 0, key
        assert 0 < row["raw_factor"] <= 3, f"{key} has an implausible raw factor"
        assert row["price"] > 0, key


# ===========================================================================
#  COOKED → RAW, THE CONVERSION THAT WOULD BE SILENTLY WRONG
# ===========================================================================

def test_meat_is_bought_heavier_than_it_is_eaten():
    """150 g of cooked chicken started as more than 150 g raw. Costing the cooked
    weight would understate every non-veg plan."""
    q = costing._quantity("chicken_breast", 150)
    assert q["raw_grams"] > 150
    assert q["raw_grams"] == pytest.approx(210, abs=1)


def test_rice_and_dal_are_bought_much_lighter_than_they_are_eaten():
    """The opposite error, and the larger one: a katori of cooked rice is a
    fraction of its weight in raw rice."""
    rice = costing._quantity("rice_cooked", 150)
    dal = costing._quantity("toor_dal", 150)
    assert rice["raw_grams"] == pytest.approx(57, abs=1)
    assert dal["raw_grams"] == pytest.approx(53, abs=1)
    # Getting this wrong would roughly triple the grain and pulse bill.
    assert rice["raw_grams"] < 150 / 2


def test_ignoring_the_raw_conversion_would_visibly_change_the_bill():
    """
    Guards the whole point of raw_factor.

    If someone ever "simplifies" it away, this fails loudly rather than the app
    quietly producing a plausible, wrong total.
    """
    day = _day()
    real = costing.cost_day(day)

    flat = {k: {**v, "raw_factor": 1.0} for k, v in costing.PURCHASE.items()}
    original, costing.PURCHASE = costing.PURCHASE, flat
    try:
        naive = costing.cost_day(day)
    finally:
        costing.PURCHASE = original

    assert real["per_day"] != pytest.approx(naive["per_day"], rel=0.05), (
        "raw/cooked conversion is not affecting the total — it has been lost"
    )


# ===========================================================================
#  UNITS
# ===========================================================================

def test_eggs_are_counted_not_weighed():
    """Nobody buys 150 g of egg. Three eggs is three eggs."""
    q = costing._quantity("eggs_whole", 150)
    assert q["unit"] == costing.PIECE
    assert q["units"] == 3
    assert "egg" in costing._display("eggs_whole", q)


def test_pieces_are_always_whole_numbers():
    """You cannot buy 2.4 eggs, and a shopping list saying so is a bug."""
    for grams in (75, 150, 210, 400):
        q = costing._quantity("eggs_whole", grams)
        assert float(q["units"]).is_integer(), f"{grams} g gave {q['units']} eggs"


def test_liquids_are_bought_by_the_litre_and_oil_is_lighter_than_water():
    milk = costing.PURCHASE["milk_toned"]
    oil = costing.PURCHASE["oil"]
    assert milk["unit"] == costing.LITRE and oil["unit"] == costing.LITRE
    assert oil["unit_grams"] < milk["unit_grams"], "a litre of oil weighs less than a litre of milk"


def test_egg_whites_are_priced_as_whole_eggs():
    """You pay for the yolk you throw away — pricing them any other way makes egg
    whites look cheaper than they are."""
    assert costing.PURCHASE["egg_whites"]["price"] == costing.PURCHASE["eggs_whole"]["price"]


# ===========================================================================
#  THE BILL
# ===========================================================================

def test_the_total_is_the_sum_of_the_lines():
    c = costing.cost_day(_day())
    assert sum(i["cost"] for i in c["items"]) == pytest.approx(c["total"], abs=0.05)


def test_weekly_and_monthly_track_the_daily_figure_without_being_a_multiple_of_it():
    """
    Close to the daily figure scaled up, but deliberately not equal to it.

    Equal would mean the rounding of whole-unit foods was being applied once per
    day and multiplied, which understates the bill — see the week test below.
    Wildly different would mean the scaling is broken. This pins it between the
    two.
    """
    c = costing.cost_day(_day())
    assert c["per_day"] * 7 <= c["per_week"] <= c["per_day"] * 7 * 1.15
    assert c["per_day"] * 30 <= c["per_month"] <= c["per_day"] * 30 * 1.15


def test_a_week_is_priced_as_a_week_not_as_seven_rounded_days():
    """
    Whole-unit foods have to round, and rounding seven times is not the same as
    rounding once.

    4.5 eggs a day rounds to 4, and seven of those is 28 — but the week genuinely
    needs 31.5, so you buy 32. Multiplying a rounded day understates the bill,
    always in the same direction, and the error grows with the number of
    piece-priced foods. The weekly figure must come from a week's quantities.
    """
    one = costing.cost_day(_day(), days=1)
    seven = costing.cost_day(_day(), days=7)

    assert seven["total"] == pytest.approx(one["per_week"], rel=0.01), (
        "per_week is not being computed at a week's scale"
    )
    # And it is at least as much as the naive multiplication, never less.
    assert one["per_week"] >= one["per_day"] * 7 - 0.01


def test_a_coachs_own_price_changes_the_total():
    day = _day()
    before = costing.cost_day(day)
    after = costing.cost_day(day, {"chicken_breast": 900})
    if any(i["key"] == "chicken_breast" for i in before["items"]):
        assert after["total"] > before["total"]


def test_the_biggest_line_is_identified():
    """The single most useful thing a coach reads here: what to change first."""
    c = costing.cost_day(_day())
    assert c["biggest"] is not None
    assert c["biggest"]["cost"] == max(i["cost"] for i in c["items"])
    assert 0 < c["biggest_share_pct"] <= 100


def test_nothing_is_dropped_from_the_bill_without_saying_so():
    c = costing.cost_day(_day())
    priced = {i["key"] for i in c["items"]}
    for item in _day()["items"]:
        assert item["key"] in priced or item["name"] in c["unpriced"]


@pytest.mark.parametrize("diet", ["omnivore", "eggetarian", "vegetarian", "vegan"])
@pytest.mark.parametrize("budget", ["tight", "moderate", "flexible"])
def test_every_diet_and_budget_produces_a_priced_plan(diet, budget):
    day = planner.plan({**BASE, "diet": diet}, kcal=2200, lbm_kg=58.0,
                       goal="cut", budget=budget)["day"]
    c = costing.cost_day(day)
    assert c["items"], f"{diet}/{budget} priced nothing"
    assert c["per_day"] > 0
    assert not c["unpriced"], f"{diet}/{budget} left {c['unpriced']} unpriced"


def test_a_tight_budget_plan_costs_less_than_a_flexible_one():
    """
    The budget setting has to mean something in rupees, not just in food choice.

    This is the assertion that would catch PRICEY being emptied or the budget
    filter being bypassed — the plan would still look reasonable and cost more.
    """
    def cost(budget):
        day = planner.plan({**BASE, "diet": "omnivore"}, kcal=2200, lbm_kg=58.0,
                           goal="cut", budget=budget)["day"]
        return costing.cost_day(day)["per_day"]

    assert cost("tight") < cost("flexible")
