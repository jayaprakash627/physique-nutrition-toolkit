"""
engine.py — assembles a full assessment.

This is the layer that makes the product what it is. `formulas.py` produces
numbers and `knowledge/` holds the teaching content; the engine's only job is to
marry them, so no number ever reaches the client without its explanation, its
food examples and its citation attached.

That coupling is enforced structurally rather than by discipline: `_targeted()`
builds every macro block, and it cannot construct one without an explanation
object and a source list. If someone later adds a new target and forgets the
"why", the response shape makes it obvious.

Flow of `assess()`:
    1. Body fat        — four methods, pick the best available, show the spread
    2. Composition     — lean mass, fat mass, FFMI, waist-to-height
    3. Energy          — both BMR equations, TDEE, goal targets
    4. Macros          — protein → fat → carbs, each with its explanation
    5. Fibre & water   — scaled to intake and to climate
    6. Micronutrients  — risk-profiled for this specific client
    7. Safety          — flags over everything above
"""

from __future__ import annotations

from . import formulas as f
from . import planner, safety
from .knowledge import explanations as ex
from .knowledge import foods, micronutrients, sources


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _targeted(*, number, unit: str, explanation: dict,
              how_to_hit: dict | None = None, extra: dict | None = None) -> dict:
    """
    The canonical shape of every recommendation this app produces.

    Every target the client sees goes through here, which is what guarantees the
    "teach, don't just calculate" promise holds everywhere rather than only in
    the places someone remembered.

        number       the figure itself
        unit         so the UI never hardcodes "g"
        why          the full explanation block from knowledge/explanations.py
        how_to_hit   real food portions, diet-filtered
        sources      resolved citations, ready to render
    """
    return {
        "number": number,
        "unit": unit,
        "why": {
            "id": explanation["id"],
            "title": explanation["title"],
            "headline": explanation["headline"],
            "why_this_much": explanation["why_this_much"],
            "what_it_does": explanation["what_it_does"],
            "too_little": explanation["too_little"],
            "too_much": explanation["too_much"],
        },
        "how_to_hit": how_to_hit or {},
        "sources": sources.resolve(*explanation["source_keys"]),
        **(extra or {}),
    }


# ---------------------------------------------------------------------------
#  1. Body fat — every method we can run from the given inputs
# ---------------------------------------------------------------------------

def bodyfat_report(inp: dict) -> dict:
    """
    Run every body-fat method the supplied measurements allow, and be honest
    about the disagreement between them.

    Method preference when several are available: 7-site > 3-site > Navy tape >
    Deurenberg. That order reflects accuracy in trained populations, and
    Deurenberg is last because BMI cannot see muscle.
    """
    sex = inp["sex"]
    age = inp["age"]
    weight = inp["weight_kg"]
    height = inp["height_cm"]
    sk = inp.get("skinfolds") or {}
    g = inp.get("girths") or {}

    bmi_val = f.bmi(weight_kg=weight, height_cm=height)

    results = []

    navy = f.bodyfat_navy(
        sex=sex, height_cm=height,
        neck_cm=g.get("neck"), waist_cm=g.get("waist"), hip_cm=g.get("hip"),
    )
    if navy is not None:
        results.append({"method": "navy", "value": navy})

    jp3 = f.bodyfat_jp3(
        sex=sex, age=age,
        chest=sk.get("chest"), abdomen=sk.get("abdomen"), thigh=sk.get("thigh"),
        triceps=sk.get("triceps"), suprailiac=sk.get("suprailiac"),
    )
    if jp3 is not None:
        results.append({"method": "jp3", "value": jp3})

    # 7-site needs all seven; only attempt it when every site is present.
    jp7_sites = ["chest", "midaxillary", "triceps", "subscapular",
                 "abdomen", "suprailiac", "thigh"]
    if all(sk.get(s) for s in jp7_sites):
        jp7 = f.bodyfat_jp7(sex=sex, age=age, **{s: sk[s] for s in jp7_sites})
        if jp7 is not None:
            results.append({"method": "jp7", "value": jp7})

    deur = f.bodyfat_deurenberg(sex=sex, age=age, bmi=bmi_val)
    if deur is not None:
        results.append({"method": "deurenberg", "value": deur})

    # Attach the teaching notes for each method that ran.
    for r in results:
        note = ex.BODYFAT_METHOD_NOTES[r["method"]]
        r.update({
            "name": note["name"],
            "needs": note["needs"],
            "trust": note["trust"],
            "how": note["how"],
            "watch": note["watch"],
            "sources": sources.resolve(*note["source_keys"]),
            "band": f.classify_bodyfat(sex, r["value"])["label"],
        })

    # Which one do we build the rest of the report on?
    preference = ["jp7", "jp3", "navy", "deurenberg"]
    chosen = None
    for pref in preference:
        match = next((r for r in results if r["method"] == pref), None)
        if match:
            chosen = match
            break

    # A directly supplied body-fat figure (from a DEXA scan, say) always wins —
    # a real measurement beats any estimate.
    supplied = inp.get("bodyfat_pct")
    if supplied:
        chosen = {
            "method": "supplied",
            "value": round(float(supplied), 1),
            "name": "Supplied by you",
            "needs": "A measurement you already trust (DEXA, BodPod, InBody, or a coach's callipers)",
            "trust": "Depends on the source — a DEXA scan beats every estimate here",
            "how": "You entered this directly, so the app uses it rather than estimating.",
            "watch": "Even DEXA carries ±2–3% error, and hydration shifts BIA/InBody "
                     "readings noticeably between mornings.",
            "sources": [],
            "band": f.classify_bodyfat(sex, round(float(supplied), 1))["label"],
        }
        results.insert(0, chosen)

    values = [r["value"] for r in results if r["method"] != "supplied"]
    spread = round(max(values) - min(values), 1) if len(values) > 1 else 0.0

    return {
        "bmi": bmi_val,
        "methods": results,
        "chosen": chosen,
        "spread": spread,
        "spread_note": ex.SPREAD_EXPLAINER,
        "bands": f.BODYFAT_BANDS[sex],
        "band_source": sources.resolve("ACE_BODYFAT"),
        "available_note": (
            "Only the methods you supplied measurements for are shown. Add neck "
            "and waist girths for the Navy method, or calliper readings for "
            "Jackson–Pollock, to compare more of them."
        ),
    }


