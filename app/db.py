"""
db.py — SQLite persistence for client profiles, measurements and saved reports.

Same approach as my other repos: SQLite ships with Python, so there's no database
server to install, and the whole store is one `toolkit.db` file next to the app.
Every function opens a short-lived connection, commits and closes.

Why that's fine here: this is a single-coach tool with a handful of writes per
session, so connection setup cost is irrelevant and the simplicity is worth more
than a pool. If it ever became multi-user I'd move to a connection pool and
proper migrations — noting that here because it's the honest boundary of the
design, not an oversight.

Three tables:
    clients       one row per person the coach tracks
    measurements  many rows per client, one per weigh-in — this is the time series
    reports       saved assessment snapshots, stored as JSON

`reports` stores the whole response as a JSON blob rather than normalising it
into columns. That's deliberate: the report shape includes long-form explanation
text and will keep evolving as the knowledge base grows, and a snapshot should
stay exactly as it was when the coach handed it to the client — including the
wording of the advice. Normalising it would break that guarantee on every schema
change.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "TOOLKIT_DB",
    os.path.join(os.path.dirname(__file__), "..", "toolkit.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  sex         TEXT NOT NULL,
  age         INTEGER,
  height_cm   REAL,
  diet        TEXT,
  goal        TEXT,
  notes       TEXT,
  created_at  TEXT
);

CREATE TABLE IF NOT EXISTS measurements (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id   INTEGER NOT NULL,
  taken_on    TEXT NOT NULL,
  weight_kg   REAL,
  bodyfat_pct REAL,
  waist_cm    REAL,
  neck_cm     REAL,
  hip_cm      REAL,
  chest_cm    REAL,
  arm_cm      REAL,
  thigh_cm    REAL,
  note        TEXT,
  created_at  TEXT,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id   INTEGER,
  created_at  TEXT,
  goal        TEXT,
  kcal        INTEGER,
  payload     TEXT,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

-- The measurements query is always "everything for one client, in date order",
-- so index exactly that.
CREATE INDEX IF NOT EXISTS idx_measurements_client
  ON measurements(client_id, taken_on);
CREATE INDEX IF NOT EXISTS idx_reports_client
  ON reports(client_id, created_at);
"""

MEASUREMENT_COLS = [
    "taken_on", "weight_kg", "bodyfat_pct", "waist_cm", "neck_cm",
    "hip_cm", "chest_cm", "arm_cm", "thigh_cm", "note",
]

CLIENT_COLS = ["name", "sex", "age", "height_cm", "diet", "goal", "notes"]


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Create the schema if it isn't there.

    Called on every connection, which sounds wasteful but isn't: it's one lookup
    against sqlite_master, and this app serves a handful of requests per session.

    It exists because `init_db()` at startup is not enough. SQLite is a plain
    file, so it can disappear under a running process — deleted during a tidy-up,
    moved, restored from a backup, or TOOLKIT_DB repointed at a fresh path. When
    that happened, `sqlite3.connect()` happily created a new empty file and every
    query then failed with "no such table: clients" as an opaque 500. The endpoint
    looked broken when the real problem was a missing file.

    CREATE TABLE IF NOT EXISTS makes running the script idempotent, so recovery
    costs nothing and needs no restart.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='clients'"
    ).fetchone()
    if not exists:
        conn.executescript(SCHEMA)


