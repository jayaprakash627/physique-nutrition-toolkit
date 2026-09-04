# Understanding this project, from zero

A guide to your own codebase, written to be read in order. It assumes you can
recognise a variable, a loop and a function, and assumes nothing at all about web
applications, databases, or deployment.

Each stage ends with something you *do*, not something you've read. That's
deliberate: reading 18,000 lines teaches almost nothing, while changing three
lines and watching the screen react teaches you the whole path those lines sit
on.

**Contents**

- [Stage 0 — the words](#stage-0--the-words)

*(Later stages get added as we go. This file is the record, so you never have to
re-ask something already explained.)*

---

# Stage 0 — the words

Every word below describes something that has *already happened* on your machine.
None of it is abstract.

## The one-sentence version of what you own

> A program that does nutrition maths, wrapped in a web page, with a locked
> section where one coach keeps client records — running both on your Mac and on
> a computer in Singapore.

Everything else is detail.

---

## Cluster A — the two halves

Your project is two programs that talk to each other.

**Backend** — the `app/` folder. Python. It does the thinking: the maths, the
safety rules, reading and writing records. It has no idea what anything *looks*
like.

**Frontend** — the `static/` folder. HTML, CSS and JavaScript. It's what you see.
It does no nutrition maths at all; it asks the backend and displays the answer.

They are genuinely separate. You could delete the entire frontend and the backend
would still work perfectly — you'd just have to talk to it with commands instead
of buttons. That's exactly what I was doing every time you saw me run a `curl`
command in our conversation.

**Server** — a program that starts up and then *waits*. It doesn't do anything
until someone asks it something. Your backend is a server. The thing that starts
it is called **uvicorn** — that's the word you saw in `./run.sh`:

```
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Read that as: *"uvicorn, please run the thing called `app` that lives in
`app/main.py`, and listen on door number 8000."*

**Client** — whoever asks. Your browser is a client. `curl` is a client. Your
phone would be a client.

**Request** and **response** — one question, one answer. That's the entire
protocol. The client asks, the server answers, and then the server goes back to
waiting. It doesn't remember you between requests — which is exactly why sessions
had to be invented (Cluster C).

**localhost** and **127.0.0.1** — both mean *"this same computer."* Not a place on
the internet. This is why `http://127.0.0.1:8000` works on your Mac and does
absolutely nothing on your phone: you're telling the phone to look inside itself,
and there's no server in there.

**Port** — the `:8000` part. One computer can run many servers at once, so each
picks a numbered door. Your toolkit used 8000 and 8004 at different times; your
portfolio used 5500. When you saw *"Port 8004 is in use"*, that was two programs
reaching for the same door.

---

## Cluster B — how they talk

**HTTP** — the language of request-and-response. You already know its vocabulary
from watching me work.

**Endpoint** (or **route**) — one specific thing the backend can be asked. Yours
has about 40. They all start with `/api/`:

| Endpoint | What it does |
|---|---|
| `/api/assess` | do the full nutrition calculation |
| `/api/clients` | list saved clients |
| `/api/meal-plan` | build a diet |
| `/api/health` | are you alive? |

**API** — the whole set of them together. "The API" just means "all the things the
backend can be asked to do."

**GET** and **POST** — two kinds of request. GET means *give me something*
(`/api/clients` — list the clients). POST means *here's some data, do something
with it* (`/api/assess` — here's a weight and a height, calculate). There are
others; those two cover almost everything you'll touch.

**JSON** — the format data travels in. It looks like this, and you've seen it many
times in our conversation:

```json
{"status": "ok", "foods_loaded": 45, "coach_mode_locked": true}
```

Curly braces, `"name": value` pairs, commas between. That's the whole idea.

**Status code** — a three-digit number on every response saying how it went. You
have watched me read these all conversation:

| Code | Means | Where you saw it |
|---|---|---|
| **200** | fine | every working request |
| **201** | created something | adding a client |
| **401** | you're not logged in | `/api/clients` before login |
| **404** | no such thing | a route that doesn't exist |
| **422** | your input was invalid | the mistyped food we rejected |
| **500** | the server crashed | the CSV bug with Devanagari names |
| **503** | the server is up but can't do this | database unreachable |

That table is most of debugging. A 500 means *I* wrote a bug. A 422 means the
*user* sent something wrong. Telling those two apart quickly is a real skill.

---

## Cluster C — where things are kept

**Database** — a program (or a file) built for storing information so it survives
the server stopping. Yours holds eight **tables**. A table is a grid, like one
spreadsheet tab. A **row** is one entry.

Here is your actual `clients` table, from when I added a test client:

```
id  name         sex   age  height_cm  goal  created_at
1   Arjun Kumar  male  29   176.0      cut   2026-09-03T18:29:59+00:00
```

That's it. That's a database. The other tables are `measurements` (one row per
weigh-in), `reports`, `invites`, `intakes`, `sessions`, `prices`, `custom_foods`.

**SQL** — the language for asking a database questions. It reads almost like
English, and this is a real line from your `app/db.py`:

```sql
SELECT * FROM clients WHERE id = ?
```

*"Give me everything from the clients table where the id matches this."* The `?`
is a blank the code fills in safely.

**SQLite** — a database that is just **a single file** on disk (`toolkit.db`). No
separate program to run. Brilliant for developing.

**PostgreSQL** (Postgres) — a database that is a **proper separate server**. More
work to set up, but it survives things a file doesn't. **Neon** is a company that
runs one for you for free. This is the switch still pending.

**Session** — remember that the server forgets you between requests? So when you
log into Coach mode, the server writes down a long random string, gives your
browser a copy in a **cookie**, and your browser hands it back on every later
request. That's all "being logged in" is: both sides holding the same secret
string. Yours are kept in the `sessions` table.

**Environment variable** — a setting handed to a program when it starts, from
*outside* the code. Yours has two that matter:

- `COACH_PASSWORD` — the Coach mode password
- `DATABASE_URL` — which database to use (unset = the SQLite file)

They live outside the code for one reason: **secrets must never be in the code**,
because code goes to GitHub where anyone can read it. That's why your `.env` file
is in `.gitignore`.

---

## Cluster D — your Mac versus the world

**Deployment** — the act of putting your program on a computer that isn't yours,
so other people can use it. That's all. Not a technology, an *action*.

**Production** — the real, live copy that real people use. As opposed to
**development** or **local**, which is the copy on your Mac where breaking things
is free. You have both:

| | Local | Production |
|---|---|---|
| Address | `http://127.0.0.1:8000` | `physique-nutrition-toolkit.onrender.com` |
| Who can reach it | only you | anyone on earth |
| Who starts it | you, with `./run.sh` | nobody — it's always running |
| If you break it | nothing happens | your clients see it |

**Hosting** — renting a computer that stays on. **Render** is your host. It watches
your GitHub repository, and when new code arrives it fetches it and restarts your
server automatically. That's what "auto-deploy" means, and it's why you kept
seeing me push and then wait.

**Redeploy** — Render throwing away the running copy and starting a fresh one from
the newest code. Important consequence: **anything written to the old copy's disk
is gone.** That is the single reason the Neon switch matters.

**Ephemeral** — "doesn't last." Render's free disk is ephemeral. A SQLite file
there is deleted on every redeploy. Ten clients' records would vanish with no
error message. Hence Postgres.

**Git**, **commit**, **push** — Git records the history of your code. A **commit**
is one saved point with a message explaining why. A **push** sends commits to
GitHub. You watched this maybe fifteen times; each `git commit` you saw was one
entry in that history.

**Test suite** — automated checks that tell you whether you've broken anything.
You have two sets, and the split is deliberate:

- **349 fast checks** — pure logic, no browser needed. They run in **one second**,
  so you can run them after every single change.
- **39 browser checks** — these actually open a real Chrome, click your buttons
  and read the screen. They take about a minute, so they're opt-in
  (`pytest -m e2e`).

388 in total. This is the most useful thing you own, and Stage 3
is about making it yours. It means you can change almost any line in this project
and know within one second whether you've broken something.

---

## Do this now (about ten minutes)

Open a terminal. Then:

**1. Start it.**

```bash
cd ~/Documents/physique-nutrition-toolkit && ./run.sh
```

You've just started a server. Leave it running; open a *second* terminal window
for the rest.

**2. Ask it a question as a client, with no browser involved.**

```bash
curl http://127.0.0.1:8000/api/health
```

You sent a GET request to an endpoint and got JSON back. That is the entire
frontend/backend relationship, with the frontend removed.

**3. See the status code by itself.**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/clients
```

You should get **401** — not logged in. You just tested your own auth boundary.

**4. Do a real calculation with a POST.**

```bash
curl -s -X POST http://127.0.0.1:8000/api/assess \
  -H 'Content-Type: application/json' \
  -d '{"sex":"male","age":28,"weight_kg":75,"height_cm":178,"goal":"cut"}'
```

You sent data and got a full nutrition report back. No browser, no buttons — this
is your backend, naked.

**5. Look inside the database.**

```bash
sqlite3 ~/Documents/physique-nutrition-toolkit/toolkit.db ".tables"
```

Eight table names. That's your storage.

**6. Run the tests.**

```bash
cd ~/Documents/physique-nutrition-toolkit && .venv/bin/python -m pytest -q
```

You should see `349 passed` in about a second. (The other 39 are the browser
ones, deliberately skipped here — that's what `39 deselected` means.)

Stop the server with **Control-C** when you're done.

---

## Check yourself

You're ready for Stage 1 if you can answer these without scrolling up:

1. Why does `127.0.0.1:8000` not work on your phone?
2. Something returns **401**. Whose mistake is it — yours or the user's? What about **500**?
3. What's the difference between GET and POST?
4. Why is `COACH_PASSWORD` not written in the code?
5. Why would ten clients' records disappear from the live site today?
6. What does Render actually *do* when you push to GitHub?

If any of those are shaky, say which — that's not a failure, it's the useful
signal for what to go over again.