# ---------------------------------------------------------------------------
#  2. Composition
# ---------------------------------------------------------------------------

def composition_report(inp: dict, bf_pct: float) -> dict:
    """Lean mass, fat mass, FFMI, waist-to-height, and goal-weight maths."""
    weight = inp["weight_kg"]
    height = inp["height_cm"]
    sex = inp["sex"]
    girths = inp.get("girths") or {}

    lbm = f.lean_mass(weight_kg=weight, bf_pct=bf_pct)
    fm = f.fat_mass(weight_kg=weight, bf_pct=bf_pct)
    ffmi_val = f.ffmi(lbm_kg=lbm, height_cm=height)

    whtr = None
    if girths.get("waist"):
        whtr = f.waist_to_height(waist_cm=girths["waist"], height_cm=height)
        whtr["sources"] = sources.resolve("WHTR")
        whtr["explain"] = (
            "Keep your waist under half your height. It's a better flag for the "
            "fat stored around your organs (visceral fat) than BMI is, and you "
            "can check it with a tape and no arithmetic."
        )

    # What would you weigh at a range of goal body-fat levels?
    floor = f.SAFE_BODYFAT_FLOOR[sex]
    goal_points = [floor, floor + 2, floor + 4, floor + 6, floor + 8]
    goal_weights = [
        {
            "bodyfat_pct": round(p, 1),
            "weight_kg": f.target_weight_for_bodyfat(lbm_kg=lbm, target_bf_pct=p),
            "change_kg": round(
                f.target_weight_for_bodyfat(lbm_kg=lbm, target_bf_pct=p) - weight, 1
            ),
            "band": f.classify_bodyfat(sex, p)["label"],
        }
        for p in goal_points
    ]

    return {
        "weight_kg": weight,
        "bodyfat_pct": bf_pct,
        "lean_mass_kg": lbm,
        "fat_mass_kg": fm,
        "bodyfat_band": f.classify_bodyfat(sex, bf_pct),
        "ffmi": {
            **ffmi_val,
            "band": f.ffmi_band(ffmi_val["normalised"]),
            "context": ex.FFMI_CONTEXT,
            "sources": sources.resolve("KOURI_FFMI"),
        },
        "waist_to_height": whtr,
        "goal_weights": goal_weights,
        "goal_weight_note": (
            "These assume you keep every kilo of your current lean mass while "
            "losing fat — the best case. A slow cut with enough protein and hard "
            "training gets close; a crash diet doesn't, because lean mass goes "
            "too. Treat them as the floor of what you'd weigh, not a promise."
        ),
        "lean_mass_explain": (
            f"Your lean body mass is {lbm} kg — bone, organs, water and muscle, "
            "everything except fat. This is the number that drives your protein "
            "target and the better of the two BMR equations, because it's what "
            "actually needs feeding. Fat tissue is metabolically quiet by "
            "comparison."
        ),
    }


# ---------------------------------------------------------------------------
#  3. Energy
# ---------------------------------------------------------------------------