@contextmanager
def db():
    """Short-lived connection, schema-checked, committed on clean exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLite has foreign keys off by default, per connection — so ON DELETE
    # CASCADE only works if we turn it on every time.
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """
    Create the schema at startup.

    Now belt-and-braces rather than load-bearing — `db()` self-heals — but it
    still means a fresh install has its tables before the first request, and it
    fails loudly at boot if the DB path isn't writable.
    """
    with db() as c:
        c.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
#  Clients
# ---------------------------------------------------------------------------

def create_client(data: dict) -> dict:
    with db() as c:
        cur = c.execute(
            f"INSERT INTO clients ({', '.join(CLIENT_COLS)}, created_at) "
            f"VALUES ({', '.join('?' * len(CLIENT_COLS))}, ?)",
            [data.get(k) for k in CLIENT_COLS] + [_now()],
        )
        new_id = cur.lastrowid

    # Deliberately OUTSIDE the `with` block. get_client() opens its own
    # connection, and the INSERT above is only committed when the block exits —
    # so calling it inside would query a connection that cannot see the new row
    # yet and would return None.
    return get_client(new_id)


def list_clients() -> list[dict]:
    """All clients, newest first, each with a measurement count for the list UI."""
    with db() as c:
        rows = c.execute("""
            SELECT c.*,
                   (SELECT COUNT(*) FROM measurements m WHERE m.client_id = c.id)
                       AS measurement_count,
                   (SELECT MAX(taken_on) FROM measurements m WHERE m.client_id = c.id)
                       AS last_measured
            FROM clients c
            ORDER BY c.id DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_client(client_id: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return dict(row) if row else None


def update_client(client_id: int, data: dict) -> dict | None:
    if not get_client(client_id):
        return None
    with db() as c:
        c.execute(
            f"UPDATE clients SET {', '.join(f'{k} = ?' for k in CLIENT_COLS)} "
            "WHERE id = ?",
            [data.get(k) for k in CLIENT_COLS] + [client_id],
        )
    return get_client(client_id)


def delete_client(client_id: int) -> bool:
    """Deletes the client and — via ON DELETE CASCADE — their measurements and reports."""
    with db() as c:
        cur = c.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
#  Measurements
# ---------------------------------------------------------------------------

def add_measurement(client_id: int, data: dict) -> dict:
    with db() as c:
        cur = c.execute(
            f"INSERT INTO measurements (client_id, {', '.join(MEASUREMENT_COLS)}, created_at) "
            f"VALUES (?, {', '.join('?' * len(MEASUREMENT_COLS))}, ?)",
            [client_id] + [data.get(k) for k in MEASUREMENT_COLS] + [_now()],
        )
        row = c.execute(
            "SELECT * FROM measurements WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def list_measurements(client_id: int) -> list[dict]:
    """Chronological — the charts plot straight from this order."""
    with db() as c:
        rows = c.execute(
            "SELECT * FROM measurements WHERE client_id = ? ORDER BY taken_on ASC, id ASC",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_measurement(measurement_id: int) -> bool:
    with db() as c:
        cur = c.execute("DELETE FROM measurements WHERE id = ?", (measurement_id,))
        return cur.rowcount > 0


def progress_summary(client_id: int) -> dict | None:
    """
    First vs latest measurement, and the change between them.

    Returned separately from the raw list because it's what a coach actually
    opens the app to see: "is this working?"
    """
    rows = list_measurements(client_id)
    if not rows:
        return None
    first, last = rows[0], rows[-1]

    def delta(key: str):
        a, b = first.get(key), last.get(key)
        return round(b - a, 1) if a is not None and b is not None else None

    # Fat and lean mass change is the interesting part — losing 5 kg means very
    # different things depending on what it was made of.
    fat_change = lean_change = None
    if first.get("bodyfat_pct") and last.get("bodyfat_pct"):
        f_first = first["weight_kg"] * first["bodyfat_pct"] / 100
        f_last = last["weight_kg"] * last["bodyfat_pct"] / 100
        fat_change = round(f_last - f_first, 1)
        lean_change = round(
            (last["weight_kg"] - f_last) - (first["weight_kg"] - f_first), 1
        )

    return {
        "entries": len(rows),
        "first": first,
        "latest": last,
        "weight_change_kg": delta("weight_kg"),
        "bodyfat_change_pct": delta("bodyfat_pct"),
        "waist_change_cm": delta("waist_cm"),
        "fat_mass_change_kg": fat_change,
        "lean_mass_change_kg": lean_change,
    }


# ---------------------------------------------------------------------------
#  Saved reports
# ---------------------------------------------------------------------------

def save_report(client_id: int | None, report: dict) -> dict:
    """Snapshot a full assessment, stored as JSON. See the module docstring for why."""
    with db() as c:
        cur = c.execute(
            "INSERT INTO reports (client_id, created_at, goal, kcal, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                client_id,
                _now(),
                report.get("input", {}).get("goal"),
                report.get("nutrition", {}).get("kcal", {}).get("number"),
                json.dumps(report),
            ),
        )
        return {"id": cur.lastrowid, "created_at": _now()}


def list_reports(client_id: int | None = None) -> list[dict]:
    """Report index — metadata only, no payload, so the list stays light."""
    with db() as c:
        if client_id is None:
            rows = c.execute(
                "SELECT id, client_id, created_at, goal, kcal FROM reports "
                "ORDER BY id DESC LIMIT 100"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, client_id, created_at, goal, kcal FROM reports "
                "WHERE client_id = ? ORDER BY id DESC",
                (client_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_report(report_id: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d["payload"])
        return d


def delete_report(report_id: int) -> bool:
    with db() as c:
        cur = c.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        return cur.rowcount > 0
