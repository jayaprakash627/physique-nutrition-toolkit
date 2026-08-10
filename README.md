# 🏋️ Physique & Nutrition Coaching Toolkit

**A nutrition coach that explains itself.** Every number this tool produces comes
with the physiology behind it, what goes wrong at too little or too much, real
food portions to hit it, and the published standard it came from.

> Most trainers say *"eat 180 g of protein"* and stop there. So the client
> doesn't understand it, doesn't trust it, and doesn't stick to it. I've competed
> in powerlifting and bodybuilding — people don't fail because the numbers were
> wrong. They fail because nobody explained them.
>
> — Built by **Jayaprakash M** ([portfolio](https://jayaprakash627.github.io) · [GitHub](https://github.com/jayaprakash627))

---

## ⚠️ Read this first

This toolkit produces **population-level estimates for education and coaching
support**. It is **not medical advice, diagnosis or treatment.** Every formula
here carries real error bars, and no equation can see your health history,
medication, bloodwork or training context.

It actively **refuses to plan** for cases where a calculator is the wrong tool:
under-18s, pregnancy, body-fat targets below the healthy minimum (with different
floors for men and women), calorie targets below a safe floor, and timelines that
would cost muscle. It flags them, explains the physiology, and points to a
professional.

---

## 🚪 Start simple, go as deep as you want

The first version of this tool put a 20-field form on the front page — including
neck circumference and seven calliper sites — before showing a single number. I
gave it to friends who train. They didn't use it. It was built for a coach who
already owns callipers, not for the person who just wants to know what to eat.

So the front door is now **five questions**, all things you already know: sex,
age, weight, height, goal, activity, diet. No tape measure, no signup. You get:

1. **One number** — the calories, big and unmissable
2. **One sentence** — what that does and how fast
3. **One priority** — "if you only track one thing, track this" (it's protein)
4. **Three actions** — concrete things to do this week

Everything else is still there, just demoted: each macro keeps its
**"Why this number?"** panel, and one *"Show me everything"* fold opens the full
coach's report — body-fat method comparison, how the calories were derived, body
composition, the micronutrient panel. A **Simple / Full detail** switch in the
header remembers which you prefer.

If you skip the measurements, the plan says so and offers a 30-second tape
measurement to sharpen it — rather than silently handing you the least accurate
estimate as though it were fact.

## ✨ What makes it different

Everything below is built around one rule: **no number ships without its
reasoning.**

| Most calculators | This toolkit |
|---|---|
| "Protein: 165 g" | 165 g, from **lean mass** — plus muscle protein synthesis, why protein rises in a deficit, satiety, the thermic effect, what happens below 0.8 g/kg, and 6 Indian foods that get you there |
| Ignores fat's floor | Warns when fat drops under ~0.5 g/kg or 20% of calories, explains hormone production, vitamin A/D/E/K absorption, and **raises fat back to the floor automatically** |
| Skips micronutrients | A 15-nutrient panel, **risk-ordered for the individual** — vegetarians flagged for B12/iron/omega-3, deep cuts for micronutrient gaps, heavy sweaters for electrolytes |
| One body-fat number | Four methods side by side, **the spread between them**, and which to trust |
| No sources | 33 cited standards — ISSN, ACSM, WHO, ICMR-NIN, IOM, EFSA, NIH ODS, IOC |

Indian-first throughout: **ICMR-NIN 2020 RDAs** alongside Western references
(they differ substantially for iron and zinc, and the tool explains *why*), food
portions in katoris and rotis, and hydration that accounts for Indian heat.

---

## 🧮 What it calculates

**Energy** — BMR via Mifflin–St Jeor *and* Katch–McArdle side by side (with an
explanation of why the lean-mass equation suits lifters), TDEE, and cut /
aggressive cut / maintain / lean-bulk targets at evidence-backed rates.

**Macros** — protein from lean body mass, fat with a protected floor, carbs
taking the remainder. Grams, calories and % for each, plus a meal-by-meal
breakdown that reconciles to the daily total exactly.

**Fibre & water** — fibre scaled to intake (14 g/1000 kcal, WHO floor honoured);
water built from bodyweight + training hours + climate + a high-protein
allowance.

**Micronutrients** — Vitamin D, B12, Iron, Calcium, Magnesium, Zinc, Potassium,
Sodium, Iodine, Omega-3, and vitamins A/C/E/K + folate. Each with function, why
athletes fall short, deficiency signs, upper limits, and diet-filtered food
sources.

**Body fat** — US Navy tape, Jackson–Pollock 3-site and 7-site, Deurenberg, with
the disagreement between them made explicit.

**Physique metrics** — lean/fat mass, FFMI (raw and height-normalised, with
honest natural-limit context), waist-to-height ratio, and target weight at a goal
body fat.

**Goal & contest prep planner** — "I'm X% now, want Y% by date Z" → required
weekly rate, week-by-week projection, and a blunt verdict when the timeline isn't
safe.

**Strength tools** — 1RM via Epley and Brzycki, a % of 1RM loading table rounded
to real plates, and DOTS / Wilks scoring.

**Track & export** — client profiles, measurements over time, progress charts
(including the **fat-mass vs lean-mass split**, which is what actually tells you
if a cut is working), and a printable summary that includes the explanations.

---

## ▶️ Run it

Needs **Python 3.10+**. No build step, no Node, no database server.

```bash
git clone https://github.com/jayaprakash627/physique-nutrition-toolkit.git
cd physique-nutrition-toolkit
```

```bash
python3 -m venv .venv && source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000**. Interactive API docs at `/docs`.

### Tests

```bash
pip install -r requirements-dev.txt && pytest -q
```

162 tests covering every formula against its published value, the safety
guardrails, knowledge-base integrity (every citation resolves, every nutrient is
complete), the plain-language summary for every goal — including a check that no
internal enum like `aggressive_cut` ever leaks into text a person reads — and the
API contract.

---

## 🧱 Tech stack

| Part | Choice | Why |
|---|---|---|
| Backend | Python · FastAPI | Type-validated request models, automatic OpenAPI docs |
| Storage | SQLite | One file, zero setup — matches the scale of a single-coach tool |
| Validation | Pydantic | Physiological bounds on every field; catches height-in-metres |
| Frontend | Plain HTML/CSS/JS | No framework, no build step — clone and run |
| Charts | Hand-rolled Canvas | ~250 lines, DPR-aware, theme-reactive; no chart library |
| Tests | pytest | 150 tests, no network, no fixtures beyond a temp DB |

### Layout

```
app/
├── main.py         FastAPI routes — thin, no logic
├── engine.py       assembles reports: binds every number to its explanation,
│                   plus plain_summary() — the beginner's one-sentence answer
├── formulas.py     pure maths, one function per published equation
├── safety.py       the guardrails — flags, blocks, and why
├── models.py       Pydantic schemas with physiological bounds
├── db.py           SQLite: clients, measurements, saved reports
└── knowledge/      ← the nutrition content, deliberately separated
    ├── sources.py         33 cited standards, one entry each
    ├── explanations.py    the "Why this number?" text per macro
    ├── micronutrients.py  the vitamin & mineral panel + risk profiling
    └── foods.py           Indian food portions (IFCT 2017)
static/
├── index.html
├── css/  theme.css (tokens, light + dark) · app.css
└── js/   api.js · charts.js · render.js · app.js
tests/   150 tests
```

**Why `knowledge/` is its own package:** the nutrition content is the product,
and it needs to be verifiable by someone who knows nutrition but not Python. It
has zero dependencies on the app — the arrows point one way — so a dietitian can
review those four files in isolation and correct a number without touching
application logic.

---

## 📐 Formulas & standards

Every equation below is implemented in [`app/formulas.py`](app/formulas.py) with
its source key in the docstring, and every source key resolves to a full citation
in [`app/knowledge/sources.py`](app/knowledge/sources.py).

### Basal metabolic rate

**Mifflin–St Jeor (1990)** — the most accurate general-population equation, but
it uses total bodyweight so it cannot see body composition.

```
Men:   BMR = 10·kg + 6.25·cm − 5·age + 5
Women: BMR = 10·kg + 6.25·cm − 5·age − 161
```

**Katch–McArdle** — predicts from lean mass alone. No sex term, because lean mass
already carries most of the between-sex difference. **Preferred here for
lifters**, whose lean mass sits well above what bodyweight-only equations assume.

```
BMR = 370 + 21.6 × LBM(kg)
```

The trade-off is stated in the UI: Katch–McArdle is only as good as the body-fat
estimate feeding it.

**TDEE** = BMR × activity factor (1.20 sedentary → 1.90 very active).
*Source: [Mifflin & St Jeor](https://academic.oup.com/ajcn/article-abstract/51/2/241/4695104),
[Katch–McArdle](https://pubmed.ncbi.nlm.nih.gov/7361681/),
[ACSM 2016](https://journals.lww.com/acsm-msse/fulltext/2016/03000/nutrition_and_athletic_performance.25.aspx)*

### Body fat

**U.S. Navy circumference** (Hodgdon & Beckett, 1984), girths in cm:

```
Men:   %BF = 495 / (1.0324 − 0.19077·log₁₀(waist − neck) + 0.15456·log₁₀(height)) − 450
Women: %BF = 495 / (1.29579 − 0.35004·log₁₀(waist + hip − neck) + 0.22100·log₁₀(height)) − 450
```

**Jackson–Pollock 3-site** — note the sites differ by sex:

```
Men (chest, abdomen, thigh):         Db = 1.10938 − 0.0008267·S + 0.0000016·S² − 0.0002574·age
Women (triceps, suprailiac, thigh):  Db = 1.099421 − 0.0009929·S + 0.0000023·S² − 0.0001392·age
```

**Jackson–Pollock 7-site** (chest, midaxillary, triceps, subscapular, abdomen,
suprailiac, thigh):

```
Men:   Db = 1.112 − 0.00043499·S + 0.00000055·S² − 0.00028826·age
Women: Db = 1.097 − 0.00046971·S + 0.00000056·S² − 0.00012828·age
```

**Siri (1961)** converts density to percentage: `%BF = 495/Db − 450`

**Deurenberg (1991)** — included as a *contrast*, not a recommendation, because
BMI cannot distinguish muscle from fat and systematically over-reads lifters:

```
%BF = 1.20·BMI + 0.23·age − 10.8·(1 if male else 0) − 5.4
```

*Sources: [Navy](https://apps.dtic.mil/sti/citations/ADA143890),
[J&P men 1978](https://pubmed.ncbi.nlm.nih.gov/718832/),
[J&P&W women 1980](https://pubmed.ncbi.nlm.nih.gov/7402053/),
[Siri](https://pubmed.ncbi.nlm.nih.gov/8286893/),
[Deurenberg](https://pubmed.ncbi.nlm.nih.gov/2043597/)*

### Physique metrics

```
BMI          = kg / m²
Lean mass    = weight × (1 − %BF/100)
FFMI         = LBM(kg) / height(m)²
FFMI (norm.) = FFMI + 6.1 × (1.8 − height in m)
Target weight at goal %BF = LBM / (1 − goal%/100)
Waist-to-height = waist / height     (keep under 0.5)
```

FFMI context: ~18–19 untrained, ~20–21 athletic, ~22–23 well-trained, ~25 is
where [Kouri et al. (1995)](https://pubmed.ncbi.nlm.nih.gov/7496846/) found very
few drug-free lifters above — **a population observation, not a biological law.**

### Macronutrients — and why the order matters

The sequencing *is* the method:

1. **Protein from lean body mass**, not total weight. Fat tissue doesn't need
   feeding; muscle does. Two people at 80 kg with different body composition get
   genuinely different targets.
   - Cut **2.4 g/kg LBM** · Maintain **2.1** · Bulk **2.0**
   - Highest while cutting, because that's when muscle is most at risk. A tool
     that *lowers* protein in a deficit has the logic backwards.
   - Cross-checked against the ISSN's 1.6–2.2 g/kg **bodyweight** range, and the
     UI says when you fall outside it and why.
2. **Fat second, with a protected floor.** Fat is the macro with a hard
   biological minimum, so it's claimed before carbs rather than getting leftovers.
   - Target 25–28% of calories; **floor = max(0.5 g/kg bodyweight, 20% of
     calories)**. If the plan wants less, fat is raised to the floor and the
     difference comes out of carbs — with a flag explaining it.
3. **Carbs take the remainder.** Not because they matter least, but because they
   have the widest safe range, which makes them the right lever to absorb the
   adjustment.

```
Protein: 4 kcal/g   Carbs: 4 kcal/g   Fat: 9 kcal/g
Body fat energy: ~7700 kcal per kg
```

**Rates.** Cut = 20% deficit (aggressive = 25%, always flagged). Lean bulk = 10%
surplus. Safe loss = **0.5–1.0% of bodyweight per week**; muscle gain caps around
0.25–0.5%/week.

*Sources: [ISSN protein 2017](https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0177-8),
[ISSN diets 2017](https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0174-y),
[Helms et al. 2014](https://jissn.biomedcentral.com/articles/10.1186/1550-2783-11-20),
[IOM DRI](https://nap.nationalacademies.org/catalog/10490),
[WHO fats 2023](https://www.who.int/publications/i/item/9789240073654)*

### Fibre & water

```
Fibre = 14 g per 1000 kcal, clamped to 25–45 g/day
Water = 35 ml/kg  +  600 ml per training hour  +  climate (0–900 ml)
        +  250 ml when protein exceeds 2 g/kg
```

Fibre's floor is the WHO 25 g/day figure; the cap reflects gut tolerance rather
than any upper safety limit. Water is *total* fluid — food contributes roughly
25%, which the UI states so nobody tries to drink 5 L of plain water.

*Sources: [IOM DRI](https://nap.nationalacademies.org/catalog/10490),
[WHO carbohydrate 2023](https://www.who.int/publications/i/item/9789240073593),
[EFSA water 2010](https://www.efsa.europa.eu/en/efsajournal/pub/1459),
[ACSM hydration 2007](https://pubmed.ncbi.nlm.nih.gov/17277604/)*

### Micronutrients

Two reference sets per nutrient, shown side by side on purpose:

- **[ICMR-NIN 2020](https://www.nin.res.in/RDA_short_Report_2020.html)** — the
  Indian RDA. Several values are **higher** than Western ones: iron is 19 mg
  (men) / 29 mg (women) vs the US 8/18, and zinc 17/13 vs 11/8. That's not an
  error — phytates in a cereal-and-pulse diet block absorption, so more must be
  eaten to absorb the same amount.
- **IOM / WHO / EFSA / NIH ODS** — the Western reference.

Food values are rounded from the
**[Indian Food Composition Tables (IFCT 2017)](https://www.nin.res.in/ebooks/IFCT2017.pdf)**
and USDA FoodData Central.

Risk profiling is rule-based and readable, so a coach can see exactly why a flag
appeared: vegetarian/vegan → B12, iron, omega-3, calcium; deficit ≥22% → deep-cut
micronutrient gaps; hot climate or ≥1.5 h training → electrolytes; carbs
<2 g/kg → potassium and sodium; fat <0.7 g/kg → fat-soluble vitamins.

### Strength

```
Epley:   1RM = w × (1 + reps/30)
Brzycki: 1RM = w × 36 / (37 − reps)
DOTS / Wilks: score = total × 500 / (a + b·bw + c·bw² + d·bw³ + e·bw⁴ [+ f·bw⁵])
```

The two 1RM equations are **identical at exactly 10 reps** and then swap which
reads higher — Epley above at low reps, Brzycki above beyond 10 — so the pair
brackets the true value from either side.

*Sources: [Epley](https://en.wikipedia.org/wiki/One-repetition_maximum),
[Brzycki](https://www.tandfonline.com/doi/abs/10.1080/07303084.1993.10606684),
[DOTS/Wilks](https://en.wikipedia.org/wiki/Wilks_coefficient)*

### Safety thresholds

| Guardrail | Threshold | Action |
|---|---|---|
| Under 18 | age < 18 | **Blocked** — growth and bone density |
| Pregnancy / breastfeeding | flagged | **Blocked** — needs clinical guidance |
| Below essential body fat | <3% men, <10% women | **Blocked** |
| Healthy body-fat floor | <8% men, <16% women | Warning |
| Calorie floor | <1500 men, <1200 women | **Blocked** |
| Eating below BMR | target < 0.95 × BMR | Warning |
| Deficit depth | ≥24% below maintenance | Warning |
| Loss rate | >1.0% bodyweight/week | Warning |
| Fat below floor | <0.5 g/kg or <20% kcal | Raised to floor + explained |
| Carbs impossible | protein + fat > total kcal | **Blocked** |
| Prep rate | >1.5% bodyweight/week | **Blocked** |

Blocked means: **the numbers are still shown** — hiding them just sends someone
to a worse tool with no warning attached — but they're visually withdrawn and
clearly marked as not recommended, with the flags leading.

*Sources: [IOC RED-S consensus 2018](https://bjsm.bmj.com/content/52/11/687),
[ACE/ACSM ranges](https://www.acefitness.org/resources/everyone/tools-calculators/percent-body-fat-calculator/),
[Helms et al. 2014](https://jissn.biomedcentral.com/articles/10.1186/1550-2783-11-20)*

---

## 🔌 API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/meta` | Every option list, help text and disclaimer |
| `GET` | `/api/sources` | The full citation registry |
| `GET` | `/api/micronutrients?sex=` | Reference panel, no client needed |
| `POST` | `/api/assess` | **The full assessment** |
| `POST` | `/api/bodyfat` | Method comparison only |
| `POST` | `/api/prep-plan` | Goal / contest projection |
| `POST` | `/api/strength` | 1RM, % table, DOTS/Wilks |
| `GET/POST` | `/api/clients` | List / create clients |
| `GET/PUT/DELETE` | `/api/clients/{id}` | Client detail, update, delete (cascades) |
| `POST` | `/api/clients/{id}/measurements` | Log a measurement |
| `GET/POST` | `/api/reports` | Saved assessment snapshots |
| `GET` | `/api/health` | Liveness + content counts |

```bash
curl -s localhost:8000/api/assess -H 'Content-Type: application/json' -d '{
  "sex":"male","age":24,"weight_kg":78,"height_cm":175,"goal":"cut",
  "activity":"moderate","diet":"omnivore","climate":"hot","training_hours":1.5,
  "girths":{"neck":39,"waist":82}
}' | python3 -m json.tool | head -40
```

---

## 🎨 Design notes

Dark-first, matching my portfolio: `#0A0E14` background with teal `#5EEAD4`, blue
`#6EA8FE` and violet `#A78BFA` accents; Space Grotesk, Inter and JetBrains Mono.
Full light theme with **re-derived accent colours** — the dark-theme values fail
contrast on white, so they're darkened rather than reused.

**Progressive disclosure at three levels**, which is what the redesign fixed. The
*journey*: five questions, then the answer, then optional depth. The *page*: one
number leads, the coach's report hides behind a fold. The *component*: every
explanation sits behind a "Why this number?" disclosure. The original only had the
third one, which is why it still felt like a wall.

Goal and activity use **large tappable cards instead of dropdowns** — seeing all
the options at once matters for the two choices that actually change the plan, and
46px targets work on a phone. Charts are hand-rolled Canvas: device-pixel-ratio
aware so they're sharp on Retina, and they re-read the CSS custom properties on
theme toggle so they recolour in place.

The print stylesheet **force-opens every collapsed panel**, so a printed client
summary carries the reasoning rather than a page of bare numbers. That's the whole
point of the tool.

---

## 🚧 Scope & honesty

- **Estimates, not measurements.** BMR equations carry ~±10% error; skinfolds
  ±3–5% in skilled hands. The app says so repeatedly, and shows the spread
  between body-fat methods rather than hiding behind one number.
- **Nutrient values are approximations.** Brands, cooking oil and portion size
  all move them. Numbers are deliberately rounded — false precision implies
  accuracy that food tables themselves don't have.
- **Single-user by design.** No auth, no multi-tenancy. SQLite with short-lived
  connections is right for one coach; a multi-user version would need a
  connection pool and real migrations.
- **The activity multiplier is the weakest input** in the whole calculation, and
  almost always overestimated. The UI says to pick lower and let real scale data
  correct it.

## 💡 Ideas to take it further

- **Photo progress tracking** — dated front/side/back images beside the chart,
  since the mirror often shows what the scale hides.
- **Adaptive TDEE** — infer true maintenance from logged weight and intake over
  time instead of trusting the activity multiplier at all.
- **Refeed and diet-break scheduling** — planned maintenance phases based on
  deficit duration, which is what makes long cuts actually work.
- **Bloodwork context** — let a coach record ferritin, vitamin D and lipids so
  the micronutrient panel reflects tested status rather than population risk.
- **Recipe builder** — compose meals from the food database and check them
  against the day's remaining macros.
- **Multi-user + auth** — real accounts so a coach's clients can log their own
  measurements.

---

## 📄 Licence

MIT — see [LICENSE](LICENSE). The nutrition content is compiled from public
guidelines with sources cited throughout; it is educational material, not
clinical guidance.