def energy_report(inp: dict, lbm: float) -> dict:
    """Both BMR equations side by side, TDEE, and the four goal targets."""
    sex, weight, height, age = inp["sex"], inp["weight_kg"], inp["height_cm"], inp["age"]
    activity = inp.get("activity", "moderate")

    mifflin = f.bmr_mifflin(sex=sex, weight_kg=weight, height_cm=height, age=age)
    katch = f.bmr_katch_mcardle(lbm_kg=lbm)

    # Katch–McArdle is preferred because it reads lean mass directly — but it
    # inherits the error of the body-fat estimate that produced that lean mass.
    chosen_method = "Katch–McArdle"
    chosen_bmr = katch

    tdee_val = f.tdee(bmr=chosen_bmr, activity=activity)
    targets = f.energy_targets(tdee_kcal=tdee_val, weight_kg=weight)

    return {
        "bmr": {
            "mifflin": mifflin,
            "katch_mcardle": katch,
            "chosen": chosen_bmr,
            "chosen_method": chosen_method,
            "difference": abs(mifflin - katch),
            "why_katch": (
                "Both equations estimate the same thing — the calories you'd burn "
                "lying still all day — but they ask different questions.\n\n"
                f"Mifflin–St Jeor ({mifflin} kcal) uses your total bodyweight. "
                "It's the most accurate equation for the general population, but "
                "it can't tell muscle from fat: two people at the same weight get "
                "the same answer even if one is 12% body fat and the other 30%.\n\n"
                f"Katch–McArdle ({katch} kcal) uses only your lean mass — "
                "370 + 21.6 × LBM. Muscle burns calories at rest; fat barely "
                "does. For a trained lifter that's the more meaningful input, so "
                "it's the one this report builds on.\n\n"
                "The catch: Katch–McArdle is only as good as your body-fat "
                f"estimate, since that's what lean mass comes from. The two "
                f"differ by {abs(mifflin - katch)} kcal here — if that gap is "
                "large, your body-fat estimate is the thing to tighten up first."
            ),
            "sources": sources.resolve("MIFFLIN", "KATCH_MCARDLE"),
        },
        "activity": {
            "key": activity,
            "factor": f.ACTIVITY_LEVELS[activity]["factor"],
            "label": f.ACTIVITY_LEVELS[activity]["label"],
            "all_levels": f.ACTIVITY_LEVELS,
            "explain": (
                "Your activity factor multiplies BMR to give TDEE — what you "
                "actually burn on an average day. This is the biggest source of "
                "error in the whole calculation, and almost always in the same "
                "direction: people overestimate. Four gym sessions a week plus a "
                "desk job and few steps is 'light' to 'moderate', not 'active'. "
                "When in doubt, pick the lower bracket and let real scale data "
                "correct you."
            ),
            "sources": sources.resolve("ACSM_ENERGY"),
        },
        "tdee": tdee_val,
        "targets": targets,
        "targets_explain": (
            "Cut is 20% below maintenance; the aggressive option is 25% and "
            "carries the trade-offs the safety notes describe. Lean bulk is only "
            "10% above, because muscle can't be built faster than roughly "
            "0.25–0.5% of bodyweight per week — a bigger surplus adds fat, not "
            "speed."
        ),
        "sources": sources.resolve("MIFFLIN", "KATCH_MCARDLE", "ACSM_ENERGY", "HELMS_NATURAL"),
    }


# ---------------------------------------------------------------------------
#  4–5. Nutrition plan: macros, fibre, water
# ---------------------------------------------------------------------------

