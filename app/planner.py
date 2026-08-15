"""
planner.py — turns a calorie target into a day of real food, and shows the working.

Two things live here, and they answer two different questions a coach gets asked.

**"Where did these numbers come from?"** — `macro_math()` writes out the split as
arithmetic you can check by hand: 2000 kcal in, and every step from lean mass to
grams of rice, with the sum proved at the end. Nothing in it is recalculated.
It reads `formulas.macros()` — the same function the rest of the app uses — and
narrates what that function did. That matters more than it sounds: an explanation
that recomputes its own numbers is an explanation that can quietly disagree with
the plan it claims to describe, and the coach would have no way to tell which one
was wrong.

**"So what do I actually eat?"** — `build_day()` fills the targets with ordinary
food. Dal, eggs, curd, rice, roti, oats, seasonal veg. No imported powders, no
"superfoods", nothing a coach has to apologise for the price of. Budget, diet and
the client's own dislikes come straight from their intake answers.

The fill is greedy and in the same order the macros were built — protein, then
fibre, then carbs, then fat — and it subtracts as it goes, because food doesn't
respect the categories. Eggs bring 16 g of fat with the protein; dal brings 28 g
of carbs. Filling carbs without counting what dal already contributed is how a
"2000 kcal plan" quietly becomes 2400.

Real portions come in whole units, so the plan lands *close* to target, not on
it. `build_day()` reports the gap on every macro rather than rounding it out of
sight — a coach who can see it's 8 g under on protein can fix that in seconds,
and one who's told it's perfect can't.
"""

from __future__ import annotations

from . import formulas as f
from .knowledge import foods

# ---------------------------------------------------------------------------
#  Food rotations — deliberately boring
# ---------------------------------------------------------------------------
#
# Ordered cheapest-and-simplest first, because that's the order a plan should
# reach for. The greedy fill takes them in sequence, so the staples do most of
# the work and the pricier items only appear when the target is still short.

PROTEIN_ROTATION = {
    "omnivore":    ["eggs_whole", "chicken_breast", "curd", "toor_dal", "milk_toned",
                    "chana", "fish_rohu", "paneer_low_fat", "whey"],
    "eggetarian":  ["eggs_whole", "curd", "toor_dal", "milk_toned", "paneer_low_fat",
                    "chana", "greek_yogurt", "whey"],
    "vegetarian":  ["curd", "toor_dal", "milk_toned", "paneer_low_fat", "chana",
                    "rajma", "greek_yogurt", "whey"],
    "vegan":       ["soya_chunks", "toor_dal", "rajma", "chana", "tofu", "peanuts"],
}

CARB_ROTATION = ["rice_cooked", "roti", "oats", "banana", "brown_rice",
                 "sweet_potato", "potato", "idli", "chapati_bajra"]

FAT_ROTATION = ["oil", "peanuts", "almonds", "ghee", "peanut_butter", "flaxseed"]

VEG_ROTATION = ["mixed_veg", "salad_veg", "palak", "bhindi", "sprouts",
                "guava", "apple", "papaya", "orange"]

# Excluded when the client said money is tight. Not a judgement about quality —
# dal and eggs do the same job. It's about a plan they can still afford in month
# four, which is the only kind that works.
PRICEY = {"whey", "almonds", "walnuts", "sardines", "mutton", "tofu", "greek_yogurt"}

# No more than this many portions of any one food in a day, so the plan stays
# something a person would actually eat rather than six katori of dal.
MAX_PORTIONS = 3


def _avoid_set(*texts: str) -> set[str]:
    """
    Turn free-text dislikes and allergies into food keys to skip.

    The intake asks these as open questions ("Foods you genuinely dislike"),
    because a dropdown would never cover it. So the match is deliberately crude:
    lowercase substring against each food's key and display name. It will miss
    phrasing it has never seen, which is why the plan states what it excluded —
    a coach reading "avoided: eggs" can see the match worked, and a coach who
    doesn't see the allergy listed knows to check it themselves.
    """
    blob = " ".join(t.lower() for t in texts if t)
    if not blob.strip():
        return set()
    hits = set()
    for food in foods.ALL_FOODS:
        name = food["name"].lower()
        key = food["key"].lower()
        words = [w for w in key.split("_") if len(w) > 3] + [name.split(",")[0]]
        if any(w in blob for w in words if len(w) > 3):
            hits.add(food["key"])
    return hits


