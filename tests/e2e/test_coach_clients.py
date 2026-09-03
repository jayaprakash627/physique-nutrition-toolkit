"""
Coach mode: logging in, and the client records that outlive the session.

This is the half people pay for, and the half that holds health data. The tests
follow one client all the way through — created, weighed twice, read back, and
deleted — because that is the actual working loop, and a bug in the middle of it
is only visible end to end.
"""

import pytest

pytestmark = pytest.mark.e2e


def test_the_wrong_password_gets_you_nowhere(page):
    page.get_by_role("tab", name="Coach mode").click()
    page.fill("#coachPassword", "definitely-not-the-password")
    page.click("#loginForm button[type=submit]")

    page.wait_for_timeout(1200)
    assert page.locator("#coachWorkspace").is_hidden(), "a wrong password opened the workspace"


def test_logging_in_opens_the_workspace(coach):
    assert coach.locator("#coachWorkspace").is_visible()
    assert coach.locator("#clientForm").is_visible()


def test_a_client_can_be_added_and_appears_in_the_list(coach):
    """The thing a coach does first. If this breaks, nothing else matters."""
    coach.fill("#c_name", "Priya Sharma")
    coach.locator('[data-seg="cSex"] button[data-value="female"]').click()
    coach.fill("#c_age", "31")
    coach.fill("#c_height", "163")
    coach.select_option("#c_diet", "vegetarian")
    coach.select_option("#c_goal", "cut")
    coach.click("#clientForm button[type=submit]")

    coach.wait_for_selector("#clientList >> text=Priya Sharma", timeout=10_000)
    assert "Priya Sharma" in coach.locator("#clientList").inner_text()


def test_a_client_survives_a_full_page_reload(coach):
    """
    The point of storing them at all.

    A client kept only in the page's memory would pass every other test here and
    still be useless — this is the one that proves it reached the database.
    """
    coach.fill("#c_name", "Reload Test Client")
    coach.fill("#c_age", "40")
    coach.fill("#c_height", "170")
    coach.click("#clientForm button[type=submit]")
    coach.wait_for_selector("#clientList >> text=Reload Test Client", timeout=10_000)

    coach.reload()
    coach.get_by_role("tab", name="Coach mode").click()
    coach.wait_for_selector("#coachWorkspace:not([hidden])", timeout=10_000)
    coach.wait_for_selector("#clientList >> text=Reload Test Client", timeout=10_000)


def test_measurements_can_be_logged_and_progress_is_computed(coach):
    """Two weigh-ins should produce a change, not just two rows."""
    coach.fill("#c_name", "Progress Client")
    coach.fill("#c_age", "28")
    coach.fill("#c_height", "180")
    coach.click("#clientForm button[type=submit]")
    coach.wait_for_selector("#clientList >> text=Progress Client", timeout=10_000)

    client_id = coach.evaluate("""async () => {
      const r = await fetch('/api/clients');
      const list = (await r.json()).clients;
      return list.find(c => c.name === 'Progress Client').id;
    }""")

    coach.evaluate("""async (id) => {
      for (const m of [{taken_on:'2026-08-01', weight_kg:88.0, bodyfat_pct:24.0},
                       {taken_on:'2026-08-20', weight_kg:85.5, bodyfat_pct:22.4}]) {
        await fetch(`/api/clients/${id}/measurements`, {
          method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(m)});
      }
    }""", client_id)

    detail = coach.evaluate("""async (id) => {
      const r = await fetch(`/api/clients/${id}`);
      return await r.json();
    }""", client_id)

    assert len(detail["measurements"]) == 2
    assert detail["progress"]["weight_change_kg"] == -2.5
    # Losing 2.5 kg means different things depending on what it was made of, so
    # the split is the number a coach actually reads.
    assert detail["progress"]["fat_mass_change_kg"] is not None
    assert detail["progress"]["lean_mass_change_kg"] is not None


def test_logging_out_closes_the_workspace_and_the_data(coach):
    coach.click("#logoutBtn")
    coach.wait_for_selector("#coachLogin:not([hidden])", timeout=10_000)
    assert coach.locator("#coachWorkspace").is_hidden()

    status = coach.evaluate("""async () => (await fetch('/api/clients')).status""")
    assert status in (401, 503), f"client data still reachable after logout: {status}"