def nutrition_report(inp: dict, *, kcal: float, lbm: float, tdee_val: float,
                     bmr_val: float, goal: str) -> dict:
    """
    The macro plan, with every number carrying its explanation and food examples.

    Order is load-bearing: protein from lean mass, fat to its floor, carbs take
    the remainder. See `formulas.macros` and the explanation text for why.
    """
    weight = inp["weight_kg"]
    diet = inp.get("diet", "omnivore")
    meals = inp.get("meals", 4)
    climate = inp.get("climate", "hot")
    training_hours = inp.get("training_hours", 1.0)

    m = f.macros(kcal=kcal, weight_kg=weight, lbm_kg=lbm, goal=goal)
    p, fat_b, c = m["protein"], m["fat"], m["carbs"]

    # --- Calories ---------------------------------------------------------
    delta = round(kcal - tdee_val)
    rate_kg = delta * 7 / f.KCAL_PER_KG_FAT
    kcal_ctx = {
        "target": round(kcal),
        "tdee": round(tdee_val),
        "bmr_used": round(bmr_val),
        "bmr_method": "Katch–McArdle",
        "delta": delta,
        "delta_pct": abs(round(delta / tdee_val * 100)) if tdee_val else 0,
        "goal": goal,
        "rate_kg_per_week": round(abs(rate_kg), 2),
        "rate_pct_bw": round(abs(rate_kg) / weight * 100, 2),
    }

    # --- Protein ----------------------------------------------------------
    protein_ctx = {
        **p, "lbm_kg": lbm, "goal": goal, "kcal": p["kcal"],
        "deficit_pct": kcal_ctx["delta_pct"],
        "in_issn_range": 1.6 <= p["g_per_kg_bw"] <= 2.2,
    }
    sample_day = foods.sample_plate(p["grams"], diet)
    # Whole portions rarely land exactly on target, so state the total the plate
    # actually delivers rather than implying it's a perfect match.
    sample_total = round(sum(x["protein_g"] for x in sample_day), 1)

    protein_block = _targeted(
        number=p["grams"], unit="g/day",
        explanation=ex.protein(protein_ctx),
        how_to_hit={
            "single_food_equivalents": foods.portions_for_protein(p["grams"], diet),
            "sample_day": sample_day,
            "sample_day_total_g": sample_total,
            "sample_day_kcal": sum(x["kcal"] for x in sample_day),
            "note": (
                "The first list shows what your whole target looks like in ONE "
                "food — for scale, not as a suggestion to eat only paneer. The "
                f"sample day is one realistic way to combine them, landing at "
                f"{sample_total} g against your {p['grams']} g target; real "
                "portions come in whole units, so close is the goal, not exact."
            ),
        },
        extra={
            "kcal": p["kcal"], "pct_kcal": p["pct_kcal"],
            "g_per_kg_bw": p["g_per_kg_bw"], "g_per_kg_lbm": p["g_per_kg_lbm"],
            "issn_range_g_per_kg": [1.6, 2.2],
            "in_issn_range": protein_ctx["in_issn_range"],
        },
    )

    # --- Fat --------------------------------------------------------------
    fat_block = _targeted(
        number=fat_b["grams"], unit="g/day",
        explanation=ex.fat({**fat_b, "kcal": fat_b["kcal"]}),
        how_to_hit={
            "portions": [
                {
                    "name": x["name"], "household": x["household"],
                    "fat_g": x["fat_g"], "kcal": x["kcal"],
                }
                for x in foods.FAT_FOODS if foods.diet_ok(x, diet)
            ],
            "note": (
                "Fat adds up fast — it's 9 kcal per gram against 4 for protein "
                "and carbs. Two tablespoons of oil in cooking is already ~30 g. "
                "Measure the cooking oil for a week and you'll find most of your "
                "unaccounted calories."
            ),
        },
        extra={
            "kcal": fat_b["kcal"], "pct_kcal": fat_b["pct_kcal"],
            "g_per_kg_bw": fat_b["g_per_kg_bw"],
            "floor_g": fat_b["floor_g"], "below_floor": fat_b["below_floor"],
        },
    )

    # --- Carbs ------------------------------------------------------------
    carb_block = _targeted(
        number=c["grams"], unit="g/day",
        explanation=ex.carbs({
            **c, "kcal": c["kcal"], "goal": goal,
            "low_warning": c["g_per_kg_bw"] < 2.0,
            "training_days": training_hours,
        }),
        how_to_hit={
            "portions": [
                {
                    "name": x["name"], "household": x["household"],
                    "carb_g": x["carb_g"], "kcal": x["kcal"], "fibre_g": x["fibre_g"],
                }
                for x in foods.CARB_FOODS if foods.diet_ok(x, diet)
            ],
            "note": (
                "Put most of your carbs around training, where the glycogen "
                "actually gets used. Favour whole sources — millets, brown rice, "
                "oats, dal, fruit — since they bring fibre and micronutrients "
                "with them, which refined flour and sugar don't."
            ),
        },
        extra={
            "kcal": c["kcal"], "pct_kcal": c["pct_kcal"],
            "g_per_kg_bw": c["g_per_kg_bw"],
        },
    )

    # --- Fibre ------------------------------------------------------------
    fib = f.fibre_target(kcal=kcal)
    fibre_block = _targeted(
        number=fib["grams"], unit="g/day",
        explanation=ex.fibre(fib),
        how_to_hit={
            "portions": foods.high_fibre_picks(diet),
            "note": (
                "Increase gradually — about 5 g a week — and raise water at the "
                "same time. Fibre without water makes constipation worse, not "
                "better."
            ),
        },
        extra={"clamped": fib["clamped"], "unclamped": fib["unclamped"]},
    )

    # --- Water ------------------------------------------------------------
    w = f.water_target(
        weight_kg=weight, training_hours=training_hours,
        climate=climate, protein_g=p["grams"],
    )
    water_block = _targeted(
        number=w["total_l"], unit="L/day",
        explanation=ex.water({
            **w, "training_hours": training_hours, "climate": climate.replace("_", " "),
            "weight_kg": weight,
        }),
        how_to_hit={
            "breakdown": [
                {"label": "Baseline (35 ml/kg)", "ml": w["baseline_ml"]},
                {"label": f"Training ({training_hours} h)", "ml": w["training_ml"]},
                {"label": f"Climate ({climate.replace('_', ' ')})", "ml": w["climate_ml"]},
                {"label": "High-protein allowance", "ml": w["protein_ml"]},
            ],
            "note": (
                f"About {w['from_food_ml']} ml of this comes from food — dal, "
                f"curd, fruit, sabzi and chai all count — so you're aiming for "
                f"roughly {round(w['from_drinks_ml'] / 1000, 1)} L from drinks. "
                "Check urine colour: pale straw is right, dark yellow means "
                "you're behind."
            ),
        },
        extra={"total_ml": w["total_ml"], "breakdown": w},
    )

    # --- Meal split -------------------------------------------------------
    split = f.meal_split(
        protein_g=p["grams"], carb_g=c["grams"], fat_g=fat_b["grams"], meals=meals,
    )

    return {
        "kcal": _targeted(
            number=round(kcal), unit="kcal/day",
            explanation=ex.calories(kcal_ctx),
            how_to_hit={
                "note": (
                    "Weigh yourself at the same time each morning, take a weekly "
                    "average, and compare that average across 2–3 weeks. Daily "
                    "weight swings of 1–2 kg are water, salt and food in transit — "
                    "not fat. Adjust off the trend, never off one morning."
                ),
            },
            extra={
                "tdee": round(tdee_val), "delta": delta,
                "delta_pct": kcal_ctx["delta_pct"],
                "rate_kg_per_week": kcal_ctx["rate_kg_per_week"],
                "rate_pct_bw": kcal_ctx["rate_pct_bw"],
            },
        ),
        "protein": protein_block,
        "fat": fat_block,
        "carbs": carb_block,
        "fibre": fibre_block,
        "water": water_block,
        "meal_split": {
            "meals": split,
            "explain": (
                "Protein is spread evenly across meals on purpose: muscle protein "
                "synthesis responds to each dose, so 4 × 40 g beats 160 g in one "
                "sitting. Carbs are weighted toward the meal around training, "
                "where they get used; fat is weighted away from it, since it "
                "slows digestion and you don't want it sitting in your stomach "
                "mid-session.\n\n"
                "That said — daily totals do most of the work. Timing is a "
                "refinement, not the foundation. Hitting your numbers on a "
                "schedule you can actually keep beats a perfect split you abandon."
            ),
            "sources": sources.resolve("ISSN_PROTEIN", "ACSM_ENERGY"),
        },
        "_raw_macros": m,      # kept for the safety layer; stripped from responses
    }


