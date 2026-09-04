"""
The diet builder, in a browser.

Its promise is that the arithmetic on screen is the arithmetic that produced the
plan. A unit test can compare two Python values; only this can confirm the coach
is actually shown them — and that the check line adds up on the page.
"""

import re

import pytest

from .conftest import meal_text, open_tool

pytestmark = pytest.mark.e2e



def _build(coach, **fields):
    """
    Build a plan and wait for THIS plan, not the last one.

    The result box is emptied first. Without that, waiting for `.mp-step` returns
    instantly because the previous plan's markup is still on the page, and the
    assertions then run against stale numbers — which is exactly how a test that
    re-prices a food and re-builds could report that the cost never moved while
    the backend was working correctly all along.
    """
    open_tool(coach, "dietTool")
    coach.evaluate("document.getElementById('dietResult').innerHTML = ''")
    for sel, val in fields.items():
        if sel.startswith("select:"):
            coach.select_option(f"#{sel[7:]}", val)
        else:
            coach.fill(f"#{sel}", val)
    coach.click("#dietForm button[type=submit]")
    coach.wait_for_selector("#dietResult .mp-step", timeout=20_000)
    return coach.locator("#dietResult")


def test_the_three_steps_are_shown_with_their_working(coach):
    box = _build(coach, d_weight="75", d_height="175")

    assert box.locator(".mp-step").count() == 3
    text = box.inner_text()
    for macro in ("Protein", "Fat", "Carbs"):
        assert macro in text
    # The arithmetic itself, not just the answer.
    assert "×" in text and "÷" in text


def test_the_check_line_actually_adds_up_on_screen(coach):
    """
    The load-bearing claim of the whole feature.

    Parses the three numbers out of the check line as rendered and adds them by
    hand. If the page ever showed a sum that didn't hold, a coach would stop
    trusting every other number on it — so this test does the arithmetic the
    coach would do.
    """
    box = _build(coach, d_weight="75", d_height="175")
    line = box.locator(".mp-check").first.inner_text()

    m = re.search(r"(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)\s*kcal.*?(\d+)\s*kcal target", line)
    assert m, f"could not read the check line: {line}"
    a, b, c, total, target = (int(x) for x in m.groups())

    assert a + b + c == total, f"{a} + {b} + {c} != {total}"
    assert abs(total - target) <= 12, f"sum {total} drifts from target {target}"
    assert "balances" in line


def test_every_macro_is_reported_against_its_target(coach):
    box = _build(coach, d_weight="75", d_height="175")
    table = box.locator("table").last.inner_text()
    for label in ("Calories", "Protein", "Carbs", "Fat", "Fibre"):
        assert label in table, f"{label} missing from the totals table"


def test_a_disliked_food_never_appears_in_the_plan(coach):
    box = _build(coach, d_weight="75", d_height="175", d_dislikes="eggs")
    assert "egg" not in meal_text(box)
    # And it says what it left out, so the coach can see the match landed.
    assert "eggs" in box.inner_text().lower()


def test_a_tight_budget_plan_avoids_the_expensive_proteins(coach):
    box = _build(coach, d_weight="75", d_height="175",
                 **{"select:d_budget": "tight", "select:d_diet": "vegetarian"})
    served = meal_text(box)
    for pricey in ("whey", "almond", "greek yogurt"):
        assert pricey not in served, f"tight budget served {pricey}"


def test_the_plan_splits_into_the_requested_meals(coach):
    box = _build(coach, d_weight="75", d_height="175", d_meals="3")
    assert box.locator(".mp-meal").count() == 3
    # Every meal needs protein in it, or it's the one that gets skipped.
    for i in range(3):
        assert re.search(r"[1-9]", box.locator(".mp-meal__macros").nth(i).inner_text())


def test_the_builder_is_refused_to_anyone_not_logged_in(page):
    """It's a coach feature. This fails if the auth dependency is ever dropped."""
    status = page.evaluate("""async () => {
      const r = await fetch('/api/meal-plan', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({sex:'male', age:28, weight_kg:75, height_cm:175, goal:'cut'})});
      return r.status;
    }""")
    assert status in (401, 503), f"meal plan reachable without a session: {status}"


# ===========================================================================
#  GROCERY COST
# ===========================================================================

def test_the_plan_shows_what_it_costs_to_buy(coach):
    box = _build(coach, d_weight="75", d_height="175")
    heads = box.locator(".cost-head")
    assert heads.count() == 3, "expected month, week and day figures"

    text = box.inner_text()
    assert "₹" in text
    # The shopping quantities, not the eaten weight — meat is heavier raw.
    assert "buy" in text.lower() or "Buy" in text


def test_the_cost_table_separates_what_you_eat_from_what_you_buy(coach):
    """
    The conversion that would otherwise be silently wrong.

    150 g of cooked chicken is ~210 g raw; 150 g of cooked rice is ~57 g raw.
    Both numbers have to be visible, or a coach cannot check the total.
    """
    box = _build(coach, d_weight="75", d_height="175")
    rows = box.inner_text().lower()
    assert "eat" in rows, "the eaten weight is not shown"
    # And at least one raw-weight explanation is surfaced.
    assert "raw" in rows or "cooked" in rows


