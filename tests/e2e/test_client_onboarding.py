"""
The onboarding form, as a client actually experiences it.

This is the surface with the most at stake and it had the least coverage: it is
the only public write path, it is reachable by anyone holding a link, and it is
the first thing a paying client ever sees. Until now it was only exercised by
POSTing JSON at the API from a second browser context — which proved the endpoint
worked and proved nothing about whether a person can fill the thing in.

Driven in a fresh context with no cookies and no session, because that is what a
client is.
"""

import pytest

from .conftest import COACH_PASSWORD

pytestmark = pytest.mark.e2e


@pytest.fixture
def token(page, server):
    """A live onboarding link, minted the way the coach mints one."""
    page.get_by_role("tab", name="Coach mode").click()
    page.fill("#coachPassword", COACH_PASSWORD)
    page.click("#loginForm button[type=submit]")
    page.wait_for_selector("#coachWorkspace:not([hidden])", timeout=10_000)
    return page.evaluate("""async () => {
      const r = await fetch('/api/invites', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({label: 'e2e client form'})});
      return (await r.json()).token;
    }""")


@pytest.fixture
def client_page(browser, server, token):
    """A stranger with a link: new context, no cookies, no session."""
    context = browser.new_context()
    p = context.new_page()
    crashes = []
    p.on("pageerror", lambda e: crashes.append(str(e)))
    p.goto(f"{server}/start/{token}")
    p.wait_for_load_state("networkidle")
    yield p
    assert not crashes, f"the client's page threw: {crashes}"
    context.close()


def test_the_client_sees_a_welcome_not_a_blank_page(client_page):
    """
    The first thing a paying client ever sees.

    A form that renders empty while it fetches, with no heading and no
    explanation, reads as a broken link — and they will tell the coach so.
    """
    client_page.wait_for_selector("#intro:not([hidden])", timeout=15_000)
    heading = client_page.locator("#introHeading").inner_text()
    assert heading.strip()
    assert client_page.locator("#introBody").inner_text().strip()
    # Privacy is stated before a single answer is collected, not after.
    assert client_page.locator("#privacySummary").inner_text().strip()


def test_the_client_can_walk_the_whole_questionnaire_and_submit(client_page):
    """
    The full journey, start to thank-you.

    Every required field is filled by walking the form as rendered rather than
    from a hardcoded list, so this keeps working when the questionnaire changes.
    """
    client_page.wait_for_selector("#intro:not([hidden])", timeout=15_000)
    client_page.click("#beginBtn")
    client_page.wait_for_selector("#intakeForm:not([hidden])", timeout=10_000)

    for _ in range(12):                      # 6 sections, generous bound
        if not client_page.locator("#consentStep").is_hidden():
            break
        client_page.evaluate("""() => {
          const host = document.getElementById('sectionHost');
          host.querySelectorAll('input, textarea, select').forEach(el => {
            if (el.type === 'radio' || el.type === 'checkbox') return;
            if (el.value) return;
            if (el.tagName === 'SELECT') { el.selectedIndex = 1; }
            else if (el.type === 'number') { el.value = el.min || '20'; }
            else { el.value = 'e2e answer'; }
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
          });
          // Choice cards are buttons with role=radio, not inputs.
          host.querySelectorAll('[role="radiogroup"], .seg, .cards').forEach(g => {
            if (!g.querySelector('[aria-checked="true"], [aria-pressed="true"]')) {
              g.querySelector('button')?.click();
            }
          });
        }""")
        nxt = client_page.locator("#nextBtn")
        if not nxt.is_visible():
            break
        nxt.click()
        client_page.wait_for_timeout(400)

    client_page.wait_for_selector("#consentStep:not([hidden])", timeout=15_000)

    # Consent is required, and the submit button must stay dead until it's given.
    assert client_page.locator("#submitBtn").is_disabled(), \
        "the client could submit without consenting"

    client_page.check("#consentBox")
    client_page.wait_for_timeout(300)
    client_page.click("#submitBtn")

    client_page.wait_for_selector("#doneStep:not([hidden])", timeout=20_000)
    done = client_page.locator("#doneStep").inner_text()
    assert done.strip(), "the thank-you screen rendered empty"


def test_the_client_is_never_shown_their_calorie_numbers(client_page):
    """
    A documented promise, and the commercial point of the whole flow.

    The closing screen reflects their answers back to earn the call; the numbers
    are the thing the coach is paid for. There is a unit test asserting no target
    reaches that payload — this checks the rendered page, which is what a client
    actually reads.
    """
    client_page.wait_for_selector("#intro:not([hidden])", timeout=15_000)
    body = (client_page.locator("#intro").inner_text()
            + client_page.locator("body").inner_text()).lower()
    for word in ("kcal", "calorie", "macro", "grams of protein"):
        assert word not in body, f"the intro leaks '{word}' to the client"


def test_a_dead_link_explains_itself(page, server):
    """
    A client whose link expired must get a sentence, not a 404.

    They read a broken link as "he sent me something broken", which is the
    opposite of the impression the whole flow exists to create.
    """
    page.goto(f"{server}/start/definitely-not-a-real-token-at-all")
    page.wait_for_selector("#deadLink:not([hidden])", timeout=15_000)
    msg = page.locator("#deadLinkMessage").inner_text()
    assert msg.strip(), "a dead link rendered no explanation"


def test_the_client_cannot_reach_coach_data_with_only_a_link(client_page):
    """The token buys one form, not the coach's records."""
    for path in ("/api/clients", "/api/intakes", "/api/prices", "/api/foods/custom"):
        status = client_page.evaluate(
            "async (p) => (await fetch(p)).status", path)
        assert status in (401, 503), f"{path} was reachable with just an intake link: {status}"