def _usable(key: str, *, diet: str, budget: str, avoid: set[str]) -> bool:
    food = foods.BY_KEY.get(key)
    if not food or key in avoid:
        return False
    if budget == "tight" and key in PRICEY:
        return False
    return foods.diet_ok(food, diet)


def macro_math(*, kcal: float, weight_kg: float, lbm_kg: float, goal: str) -> dict:
    """
    The split, written out as arithmetic a coach can check by hand.

    Reads `formulas.macros()` and explains it. Does not recompute it — see the
    module docstring for why that distinction is the whole point of this
    function.
    """
    m = f.macros(kcal=kcal, weight_kg=weight_kg, lbm_kg=lbm_kg, goal=goal)
    p, fat, carb = m["protein"], m["fat"], m["carbs"]
    goal_key = goal if goal in f.PROTEIN_PER_KG_LBM else "maintain"

    per_kg = f.PROTEIN_PER_KG_LBM[goal_key]
    fat_pct = f.FAT_PCT_KCAL[goal_key]
    floor_from_pct = round(kcal * f.FAT_FLOOR_PCT_KCAL / f.KCAL_PER_G_FAT)
    floor_from_bw = round(weight_kg * f.FAT_FLOOR_G_PER_KG)

    steps = [
        {
            "n": 1,
            "macro": "Protein",
            "rule": f"{per_kg} g per kg of LEAN mass",
            "working": (
                f"{round(lbm_kg, 1)} kg lean × {per_kg} = {p['grams']} g"
                f"  →  {p['grams']} g × {f.KCAL_PER_G_PROTEIN} kcal = {p['kcal']} kcal"
            ),
            "grams": p["grams"],
            "kcal": p["kcal"],
            "pct_kcal": p["pct_kcal"],
            "why": (
                "Off lean mass, not bodyweight — fat tissue doesn't need feeding, "
                "so scaling protein to total weight overfeeds a heavier client and "
                "underfeeds a lean one. It's set first because it's the number you "
                "least want to compromise: in a deficit it's what decides whether "
                "the weight lost is fat or muscle."
            ),
        },
        {
            "n": 2,
            "macro": "Fat",
            "rule": f"{int(fat_pct * 100)}% of calories, then checked against a floor",
            "working": (
                f"{round(kcal)} kcal × {int(fat_pct * 100)}% ÷ {f.KCAL_PER_G_FAT} kcal "
                f"= {round(kcal * fat_pct / f.KCAL_PER_G_FAT)} g"
                + (
                    f"  →  below the floor of {fat['floor_g']} g, so raised to "
                    f"{fat['grams']} g"
                    if fat["below_floor"] else
                    f"  →  above the floor of {fat['floor_g']} g, so kept at {fat['grams']} g"
                )
                + f"  →  {fat['grams']} g × {f.KCAL_PER_G_FAT} kcal = {fat['kcal']} kcal"
            ),
            "grams": fat["grams"],
            "kcal": fat["kcal"],
            "pct_kcal": fat["pct_kcal"],
            "why": (
                f"Second, because fat is the one with a hard biological minimum. The "
                f"floor is whichever is higher of {int(f.FAT_FLOOR_PCT_KCAL * 100)}% of "
                f"calories ({floor_from_pct} g) or {f.FAT_FLOOR_G_PER_KG} g per kg of "
                f"bodyweight ({floor_from_bw} g) — here that's {fat['floor_g']} g. Go "
                "under it for long and hormones and fat-soluble vitamin absorption "
                "suffer, which is a real cost for a change nobody can see."
            ),
        },
        {
            "n": 3,
            "macro": "Carbs",
            "rule": "whatever calories are left",
            "working": (
                f"{round(kcal)} − {p['kcal']} (protein) − {fat['kcal']} (fat) "
                f"= {round(kcal) - p['kcal'] - fat['kcal']} kcal"
                f"  →  ÷ {f.KCAL_PER_G_CARB} kcal = {carb['grams']} g"
                f"  →  {carb['grams']} g × {f.KCAL_PER_G_CARB} kcal = {carb['kcal']} kcal"
            ),
            "grams": carb["grams"],
            "kcal": carb["kcal"],
            "pct_kcal": carb["pct_kcal"],
            "why": (
                "Last, and on purpose. Carbs have the widest safe range of the three, "
                "so they're the right place to absorb the adjustment — every calorie "
                "the other two didn't claim ends up here. This is also why carbs move "
                "most when the calorie target changes: protein and fat are anchored, "
                "carbs flex."
            ),
        },
    ]

    total = p["kcal"] + fat["kcal"] + carb["kcal"]
    fib = f.fibre_target(kcal=kcal)

    return {
        "kcal_target": round(kcal),
        "goal": goal_key,
        "lbm_kg": round(lbm_kg, 1),
        "weight_kg": weight_kg,
        "steps": steps,
        "check": {
            "sum_kcal": total,
            "target_kcal": round(kcal),
            "difference": total - round(kcal),
            "matches": abs(total - round(kcal)) <= 12,
            "working": (
                f"{p['kcal']} + {fat['kcal']} + {carb['kcal']} = {total} kcal "
                f"against a {round(kcal)} kcal target"
            ),
            "note": (
                "The few calories of drift are rounding. Grams are whole numbers "
                "because that's what a client can measure, and the calorie column is "
                "recomputed from those rounded grams rather than the exact fractions "
                "— so the numbers on the page add up to the number at the top, which "
                "is the version a coach can defend."
            ),
        },
        "fibre": {
            "grams": fib["grams"],
            "rule": f"{f.FIBRE_G_PER_1000_KCAL} g per 1000 kcal",
            "working": (
                f"{round(kcal)} ÷ 1000 × {f.FIBRE_G_PER_1000_KCAL} = {fib['unclamped']} g"
                + (f"  →  clamped into the {f.FIBRE_MIN_G}–{f.FIBRE_MAX_TARGET_G} g "
                   f"range at {fib['grams']} g" if fib["clamped"] else "")
            ),
            "why": (
                "Fibre tracks how much food is moving through you, so it scales with "
                "calories rather than sitting at a fixed number. It carries no "
                "calories of its own — it's already counted inside the carb total, "
                "not added on top."
            ),
        },
    }


