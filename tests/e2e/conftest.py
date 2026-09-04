"""
conftest.py — a real browser, driving a real server.

These tests are deliberately NOT part of `pytest -q`. The 299 unit and API tests
need nothing but Python and a temp file, and that property is worth protecting:
anyone can clone this repo and run the suite in one command. These ones need a
Chromium binary and a live server, so they are opt-in:

    pytest -m e2e                 # just these
    pytest -m e2e --headed        # watch them happen

What they cover that the API tests cannot: that the buttons are wired to the
right handlers, that what the server returns actually renders, and that the three
front doors stay separate in a browser holding cookies. An API test can prove
/api/clients returns 401; only a browser can prove the Coach tab doesn't show a
client list to someone who never logged in.

The server runs on a free port with its own temp database, so a run can never
touch real data and two runs can't collide.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest

COACH_PASSWORD = "e2e-coach-password-7f3b91"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server() -> str:
    """Boot the app on its own port with its own database. Returns the base URL."""
    port = _free_port()
    db_path = os.path.join(tempfile.mkdtemp(prefix="e2e-toolkit-"), "toolkit.db")

    env = {
        **os.environ,
        "COACH_PASSWORD": COACH_PASSWORD,
        "TOOLKIT_DB": db_path,
        # Force SQLite even if the developer has a real DATABASE_URL exported —
        # otherwise running these locally would write test clients into the
        # production database, which is the kind of mistake you only make once.
        "DATABASE_URL": "",
    }

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server died on startup:\n{proc.stdout.read()}")
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=1) as r:
                if r.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    else:
        proc.terminate()
        raise RuntimeError("server did not become healthy within 30s")

    yield base

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# Requests this app makes on purpose and handles gracefully. A 401 from
# /api/clients before login is the auth boundary WORKING — the browser still logs
# it to the console, so without this filter every auth test would fail in
# teardown for doing exactly what it set out to prove.
_EXPECTED_CONSOLE = re.compile(
    r"Failed to load resource.*status of (401|403|404|409|422|503)", re.I
)


@pytest.fixture
def page(server, page):
    """The stock Playwright page, pointed at our server and failing loudly on JS errors."""
    crashes: list[str] = []
    console: list[str] = []
    # An uncaught JS exception is never expected — that is the class of bug these
    # tests exist to catch, and it is kept strict.
    page.on("pageerror", lambda e: crashes.append(str(e)))
    page.on(
        "console",
        lambda m: console.append(m.text)
        if m.type == "error" and not _EXPECTED_CONSOLE.search(m.text)
        else None,
    )
    page.goto(server)
    yield page
    assert not crashes, f"uncaught JavaScript exception: {crashes}"
    assert not console, f"unexpected console errors: {console}"


def open_tool(page, tool_id: str) -> None:
    """
    Make sure a <details> tool panel is open.

    Clicking the summary TOGGLES it, and two of these panels start open — so a
    click closes them and every selector inside then times out on an invisible
    element. Setting the property is idempotent, which is what a test wants.
    """
    page.evaluate(f"document.getElementById('{tool_id}').open = true")


@pytest.fixture
def coach(page):
    """A page that has logged into Coach mode through the real form."""
    page.get_by_role("tab", name="Coach mode").click()
    page.fill("#coachPassword", COACH_PASSWORD)
    page.click("#loginForm button[type=submit]")
    page.wait_for_selector("#coachWorkspace:not([hidden])", timeout=10_000)
    return page


def meal_text(box) -> str:
    """
    Only the food actually being served, lowercased.

    The diet panel also carries advice, and that advice names foods that are NOT
    in the plan: a short protein target suggests allowing whey, and the exclusion
    line lists what was left out. So searching the whole panel for "whey" finds
    the sentence recommending it and reports the plan as broken. Judge the plan
    by the meal tables.
    """
    return " ".join(
        box.locator(".mp-meal").nth(i).inner_text()
        for i in range(box.locator(".mp-meal").count())
    ).lower()


def open_all_tools(page, panel_id: str) -> None:
    """
    Open every collapsed <details> inside a panel.

    Both the Extra tools and Learn tabs put each tool behind a fold, and most of
    them have no id — so there is nothing to target individually. Everything
    inside a closed <details> is invisible to Playwright, which then times out on
    an element that is present and perfectly correct; the failure reads like a
    broken feature rather than a closed drawer.
    """
    page.evaluate(
        f"document.querySelectorAll('#{panel_id} details')"
        ".forEach(d => {{ d.open = true; }})".replace("{{", "{").replace("}}", "}")
    )