# ---------------------------------------------------------------------------
#  6. Micronutrients
# ---------------------------------------------------------------------------

def micro_report(inp: dict, *, deficit_pct: float, goal: str,
                 carb_g_per_kg: float, fat_g_per_kg: float) -> dict:
    """Risk-profile the client, then order the panel by what matters for them."""
    diet = inp.get("diet", "omnivore")
    sex = inp["sex"]

    risk_tags = micronutrients.build_risk_profile(
        diet=diet, sex=sex, deficit_pct=deficit_pct,
        climate=inp.get("climate", "hot"),
        training_hours=inp.get("training_hours", 1.0),
        goal=goal, carb_g_per_kg=carb_g_per_kg, fat_g_per_kg=fat_g_per_kg,
        contest_prep=inp.get("contest_prep", False),
    )

    panel = micronutrients.panel_for(risk_tags, sex)

    # Attach diet-appropriate food sources and resolved citations to each row.
    for row in panel:
        row["food_sources"] = foods.sources_for_micro(row["key"], diet)
        row["sources"] = sources.resolve(*row["source_keys"])
        if not row["food_sources"]:
            row["no_food_source_note"] = (
                "No strong whole-food source of this nutrient fits your diet. "
                "That absence is exactly why a supplement is worth discussing "
                "here — this is the case where 'just eat better' isn't an answer."
            )

    risks = [
        {"tag": t, **micronutrients.RISK_DEFINITIONS[t]}
        for t in risk_tags if t in micronutrients.RISK_DEFINITIONS
    ]

    return {
        "risk_tags": risk_tags,
        "risks": risks,
        "panel": panel,
        "priority_count": len([r for r in panel if r["priority"] == "high"]),
        "explain": (
            "Macros decide how you look. Micronutrients decide whether you feel "
            "like a functioning human getting there — and they're what almost "
            "every calculator skips.\n\n"
            "The cruel part is the timing: a deep cut means less total food, so "
            "fewer vitamins and minerals, at exactly the point where training "
            "stress and sweat losses raise your needs. Intake down, requirement "
            "up. That's when deficiencies show up, and they show up as fatigue, "
            "poor recovery and getting ill — which people blame on 'overtraining' "
            "instead.\n\n"
            "The panel below is ordered for you specifically, based on your diet, "
            "sex, deficit depth and training conditions. Anything marked "
            "PRIORITY has more than one reason to be on your radar."
        ),
        "targets_explain": (
            "Two reference sets are shown for each nutrient. ICMR-NIN (2020) is "
            "the Indian RDA; the Western column is the IOM/WHO/EFSA figure. Where "
            "they differ substantially — iron and zinc most of all — it isn't an "
            "error: Indian RDAs are higher because phytates in a cereal-and-pulse "
            "diet block absorption, so you have to eat more to absorb the same "
            "amount. Same biology, less absorbable food."
        ),
        "sources": sources.resolve("ICMR_NIN_2020", "IOM_MICRO", "NIH_ODS", "IFCT_2017"),
    }


# ---------------------------------------------------------------------------
#  Top-level assessment
# ---------------------------------------------------------------------------

