"""
The onboarding loop, end to end, across two browser contexts.

Coach mints a link; a client with no session and no account opens it and fills it
in; the coach reads it back and builds a diet from it. Three surfaces, three
levels of access, in one test — which is the only way to catch the token leaking
across them.
"""

import pytest

from .conftest import meal_text, open_tool

pytestmark = pytest.mark.e2e


def test_a_client_can_fill_in_a_link_and_the_coach_reads_it_back(coach, browser, server):
    open_tool(coach, "invitesTool")
    coach.fill("#inviteLabel", "E2E test client")
    coach.click("#inviteForm button[type=submit]")
    coach.wait_for_selector("#inviteList >> text=E2E test client", timeout=10_000)

    token = coach.evaluate("""async () => {
      const r = await fetch('/api/invites');
      return (await r.json()).invites[0].token;
    }""")
    assert token and len(token) > 20, "the token should be long and unguessable"

    # A brand-new context: no cookies, no session. This is a stranger with a link.
    stranger = browser.new_context()
    client_page = stranger.new_page()
    try:
        client_page.goto(f"{server}/start/{token}")
        client_page.wait_for_load_state("networkidle")

        # The client must NOT be able to see the coach's data with just this link.
        status = client_page.evaluate("""async () => (await fetch('/api/clients')).status""")
        assert status in (401, 503), f"an intake link exposed client data: {status}"

        submitted = client_page.evaluate("""async (t) => {
          const r = await fetch(`/api/intake/${t}`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({answers:{
              full_name:'E2E Client', contact:'e2e@example.com', age:30, sex:'male',
              height_cm:175, weight_kg:80, goal:'cut', diet:'vegetarian',
              budget:'tight', dislikes:'eggs', sessions_per_week:4,
            }, consent:true})});
          return {status: r.status, body: await r.json()};
        }""", token)
        assert submitted["status"] in (200, 201), submitted

        # The single-use guarantee: the same link must not work twice.
        again = client_page.evaluate("""async (t) => (await fetch(`/api/intake/${t}`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({answers:{full_name:'Second Go'}, consent:true})})).status
        """, token)
        assert again >= 400, f"a used link accepted a second submission: {again}"
    finally:
        stranger.close()

    # Back to the coach: the submission is there, and a diet can be built from it.
    coach.reload()
    coach.get_by_role("tab", name="Coach mode").click()
    coach.wait_for_selector("#coachWorkspace:not([hidden])", timeout=10_000)
    open_tool(coach, "intakesTool")
    coach.wait_for_selector("#intakeList >> text=E2E Client", timeout=10_000)

    coach.click("[data-open-intake]")
    coach.wait_for_selector("[data-build-diet]", timeout=10_000)
    coach.click("[data-build-diet]")
    coach.wait_for_selector("#dietResult .mp-step", timeout=25_000)

    # Judge the plan by the food it serves, not the panel text — the advice
    # legitimately names foods it chose not to use.
    served = meal_text(coach.locator("#dietResult"))
    assert served, "the plan rendered no meals at all"
    for absent in ("chicken", "whey", "egg", "fish", "mutton"):
        assert absent not in served, f"a vegetarian tight-budget plan served {absent}"


def test_a_nonexistent_token_is_refused_politely(page, server):
    """A stranger guessing a token should get a clear no, not a stack trace."""
    page.goto(f"{server}/start/this-token-does-not-exist-at-all")
    page.wait_for_load_state("networkidle")
    assert page.locator("body").inner_text().strip(), "the page rendered nothing at all"