def test_changing_a_price_changes_what_the_plan_costs(coach):
    """
    The whole point of an editable price list.

    The food to re-price is read off the plan rather than hardcoded. These tests
    share one server and database, so an earlier test adding a custom food can
    change which staples this plan reaches for — pinning it to chicken made the
    test pass or fail on execution order rather than on the behaviour it checks.
    """
    box = _build(coach, d_weight="75", d_height="175")
    before = box.locator(".cost-head__value").first.inner_text()

    # The most expensive line, which is guaranteed to move the total.
    key = box.evaluate("""(el) => {
      // the cost table is the second-to-last; its first row is the dearest item
      const tables = el.querySelectorAll('table');
      const costTable = tables[tables.length - 2];
      const name = costTable.querySelector('tbody tr .food-row__name').textContent.trim();
      const match = [...document.querySelectorAll('[data-price-key]')]
        .find(i => i.closest('tr').textContent.includes(name));
      return match ? match.dataset.priceKey : null;
    }""")
    assert key, "could not find a price field for the plan's dearest food"

    open_tool(coach, "pricesTool")
    field = coach.locator(f'[data-price-key="{key}"]')
    original = field.input_value()
    field.fill(str(round(float(original) * 3)))
    field.dispatch_event("change")
    coach.wait_for_selector(f'[data-reset-price="{key}"]', timeout=10_000)

    box = _build(coach, d_weight="75", d_height="175")
    after = box.locator(".cost-head__value").first.inner_text()
    assert after != before, f"monthly cost did not move: {before} -> {after}"

    # Put it back, and confirm the reset really restores the shipped default.
    coach.click(f'[data-reset-price="{key}"]')
    coach.wait_for_timeout(1000)
    assert coach.locator(f'[data-price-key="{key}"]').input_value() == original


def test_the_price_list_is_coach_only(page):
    status = page.evaluate("""async () => (await fetch('/api/prices')).status""")
    assert status in (401, 503), f"grocery prices reachable without a session: {status}"


# ===========================================================================
#  THE COACH'S OWN FOODS
# ===========================================================================

def _add_food(coach, **over):
    open_tool(coach, "foodsTool")
    fields = {
        "f_name": "Ragi millet", "f_household": "1 katori cooked", "f_portion": "150",
        "f_kcal": "336", "f_protein": "7.3", "f_carb": "72", "f_fat": "1.3",
        "f_fibre": "11.5", "f_price": "70", "f_raw": "0.4",
        **over,
    }
    for sel, val in fields.items():
        coach.fill(f"#{sel}", val)
    coach.click("#foodForm button[type=submit]")


def test_a_coach_can_add_their_own_food(coach):
    _add_food(coach)
    coach.wait_for_selector("#customFoodList >> text=Ragi millet", timeout=10_000)
    # The portion figures are derived from the per-100 g label numbers.
    assert "504" in coach.locator("#customFoodList").inner_text()


def test_a_mistyped_food_is_refused_with_a_readable_message(coach):
    """
    The message must be the sentence, not Pydantic's field path.

    "fat_100g: Value error, ..." buries the explanation a coach needs behind an
    internal field name.
    """
    _add_food(coach, f_name="Typo Food", f_kcal="33")
    coach.wait_for_selector(".toast", timeout=10_000)
    msg = coach.locator(".toast").inner_text()

    assert "don't add up" in msg
    assert "f_kcal" not in msg and "100g" not in msg and "Value error" not in msg
    assert "Typo Food" not in coach.locator("#customFoodList").inner_text()


def test_a_custom_food_reaches_the_diet_builder_and_the_bill(coach):
    _add_food(coach)
    coach.wait_for_selector("#customFoodList >> text=Ragi millet", timeout=10_000)

    box = _build(coach, d_weight="75", d_height="175",
                 **{"select:d_diet": "vegetarian"})
    panel = box.inner_text().lower()
    assert "ragi" in panel, "the coach's own food never appeared in the plan"
    # And it is priced rather than dropping off as unpriced.
    assert "not priced" not in panel


def test_a_custom_food_can_be_removed(coach):
    _add_food(coach, f_name="Temporary Food")
    coach.wait_for_selector("#customFoodList >> text=Temporary Food", timeout=10_000)

    # Target THIS food's button. Rows are sorted by name, so clicking the first
    # remove button deletes whichever food happens to sort earliest — which is
    # usually a different one left behind by an earlier test.
    coach.once("dialog", lambda d: d.accept())
    coach.locator("#customFoodList tr", has_text="Temporary Food") \
         .locator("[data-del-food]").click()
    coach.wait_for_timeout(1500)
    assert "Temporary Food" not in coach.locator("#customFoodList").inner_text()