def plain_summary(*, nutrition: dict, goal: str, diet: str,
                  bf_method: str) -> dict:
    """
    The beginner's answer: one sentence, one priority, three actions.

    Added after real user testing. The full report is accurate but it opens with
    six target cards and a micronutrient panel — which reads as homework, not
    help. People who have never tracked food don't need the whole picture first;
    they need to know what to eat tomorrow, and which single number to care about
    if they can only manage one.

    So this is deliberately reductive. It names ONE priority (protein), gives
    three concrete actions, and says what to expect. Everything else stays
    available one click away — the depth isn't removed, just demoted.
    """
    kcal = nutrition["kcal"]
    protein = nutrition["protein"]
    carbs = nutrition["carbs"]
    fat = nutrition["fat"]
    water = nutrition["water"]
    fibre = nutrition["fibre"]

    rate = kcal.get("rate_kg_per_week", 0)

    if goal in ("cut", "aggressive_cut"):
        headline = f"Eat about {kcal['number']:,} calories a day to lose fat."
        expect = (
            f"At this intake you'd lose roughly {rate} kg a week. That's "
            "deliberately not faster — quicker weight loss mostly costs you "
            "muscle, so you end up smaller rather than leaner."
        )
        priority_why = (
            "You're eating less than you burn, so your body is looking for "
            "tissue to break down. Protein is the strongest signal telling it to "
            "take that from fat and leave your muscle alone. It also keeps you "
            "fullest, which is what makes this survivable."
        )
    elif goal == "bulk":
        headline = f"Eat about {kcal['number']:,} calories a day to build muscle."
        expect = (
            f"You'd gain roughly {rate} kg a week. It's a small surplus on "
            "purpose — muscle can only be built so fast, and a bigger surplus "
            "just adds fat you'd have to diet off later."
        )
        priority_why = (
            "Protein is the raw material your body stitches into new muscle. "
            "Without enough of it, the training happens but the rebuilding "
            "doesn't."
        )
    else:
        headline = f"Eat about {kcal['number']:,} calories a day to hold steady."
        expect = (
            "Your weight should stay roughly where it is. This is where you "
            "recover best and train hardest."
        )
        priority_why = (
            "Protein covers daily repair and keeps you full. Getting enough now "
            "means you're not starting from behind whenever you do decide to cut "
            "or build."
        )

    # Three actions, ordered by how much they actually matter.
    steps = [
        {
            "n": 1,
            "do": f"Hit {protein['number']} g of protein a day",
            "how": "Build every meal around a protein source first — eggs, "
                   "chicken, fish, paneer, curd, dal or soya — then add the rest. "
                   "Getting this right matters more than everything else combined.",
        },
        {
            "n": 2,
            "do": f"Drink about {water['number']} litres of fluid a day",
            "how": "Food counts too — dal, curd, fruit and chai all add up. Check "
                   "the colour: pale straw is right, dark yellow means you're "
                   "behind. It's the easiest win on this list.",
        },
        {
            "n": 3,
            "do": "Weigh yourself weekly, not daily",
            "how": "Same time each morning, then compare the weekly average "
                   "across 2–3 weeks. Day-to-day swings of 1–2 kg are water and "
                   "food in transit, not fat. Adjust off the trend.",
        },
    ]

    accuracy = (
        "This estimate came from your height, weight and age alone, which is the "
        "roughest method — it can't tell muscle from fat, so if you train it "
        "probably over-estimates your body fat. Adding a tape measurement takes "
        "about 30 seconds and meaningfully improves everything downstream."
        if bf_method == "deurenberg"
        else
        "Good news: your measurements let us use a better body-fat method than "
        "height and weight alone, so these numbers are on firmer ground."
    )

    return {
        "headline": headline,
        "expect": expect,
        "priority": {
            "label": "If you only track one thing, track this",
            "what": f"{protein['number']} g protein a day",
            "why": priority_why,
        },
        "plate": (
            f"Across the day that's roughly {protein['number']} g protein, "
            f"{carbs['number']} g carbs and {fat['number']} g fat — plus "
            f"{fibre['number']} g of fibre from vegetables, fruit, dal and whole "
            "grains."
        ),
        "steps": steps,
        "accuracy_note": accuracy,
        "needs_better_measurement": bf_method == "deurenberg",
        "reassurance": (
            "You don't have to be perfect at this. Getting close on most days "
            "beats being exact for a week and quitting. Nothing here is a rule — "
            "it's a starting point you adjust using your own results."
        ),
    }


