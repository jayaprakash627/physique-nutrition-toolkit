"""
The front door, in a browser.

The API tests already prove /api/assess returns the right numbers. What they
cannot prove is that pressing the button shows them to a person — that the form
is wired up, the result replaces the form, and the number a client reads is the
number the engine produced.
"""

import re

import pytest

pytestmark = pytest.mark.e2e


def test_the_calculator_answers_without_any_login(page):
    """It's the lead magnet. If it ever needs a login, that's the whole point gone."""
    page.click("#quickBtn")
    page.wait_for_selector("#resultStep:not([hidden])", timeout=15_000)

    headline = page.locator("#resultStep").inner_text()
    assert re.search(r"[\d,]{3,}\s*calories", headline, re.I), headline


def test_the_form_is_replaced_by_the_answer(page):
    """A form still sitting above the answer is how people miss the answer."""
    page.click("#quickBtn")
    page.wait_for_selector("#resultStep:not([hidden])", timeout=15_000)
    assert page.locator("#startStep").is_hidden()


def test_the_number_on_screen_is_the_number_the_api_returned(page, server):
    """
    Guards against the display drifting from the calculation.

    Reads the same inputs back through the API and asserts the browser is showing
    that figure — not a rounded, stale or re-derived one.
    """
    page.click("#quickBtn")
    page.wait_for_selector("#resultStep:not([hidden])", timeout=15_000)

    expected = page.evaluate("""async () => {
      const r = await fetch('/api/assess', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sex:'male', age:25, weight_kg:75, height_cm:175,
                              goal:'cut', activity:'moderate', diet:'omnivore'})
      });
      return (await r.json()).nutrition.kcal.number;
    }""")

    shown = page.locator("#resultStep").inner_text().replace(",", "")
    assert str(int(expected)) in shown, f"expected {expected} on screen, got: {shown[:300]}"


def test_coach_mode_shows_a_lock_not_a_client_list(page):
    """The browser-level version of the auth boundary: nothing leaks before login."""
    page.get_by_role("tab", name="Coach mode").click()
    page.wait_for_selector("#coachLogin:not([hidden])", timeout=10_000)

    assert page.locator("#coachWorkspace").is_hidden()
    body = page.locator("#panel-coach").inner_text().lower()
    assert "password" in body
