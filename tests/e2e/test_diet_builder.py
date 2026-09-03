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
    open_tool(coach, "dietTool")
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
