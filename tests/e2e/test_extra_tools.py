"""
The Extra tools and Learn tabs, which had no browser coverage at all.

These are public and they carry numbers a client may act on, so "the form
submits and something numeric appears" is the minimum bar. The maths itself is
covered by the unit tests; what is checked here is that the wiring exists and
that the answer reaches the screen.
"""

import re

import pytest

from .conftest import open_all_tools

pytestmark = pytest.mark.e2e


def _tab(page, name, panel):
    """
    Switch tabs and wait for the panel, not for a fixed delay.

    Everything inside a hidden panel is invisible to Playwright, so asserting on
    a child before the switch completes times out on an element that is present
    and correct — which reads like a broken feature.
    """
    page.get_by_role("tab", name=name).click()
    page.wait_for_selector(f"#{panel}:not([hidden])", timeout=10_000)
    open_all_tools(page, panel)


def test_the_body_fat_comparison_runs_and_shows_more_than_one_method(page):
    """
    The point of this tool is the disagreement between methods, not one number.

    If it ever rendered a single figure, the honesty the README claims for it
    would be gone and nothing would look broken.
    """
    _tab(page, "Extra tools", "panel-tools")
    page.fill("#bf_age", "30")
    page.fill("#bf_weight", "80")
    page.fill("#bf_height", "178")
    # Without girths only Deurenberg can run, and there is nothing to compare —
    # the disagreement between methods is the whole point of this tool.
    page.fill("#bf_neck", "38")
    page.fill("#bf_waist", "88")
    page.click("#bfForm button[type=submit]")
    page.wait_for_selector("#bfResults >> text=/%/", timeout=15_000)

    text = page.locator("#bfResults").inner_text()
    percents = re.findall(r"\d+\.?\d*\s*%", text)
    assert len(percents) >= 2, f"expected several methods, saw: {percents}"


def test_the_contest_prep_planner_gives_a_verdict(page):
    _tab(page, "Extra tools", "panel-tools")
    page.fill("#p_weight", "85")
    page.fill("#p_current", "20")
    page.fill("#p_target", "12")
    page.fill("#p_weeks", "16")
    page.click("#prepForm button[type=submit]")
    page.wait_for_function(
        "() => document.getElementById('prepResults').innerText.trim().length > 40",
        timeout=20_000)
    assert page.locator("#prepResults").inner_text().strip()


def test_an_impossible_prep_timeline_is_refused_not_flattered(page):
    """
    The app's stated behaviour is to block rather than produce a harmful number.

    20% to 6% in three weeks is not achievable; a tool that returns a tidy
    weekly rate for it is lying to someone about to starve themselves.
    """
    _tab(page, "Extra tools", "panel-tools")
    page.fill("#p_weight", "85")
    page.fill("#p_current", "20")
    page.fill("#p_target", "6")
    page.fill("#p_weeks", "3")
    page.click("#prepForm button[type=submit]")
    page.wait_for_function(
        "() => document.getElementById('prepResults').innerText.trim().length > 40",
        timeout=20_000)

    verdict = page.locator("#prepResults").inner_text().lower()
    # Checked against what the app actually emits — safety.check_prep raises
    # "This timeline isn't safe" and marks the plan blocked — rather than against
    # wording I guessed it might use.
    assert "isn't safe" in verdict or "not safe" in verdict, verdict[:400]


def test_the_one_rep_max_tool_returns_a_loading_table(page):
    _tab(page, "Extra tools", "panel-tools")
    page.fill("#st_weight", "100")
    page.fill("#st_reps", "5")
    page.click("#strForm button[type=submit]")
    # Wait for CONTENT, not the container. #strResults is an empty div that
    # already exists, so waiting for the selector returns instantly and the
    # assertion runs against nothing — the same premature-read mistake that made
    # a working feature look broken elsewhere in this suite.
    page.wait_for_selector("#strResults table", timeout=20_000)

    text = page.locator("#strResults").inner_text()
    assert "%" in text, "expected a % of 1RM table"
    assert "1RM" in text


def test_the_learn_tab_loads_the_reference_without_a_login(page):
    """It is the public education surface — it must not need coach mode."""
    _tab(page, "Learn", "panel-learn")
    page.wait_for_selector("#sourceList a", timeout=20_000)

    cites = page.locator("#sourceList a").count()
    assert cites >= 10, f"expected the cited standards to load, saw {cites}"


def test_the_theme_toggle_actually_changes_the_theme(page):
    before = page.evaluate("document.documentElement.dataset.theme")
    page.click("#themeToggle")
    page.wait_for_timeout(500)
    after = page.evaluate("document.documentElement.dataset.theme")
    assert before != after, f"theme did not change: {before} -> {after}"


def test_the_calculator_works_on_a_phone_sized_screen(page):
    """
    Most clients will open this on a phone.

    Checked for the specific failure that makes a page unusable rather than
    merely ugly: content wider than the screen, which forces sideways scrolling.
    """
    page.set_viewport_size({"width": 375, "height": 812})
    page.reload()
    page.wait_for_selector("#quickBtn", timeout=15_000)
    page.click("#quickBtn")
    page.wait_for_selector("#resultStep:not([hidden])", timeout=20_000)

    overflow = page.evaluate("""() => {
      const doc = document.documentElement;
      return {scroll: doc.scrollWidth, client: doc.clientWidth};
    }""")
    assert overflow["scroll"] <= overflow["client"] + 2, (
        f"the page scrolls sideways on a phone: {overflow}"
    )