def assess(inp: dict) -> dict:
    """
    Run a complete assessment.

    `inp` is the validated AssessmentIn payload as a dict (see models.py).
    Returns the full report, safety flags included. Nothing is hidden when a
    safety flag fires — the numbers stay visible, clearly marked as not
    recommended, because sending someone to a worse tool with no warning helps
    nobody.
    """
    goal = inp.get("goal", "cut")
    sex = inp["sex"]

    # --- 1 & 2: body fat and composition ---------------------------------
    bf = bodyfat_report(inp)
    if not bf["chosen"]:
        # No method could run — no girths, no skinfolds, and Deurenberg somehow
        # failed. Deurenberg needs only height/weight/age, so this is very rare.
        raise ValueError(
            "Not enough measurements to estimate body fat. Provide either "
            "neck and waist girths, or calliper skinfolds, or a body-fat "
            "percentage you already know."
        )
    bf_pct = bf["chosen"]["value"]
    comp = composition_report(inp, bf_pct)
    lbm = comp["lean_mass_kg"]

    # --- 3: energy --------------------------------------------------------
    energy = energy_report(inp, lbm)
    tdee_val = energy["tdee"]
    bmr_val = energy["bmr"]["chosen"]

    # Which calorie target does the chosen goal correspond to?
    goal_key = {"cut": "cut", "maintain": "maintain", "bulk": "bulk",
                "aggressive_cut": "aggressive_cut"}.get(goal, "cut")
    kcal = energy["targets"][goal_key]["kcal"]
    # Normalise the goal for the macro logic: an aggressive cut is still a cut.
    macro_goal = "cut" if goal_key in ("cut", "aggressive_cut") else goal_key

    # --- 4 & 5: nutrition -------------------------------------------------
    nutrition = nutrition_report(
        inp, kcal=kcal, lbm=lbm, tdee_val=tdee_val,
        bmr_val=bmr_val, goal=macro_goal,
    )
    raw_macros = nutrition.pop("_raw_macros")

    deficit_pct = abs(nutrition["kcal"]["delta_pct"])
    carb_per_kg = raw_macros["carbs"]["g_per_kg_bw"]
    fat_per_kg = raw_macros["fat"]["g_per_kg_bw"]

    # --- 6: micronutrients ------------------------------------------------
    micros = micro_report(
        inp, deficit_pct=deficit_pct, goal=macro_goal,
        carb_g_per_kg=carb_per_kg, fat_g_per_kg=fat_per_kg,
    )

    # --- 7: safety over everything ---------------------------------------
    flags = []
    flags += safety.check_demographics(
        age=inp["age"], sex=sex,
        pregnant=inp.get("pregnant", False),
        medical_conditions=inp.get("medical_conditions", False),
    )
    flags += safety.check_bodyfat_target(
        sex=sex, current_bf=bf_pct, target_bf=inp.get("target_bodyfat_pct"),
    )
    flags += safety.check_energy(
        sex=sex, kcal_target=kcal, bmr=bmr_val, tdee=tdee_val,
        weight_kg=inp["weight_kg"],
        rate_pct_bw=nutrition["kcal"]["rate_pct_bw"], goal=macro_goal,
    )
    flags += safety.check_macros(
        macro_block=raw_macros, weight_kg=inp["weight_kg"], sex=sex,
    )
    flags += safety.check_hydration(
        water_ml=nutrition["water"]["total_ml"], weight_kg=inp["weight_kg"],
    )

    return {
        "input": inp,
        # The beginner-facing answer comes first in the payload because it's what
        # the UI leads with. Everything below it is the depth behind that answer.
        "summary": plain_summary(
            nutrition=nutrition, goal=macro_goal,
            diet=inp.get("diet", "omnivore"),
            bf_method=bf["chosen"]["method"],
        ),
        "bodyfat": bf,
        "composition": comp,
        "energy": energy,
        "nutrition": nutrition,
        "micronutrients": micros,
        "safety": safety.summarise(flags),
        "disclaimer": sources.DISCLAIMER,
        "safeguarding": sources.SAFEGUARDING_NOTE,
    }


# ---------------------------------------------------------------------------
#  Standalone tools
# ---------------------------------------------------------------------------

def prep_report(inp: dict) -> dict:
    """Contest / goal prep planner: current % → target % by a deadline."""
    plan = f.prep_plan(
        weight_kg=inp["weight_kg"],
        current_bf=inp["current_bodyfat_pct"],
        target_bf=inp["target_bodyfat_pct"],
        weeks=inp["weeks"],
        sex=inp["sex"],
    )
    flags = safety.check_prep_plan(plan=plan, sex=inp["sex"])
    flags += safety.check_bodyfat_target(
        sex=inp["sex"], current_bf=inp["current_bodyfat_pct"],
        target_bf=inp["target_bodyfat_pct"],
    )

    return {
        "plan": plan,
        "safety": safety.summarise(flags),
        "explain": (
            f"To go from {inp['current_bodyfat_pct']}% to "
            f"{inp['target_bodyfat_pct']}% body fat in {plan['weeks']} weeks you'd "
            f"need to {'lose' if plan['direction'] == 'loss' else 'gain'} "
            f"{plan['total_change_kg']} kg — {plan['per_week_kg']} kg per week, or "
            f"{plan['per_week_pct_bw']}% of your bodyweight weekly.\n\n"
            "The projection holds your lean mass constant, which is the best "
            "case: it assumes a moderate deficit, protein at the top of its "
            "range, and hard training throughout. Push the rate faster than "
            "0.5–1.0% of bodyweight per week and that assumption breaks — the "
            "extra loss comes out of muscle, and the finished physique is smaller "
            "rather than leaner.\n\n"
            f"That's why the safe-rate figure ({plan['weeks_at_safe_rate']} weeks) "
            "matters more than the deadline. The date is the only variable here "
            "you can change for free."
        ),
        "implied_kcal_note": (
            f"The required rate implies roughly a "
            f"{plan['implied_daily_kcal_delta']} kcal daily "
            f"{'deficit' if plan['direction'] == 'loss' else 'surplus'} "
            "(using ~7700 kcal per kg of body fat). Cross-check that against the "
            "calorie targets in the main assessment — if it's much larger, the "
            "timeline is the problem, not your discipline."
        ),
        "sources": sources.resolve("HELMS_NATURAL", "ACSM_ENERGY", "RED_S", "ACE_BODYFAT"),
        "disclaimer": sources.DISCLAIMER,
    }