# What it costs to miss each target, and in which direction. Missing low and
# missing high are not the same mistake, and treating them as if they were is
# what makes a plan technically accurate and nutritionally silly.
#
# These mirror the order the macros were built in, which is not a coincidence —
# protein is anchored, fat has a floor, carbs are the flex:
#
#   protein  under is the real failure; over is harmless. You physically cannot
#            hit a high carb target without rice and roti pushing protein past
#            its number, and refusing to allow that would wreck the carb figure
#            to fix something that was never a problem.
#   fibre    same shape. More fibre is rarely a complaint; too little is.
#   carbs    loose both ways. It's the macro designed to absorb the adjustment.
#   fat      both directions cost — over eats the calorie budget at 9 kcal/g,
#            under runs at the biological floor.
#   kcal     the one number that decides whether any of this works.
PENALTY = {                 # (missing low, going high)
    "kcal":      (1.0, 1.2),
    "protein_g": (1.6, 0.7),
    "fat_g":     (1.0, 0.9),
    "carb_g":    (0.8, 0.8),
    "fibre_g":   (0.8, 0.35),
}
# Protein overshoot is cheap but not free, and that middle setting is doing real
# work. Free, and the plan piles on chicken until carbs are 30% short — hitting
# one number by wrecking another. Expensive, and it can't fill a bulk's carbs at
# all, because rice brings protein whether you want it or not.

# What counts as "close enough" to report as landed, per macro and per direction.
# Published as part of the result rather than hidden in here, so a coach can see
# the standard the plan is being held to instead of trusting the word "close".
BANDS = {                   # (allowed % under, allowed % over)
    "kcal":      (5, 5),
    "protein_g": (5, 45),
    "fat_g":     (10, 15),
    "carb_g":    (15, 15),
    "fibre_g":   (10, None),    # None = no ceiling; see below
}

# The protein band is wide on the high side for the same reason fibre's is: the
# target is the floor you don't want to drop below, not a ceiling. An Indian
# vegetarian plan cannot avoid overshooting it — dal, chana and rajma are the
# protein sources *and* the carb sources, so buying carbs buys protein.
#
# Overshooting protein is only a real problem if it crowds something else out,
# and that's already caught: calories are held to ±5% and carbs to ±15%, so a
# plan that hits its protein by starving the carbs still fails. Which leaves the
# case this band is meant to allow — every other number correct, protein simply
# higher than the minimum — and that is a good plan, not a failed one.
#
# Fibre is a floor, not a target to hit exactly, so going over it isn't a miss —
# the guidance is "at least this much". Marking a plan as failed for delivering
# 40 g against a 30 g target would be reporting a success as a problem, and on a
# vegetarian plan it happens constantly because dal and chana are simultaneously
# the protein source and the fibre source.
#
# There is a real upper limit, it's just not this one: past roughly this much,
# gut tolerance rather than nutrition becomes the binding constraint, so the plan
# says so instead of silently serving it.
FIBRE_COMFORT_CEILING_G = 55


def _error(running: dict, targets: dict) -> float:
    """
    How far this plan is from the targets, as one number.

    Relative rather than absolute, so 10 g of protein and 10 g of fibre aren't
    treated as the same size of mistake.
    """
    total = 0.0
    for key, target in targets.items():
        if not target:
            continue
        diff = running[key] - target
        under, over = PENALTY[key]
        total += (over if diff > 0 else under) * abs(diff) / target
    return total


def _limits(kcal: float) -> tuple[float, int]:
    """
    How many portions of one food, and how many foods, a day of this size holds.

    Fixed caps looked like variety and behaved like a bug. Capped at three
    portions each, a 3000 kcal bulk ran out of carb sources before it ran out of
    carbs — rice, roti and oats all maxed out — so the plan reached for chicken
    to close a calorie gap that rice should have closed, and protein finished 80%
    over target. Five katori of rice in a day is not a modelling failure; it's
    what bulking looks like.
    """
    cap = 3.0 if kcal <= 2200 else (4.0 if kcal <= 2800 else 5.5)
    max_items = 10 if kcal <= 2200 else (12 if kcal <= 2800 else 14)
    return cap, max_items


def _fill(*, targets, running, chosen, diet, budget, avoid,
          cap=MAX_PORTIONS, max_items=14):
    """
    Add one portion at a time, always the portion that improves the plan most.

    Sequential filling — all the protein, then all the carbs — cannot work here,
    and it's worth saying why, because it's the obvious approach and it's wrong.
    Food doesn't sort itself into one macro: two rotis bring 7 g of protein, dal
    brings 28 g of carbs, and a portion of eggs brings 16 g of fat. By the time
    the carb pass finished, an earlier protein target that was exactly met had
    quietly drifted 30% over, and nothing later in the sequence could undo it.

    So instead: score the whole plan against every target at once, try adding a
    single portion of each candidate food, keep whichever scores best, and stop
    when nothing improves it. Each step is still something you can explain in a
    sentence — "add the food that gets us closest" — and because every macro is
    scored on every step, filling one can't silently wreck another.
    """
    pool = [k for k in _candidates(diet) if _usable(k, diet=diet, budget=budget, avoid=avoid)]
    counts: dict[str, float] = {}

    # Half a portion at a time, not a whole one. A portion of chicken breast is
    # 46 g of protein — forcing the plan to move in units that big is most of
    # what kept it from landing on target, and half a chicken breast or half a
    # katori of rice is what a real plate looks like anyway.
    STEP = 0.5

    # Every move is considered on every pass: add half a portion, or take one
    # away. Add-only was not enough, and the failure was instructive. Once the
    # calories landed, every further addition made the calorie error worse, so
    # the loop stopped — and reported a 3000 kcal bulk sitting 80% over on
    # protein and 21% under on carbs, with no way out. The plan didn't need more
    # food, it needed *different* food, and that means being able to put the
    # chicken back down before picking the rice up.
    for _ in range(400):                # generous bound; real plans settle in ~30
        best_move, best_error = None, _error(running, targets)

        for key in pool:
            have = counts.get(key, 0)
            food = foods.BY_KEY[key]

            if have + STEP <= cap and (have > 0 or len(counts) < max_items):
                trial = {k: running[k] + food[k] * STEP for k in running}
                score = _error(trial, targets)
                if score < best_error:
                    best_move, best_error = (key, +STEP), score

            if have > 0:
                trial = {k: running[k] - food[k] * STEP for k in running}
                score = _error(trial, targets)
                if score < best_error:
                    best_move, best_error = (key, -STEP), score

        if best_move is None:           # nothing left that gets us closer
            break

        key, delta = best_move
        food = foods.BY_KEY[key]
        counts[key] = round(counts.get(key, 0) + delta, 1)
        for k in running:
            running[k] += food[k] * delta
        if counts[key] <= 0:
            counts.pop(key)

    chosen.extend(
        {"key": k, "portions": n}
        for k, n in sorted(counts.items(), key=lambda kv: pool.index(kv[0]))
    )