def strength_report(inp: dict) -> dict:
    """1RM estimate, % of 1RM loading table, and optional DOTS/Wilks scoring."""
    orm = f.one_rep_max(weight=inp["weight"], reps=inp["reps"])
    table = f.pct_table(orm["average"])

    scores = None
    if inp.get("bodyweight_kg") and inp.get("total_kg"):
        dots = f.dots_score(
            sex=inp.get("sex", "male"),
            bodyweight_kg=inp["bodyweight_kg"], total_kg=inp["total_kg"],
        )
        wilks = f.wilks_score(
            sex=inp.get("sex", "male"),
            bodyweight_kg=inp["bodyweight_kg"], total_kg=inp["total_kg"],
        )
        scores = {
            "dots": dots,
            "wilks": wilks,
            "band": f.strength_band(dots),
            "explain": (
                "DOTS and Wilks both normalise a powerlifting total against "
                "bodyweight, so a 66 kg lifter and a 105 kg lifter can be "
                "compared fairly — lighter lifters are stronger per kilo, and a "
                "raw total hides that.\n\n"
                "DOTS is the modern standard and what most federations now use. "
                "Wilks is shown alongside it because nearly every historical meet "
                "result is recorded in Wilks, so you'll need it to compare "
                "against older numbers."
            ),
            "sources": sources.resolve("IPF_DOTS", "WILKS"),
        }

    return {
        "one_rm": orm,
        "table": table,
        "scores": scores,
        "explain": (
            f"From {inp['weight']} kg for {orm['reps']} reps, your estimated 1RM "
            f"is about {orm['average']} kg.\n\n"
            f"Two equations are shown because they disagree usefully — and the "
            f"disagreement flips direction. Epley gives {orm['epley']} kg and "
            f"Brzycki {orm['brzycki']} kg. They land on exactly the same answer "
            "at 10 reps; below 10 Epley reads higher, above 10 Brzycki does. So "
            "the pair brackets the real value instead of pretending to a single "
            "answer.\n\n"
            "Accuracy depends entirely on the set being close to failure — an "
            "estimate from a comfortable set is meaningless. It's also best below "
            "about 10 reps; a 20-rep set tells you more about your conditioning "
            "than your maximal strength.\n\n"
            f"Confidence for {orm['reps']} reps: {orm['confidence']}."
        ),
        "table_explain": (
            "Use this to pick working weights. Strength adaptations live at 85% "
            "and above with low reps and long rest; the 65–80% range is where "
            "most muscle growth happens, because you can accumulate real volume "
            "there. The rep figures are typical for trained lifters — they vary by "
            "exercise (most people do more reps at a given % on leg press than on "
            "a squat) and by individual, so treat them as a starting point and "
            "adjust from what you actually hit."
        ),
        "sources": sources.resolve("EPLEY", "BRZYCKI"),
        "disclaimer": sources.DISCLAIMER,
    }


def meal_plan_report(inp: dict, *, budget: str = "moderate",
                     dislikes: str = "", allergies: str = "") -> dict:
    """
    The coach's diet builder: the macro arithmetic, then a day of real food.

    Runs the same body-fat → composition → energy chain the public assessment
    uses, so the calorie and protein figures here are the ones the client already
    saw. Building a plan off a separately-derived number would be the fastest way
    to have a coach and their client reading two different sets of targets.
    """
    goal = inp.get("goal", "cut")

    bf = bodyfat_report(inp)
    if not bf["chosen"]:
        raise ValueError(
            "Not enough measurements to estimate body fat. Provide either "
            "neck and waist girths, or calliper skinfolds, or a body-fat "
            "percentage you already know."
        )
    comp = composition_report(inp, bf["chosen"]["value"])
    lbm = comp["lean_mass_kg"]
    energy = energy_report(inp, lbm)

    goal_key = goal if goal in energy["targets"] else "cut"
    kcal = energy["targets"][goal_key]["kcal"]
    macro_goal = "cut" if goal_key in ("cut", "aggressive_cut") else goal_key

    built = planner.plan(
        inp, kcal=kcal, lbm_kg=lbm, goal=macro_goal,
        budget=budget, dislikes=dislikes, allergies=allergies,
    )

    # The safety layer still runs. A meal plan that hits its macros perfectly is
    # not a safe plan if the calorie target underneath it was never safe, and the
    # coach should see that flag on this screen rather than only on the
    # assessment they may not have opened.
    flags = safety.check_energy(
        sex=inp["sex"], kcal_target=kcal, bmr=energy["bmr"]["chosen"],
        tdee=energy["tdee"], weight_kg=inp["weight_kg"],
        rate_pct_bw=abs(round((kcal - energy["tdee"]) * 7 / f.KCAL_PER_KG_FAT
                              / inp["weight_kg"] * 100, 2)),
        goal=macro_goal,
    )

    return {
        "input": {
            "weight_kg": inp["weight_kg"], "diet": inp.get("diet", "omnivore"),
            "meals": inp.get("meals", 4), "goal": macro_goal, "budget": budget,
        },
        "bodyfat_pct": bf["chosen"]["value"],
        "bodyfat_method": bf["chosen"]["method"],
        "lean_mass_kg": lbm,
        "tdee": round(energy["tdee"]),
        "math": built["math"],
        "day": built["day"],
        "safety": safety.summarise(flags),
        "sources": sources.resolve("IOM_MACRO", "WHO_FIBRE", "ISSN_PROTEIN", "IFCT_2017"),
        "disclaimer": sources.DISCLAIMER,
    }