def _candidates(diet: str) -> list[str]:
    """Every food the planner may reach for, staples first."""
    seen, out = set(), []
    for key in PROTEIN_ROTATION[diet] + VEG_ROTATION + CARB_ROTATION + FAT_ROTATION:
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def build_day(*, protein_g, carb_g, fat_g, fibre_g, kcal,
              diet="omnivore", budget="moderate", meals=4,
              dislikes="", allergies="") -> dict:
    """
    Fill the targets with ordinary food, then report honestly how close it landed.

    Order matches the way the macros were built — protein, fibre, carbs, fat —
    and every pass subtracts what earlier passes already contributed.
    """
    diet = diet if diet in PROTEIN_ROTATION else "omnivore"
    avoid = _avoid_set(dislikes, allergies)
    running = {"protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0, "fibre_g": 0.0, "kcal": 0.0}
    targets = {"protein_g": protein_g, "carb_g": carb_g, "fat_g": fat_g,
               "fibre_g": fibre_g, "kcal": kcal}
    chosen: list[dict] = []
    cap, max_items = _limits(kcal)

    _fill(targets=targets, running=running, chosen=chosen,
          diet=diet, budget=budget, avoid=avoid, cap=cap, max_items=max_items)

    items = []
    for c in chosen:
        food = foods.BY_KEY[c["key"]]
        n = c["portions"]
        items.append({
            "key": c["key"],
            "name": food["name"],
            "household": food["household"],
            "portions": n,
            "grams": round(food["grams"] * n),
            "kcal": round(food["kcal"] * n),
            "protein_g": round(food["protein_g"] * n, 1),
            "carb_g": round(food["carb_g"] * n, 1),
            "fat_g": round(food["fat_g"] * n, 1),
            "fibre_g": round(food["fibre_g"] * n, 1),
        })

    def compare(key, actual, target, unit="g"):
        diff = round(actual - target, 1)
        pct = round(diff / target * 100) if target else 0
        under, over = BANDS[key]
        return {
            "planned": round(actual, 1),
            "target": round(target, 1),
            "difference": diff,
            "off_by_pct": pct,
            "close_enough": -under <= pct and (over is None or pct <= over),
            "allowed_under_pct": under,
            "allowed_over_pct": over,
            "unit": unit,
        }

    totals = {
        "kcal": compare("kcal", running["kcal"], kcal, "kcal"),
        "protein_g": compare("protein_g", running["protein_g"], protein_g),
        "carb_g": compare("carb_g", running["carb_g"], carb_g),
        "fat_g": compare("fat_g", running["fat_g"], fat_g),
        "fibre_g": compare("fibre_g", running["fibre_g"], fibre_g),
    }

    return {
        "items": items,
        "meals": _split_into_meals(items, meals),
        "totals": totals,
        "all_close": all(v["close_enough"] for v in totals.values()),
        "check": _diagnose(totals, diet=diet, budget=budget, avoid=avoid),
        "excluded": sorted(avoid),
        "budget": budget,
        "diet": diet,
        "note": (
            "One day, not a prescription, and not the only way to hit these numbers. "
            "Food comes in whole portions, so the totals land near the targets rather "
            "than exactly on them — the gap for each is shown above so you can adjust "
            "rather than guess. Swap any food for another in the same row of the food "
            "list; the macros are what matter, not these particular items."
        ),
    }


def _diagnose(totals: dict, *, diet: str, budget: str, avoid: set[str]) -> list[dict]:
    """
    Say what didn't land, and what to change about it.

    Some targets genuinely cannot be met from the food available. A tight-budget
    eggetarian cut is the honest example: whey and Greek yogurt are the two
    things that add protein without much else attached, both are excluded as
    pricey, and eggs bring 16 g of fat per portion — so past a certain protein
    figure the calories run out first. That's a real constraint, not a bug, and
    the useful response is to name it and offer the lever, not to quietly ship a
    plan that misses and hope nobody totals the column.
    """
    notes = []
    protein, fibre, fat = totals["protein_g"], totals["fibre_g"], totals["fat_g"]

    if not protein["close_enough"] and protein["difference"] < 0:
        short = abs(protein["difference"])
        lever = (
            "the two foods that add protein without much else attached — whey and "
            "Greek yogurt — are excluded because the client said money is tight"
            if budget == "tight" else
            "the highest-protein options for this diet are already in the plan"
        )
        notes.append({
            "level": "warning",
            "what": f"Protein lands {short:g} g short of the {protein['target']:g} g target.",
            "why": (
                f"On a {diet} diet, {lever}. Past this point the remaining sources "
                "bring enough fat or carbs with them that the calorie target runs "
                "out before the protein one is met."
            ),
            "options": [
                "Allow one budget protein — 30 g of whey is about ₹25 and closes most of this gap.",
                f"Accept {protein['planned']:g} g. It's below ideal but still inside the "
                "range that protects muscle in a deficit.",
                "Raise calories, if the goal timeline can take it.",
            ],
        })

    if not protein["close_enough"] and protein["difference"] > 0:
        notes.append({
            "level": "info",
            "what": (
                f"Protein comes to {protein['planned']:g} g against a "
                f"{protein['target']:g} g target."
            ),
            "why": (
                "Not a mistake, and not worth 'fixing'. Rice, roti, dal and milk all "
                "carry protein, so once the calorie target is large relative to the "
                "client's lean mass, the food needed to reach the calories overshoots "
                "the protein number on its own. The alternative would be swapping "
                "staples for pure starch to bring protein down, which would be a "
                "worse plan in every other respect."
            ),
            "options": [
                "Leave it. Extra protein at this level is harmless and mildly helpful for satiety.",
                "If the calorie total is what matters most, trim the highest-protein item by half a portion.",
            ],
        })

    if fibre["planned"] > FIBRE_COMFORT_CEILING_G:
        notes.append({
            "level": "info",
            "what": f"Fibre comes to {fibre['planned']:g} g, which is high.",
            "why": (
                "Not harmful, and it's a side effect of dal, chana and vegetables "
                "doing the protein work on this diet. But going from a low-fibre "
                "diet to this overnight causes bloating and gas, and the client "
                "will blame the plan."
            ),
            "options": [
                "Build up over two weeks rather than starting here.",
                "Make sure water intake goes up with it — fibre without fluid is worse, not better.",
            ],
        })

    if not fat["close_enough"] and fat["difference"] > 0:
        notes.append({
            "level": "info",
            "what": f"Fat runs {fat['difference']:g} g over the {fat['target']:g} g target.",
            "why": (
                "Whole foods carry their own fat — eggs, curd, paneer and nuts all "
                "bring it along with the protein. At 9 kcal per gram it's the "
                "fastest way for a plan to drift over its calories."
            ),
            "options": [
                "Cut the cooking oil first — it's the one fat here with nothing else attached.",
                "Swap whole eggs for part egg whites, or paneer for its low-fat version.",
            ],
        })

    return notes


def _split_into_meals(items: list[dict], meals: int) -> list[dict]:
    """
    Spread the day's food across meals, protein first.

    Protein-led items are dealt out one per meal before anything else, so every
    meal has a protein source. That's not arithmetic — total daily protein is
    what drives the outcome — but it's how the day gets eaten: a meal with no
    protein in it is the one people skip or replace with whatever's nearby.
    """
    meals = max(1, min(8, int(meals or 4)))
    protein_keys = {food["key"] for food in foods.PROTEIN_FOODS}

    # Split everything back into half-portion units before dealing them out.
    # Handing out whole items instead produced meals of 839 and 157 kcal in the
    # same day, because one item can be half the day's food — 2.5 portions of
    # chana has to be allowed to land in two different meals, which is how anyone
    # would actually eat it.
    units = []
    for item in items:
        n = int(round(item["portions"] / 0.5))
        for _ in range(n):
            units.append({
                "key": item["key"], "name": item["name"],
                "household": item["household"], "portions": 0.5,
                "grams": item["grams"] / n, "kcal": item["kcal"] / n,
                "protein_g": item["protein_g"] / n, "carb_g": item["carb_g"] / n,
                "fat_g": item["fat_g"] / n, "fibre_g": item["fibre_g"] / n,
                "is_protein": item["key"] in protein_keys,
            })

    # Protein units first, then the rest, each going to whichever meal is
    # currently lightest. Protein leads so no meal ends up without any — total
    # daily protein is what drives the result, but a meal with none in it is the
    # one that gets skipped or replaced with whatever's to hand.
    units.sort(key=lambda u: (not u["is_protein"], -u["kcal"]))
    buckets: list[list[dict]] = [[] for _ in range(meals)]
    load = [0.0] * meals
    for unit in units:
        i = load.index(min(load))
        buckets[i].append(unit)
        load[i] += unit["kcal"]

    out = []
    for i, bucket in enumerate(buckets, start=1):
        merged: dict[str, dict] = {}
        for u in bucket:
            row = merged.setdefault(u["key"], {
                "key": u["key"], "name": u["name"], "household": u["household"],
                "portions": 0.0, "grams": 0.0, "kcal": 0.0,
                "protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0, "fibre_g": 0.0,
            })
            for field in ("portions", "grams", "kcal", "protein_g", "carb_g", "fat_g", "fibre_g"):
                row[field] += u[field]
        rows = []
        for row in merged.values():
            rows.append({
                **row,
                "grams": round(row["grams"]), "kcal": round(row["kcal"]),
                "protein_g": round(row["protein_g"], 1), "carb_g": round(row["carb_g"], 1),
                "fat_g": round(row["fat_g"], 1), "fibre_g": round(row["fibre_g"], 1),
            })
        out.append({
            "meal": i,
            "label": f"Meal {i}",
            "items": rows,
            "kcal": round(sum(x["kcal"] for x in rows)),
            "protein_g": round(sum(x["protein_g"] for x in rows), 1),
        })
    return out


def plan(inp: dict, *, kcal: float, lbm_kg: float, goal: str,
         dislikes: str = "", allergies: str = "", budget: str = "moderate") -> dict:
    """
    The whole feature: the working, then the food.

    Kept together because they're the same answer to the same question. A coach
    who can only see the plan has to trust it; one who can see the arithmetic
    behind it can check it, correct it, and explain it to the client — which is
    the difference between using a tool and being able to defend it.
    """
    math = macro_math(kcal=kcal, weight_kg=inp["weight_kg"], lbm_kg=lbm_kg, goal=goal)
    day = build_day(
        protein_g=math["steps"][0]["grams"],
        carb_g=math["steps"][2]["grams"],
        fat_g=math["steps"][1]["grams"],
        fibre_g=math["fibre"]["grams"],
        kcal=math["kcal_target"],
        diet=inp.get("diet", "omnivore"),
        budget=budget,
        meals=inp.get("meals", 4),
        dislikes=dislikes,
        allergies=allergies,
    )
    return {"math": math, "day": day}
