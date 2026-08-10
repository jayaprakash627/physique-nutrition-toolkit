"""
safety.py — the guardrails.

A calculator will happily tell a 17-year-old girl to eat 900 kcal and cut to 9%
body fat. This file is what stops that. It runs after every calculation and
returns a list of flags the UI shows prominently — never buried, never in a
collapsed panel.

Design decisions worth knowing:

  * We WARN rather than refuse to compute, in almost every case. Hiding the
    number doesn't remove the intent; it just sends the person to a worse tool
    with no warning attached. The exception is `blocked` flags, where we
    calculate but explicitly decline to present the result as a recommendation.
  * Severity is honest. If everything is a red alert, nothing is.
  * The wording never moralises and never mentions willpower. It says what goes
    wrong physiologically and who to talk to.
  * Nothing here frames a body as a problem. Lower body fat is not "better" and
    the copy never implies it.

Flag shape:
    {
      "level":    "danger" | "warning" | "info"
      "code":     stable id, so the UI can style or test specific flags
      "title":    short headline
      "message":  what's wrong and what goes wrong, in plain words
      "action":   what to do about it
      "blocked":  True when we decline to present this as a recommendation
    }
"""

from __future__ import annotations

from .formulas import SAFE_BODYFAT_FLOOR


def _flag(level: str, code: str, title: str, message: str,
          action: str, blocked: bool = False) -> dict:
    return {
        "level": level, "code": code, "title": title,
        "message": message, "action": action, "blocked": blocked,
    }


# ---------------------------------------------------------------------------
#  Demographic gates — these run before anything else
# ---------------------------------------------------------------------------

def check_demographics(*, age: int, sex: str, pregnant: bool = False,
                       medical_conditions: bool = False) -> list[dict]:
    """
    Age, pregnancy and medical-condition gates.

    Under-18s and pregnancy are the two cases where a generic macro calculator
    is genuinely the wrong tool, not just an imprecise one — requirements are
    different in kind, and getting them wrong affects growth or a pregnancy.
    """
    flags = []

    if age < 18:
        flags.append(_flag(
            "danger", "UNDER_18",
            "Under 18 — this tool isn't built for you",
            "Every formula here is validated on adults. Teenagers are still "
            "growing: energy and protein needs are higher relative to bodyweight, "
            "bone is still being laid down, and calorie restriction during "
            "growth can affect final height and bone density permanently. A "
            "deficit that's fine for a 25-year-old is not fine at 16.",
            "Please work with a paediatrician or a sports dietitian who works "
            "with young athletes. Training hard and eating enough — not "
            "dieting — is what builds a physique at your age.",
            blocked=True,
        ))
    elif age < 20:
        flags.append(_flag(
            "warning", "YOUNG_ADULT",
            "You're still finishing growing",
            "Bone density keeps accumulating into the mid-twenties, and it's "
            "built by eating enough and lifting — not by dieting. Aggressive "
            "cuts in your late teens tend to cost you long-term.",
            "Lean toward the maintain or lean-bulk targets rather than a deep "
            "cut, and keep calcium and vitamin D high.",
        ))

    if age > 65:
        flags.append(_flag(
            "info", "OLDER_ADULT",
            "Over 65 — protein needs are higher, not lower",
            "Muscle becomes harder to build and easier to lose with age "
            "(anabolic resistance), so protein requirements go up rather than "
            "down. Bone and joint health also deserve more weight than these "
            "general equations give them.",
            "Aim for the higher end of the protein range, prioritise resistance "
            "training, and check vitamin D and calcium with your doctor.",
        ))

    if pregnant:
        flags.append(_flag(
            "danger", "PREGNANCY",
            "Pregnancy and breastfeeding need clinical guidance",
            "Energy and micronutrient needs change substantially — folate, iron, "
            "iodine, calcium and B12 in particular — and calorie restriction "
            "during pregnancy can affect the baby's development. None of the "
            "targets in this app apply to you.",
            "Work with your obstetrician and a registered dietitian. Please "
            "don't use the cut targets here.",
            blocked=True,
        ))

    if medical_conditions:
        flags.append(_flag(
            "warning", "MEDICAL_CONDITION",
            "A medical condition changes these numbers",
            "Kidney disease changes safe protein intake. Diabetes changes carb "
            "distribution. Thyroid conditions change energy expenditure. Heart "
            "conditions change sodium targets. None of that is visible to a "
            "formula using your height and weight.",
            "Take these numbers to your doctor or a registered dietitian as a "
            "starting point for a conversation, not as a plan to follow.",
        ))

    return flags


# ---------------------------------------------------------------------------
#  Body-fat targets
# ---------------------------------------------------------------------------

def check_bodyfat_target(*, sex: str, current_bf: float,
                         target_bf: float | None = None) -> list[dict]:
    """
    Is the current or requested body fat below a healthy floor?

    The floors differ by sex and that difference is real, not a courtesy: women
    carry sex-specific fat needed for hormonal function, so their essential
    minimum is meaningfully higher. Presenting one floor for everyone would be
    actively unsafe for half the users.
    """
    flags = []
    floor = SAFE_BODYFAT_FLOOR.get(sex, 8.0)
    essential = 10.0 if sex == "female" else 3.0

    if current_bf < essential:
        flags.append(_flag(
            "danger", "BF_BELOW_ESSENTIAL",
            f"Current estimate is below essential body fat for {sex}s",
            f"At an estimated {current_bf}%, you're below the fat your body needs "
            "for basic function — organ protection, nerve insulation and hormone "
            "production. Either the estimate is wrong (quite likely, since these "
            "methods lose accuracy at the extremes) or this needs medical "
            "attention rather than a diet plan.",
            "Please see a doctor. If you think the estimate is off, re-measure "
            "with a different method before trusting it.",
            blocked=True,
        ))
    elif current_bf < floor:
        flags.append(_flag(
            "warning", "BF_BELOW_FLOOR",
            "Already very lean",
            f"At an estimated {current_bf}% you're below the {floor}% level this "
            "app plans down to for "
            f"{'women' if sex == 'female' else 'men'}. Staying here long-term is "
            "associated with low hormones, poor sleep, low libido, mood "
            "disturbance, weakened immunity and — in women — lost periods, which "
            "carries real bone-density consequences.",
            "Competitive athletes do drop here temporarily for a contest. If "
            "you're not peaking for something in the next few weeks, eating at "
            "maintenance is the better call.",
        ))

    if target_bf is not None:
        if target_bf < essential:
            flags.append(_flag(
                "danger", "TARGET_BELOW_ESSENTIAL",
                "That target is below essential body fat",
                f"A {target_bf}% target is below the minimum your body needs to "
                "function. This app won't plan toward it — not because the maths "
                "is hard, but because there's no version of reaching it that's "
                "safe.",
                "Pick a target at or above the healthy floor "
                f"({floor}% for {'women' if sex == 'female' else 'men'}). If a "
                "number lower than that feels necessary, that's worth talking "
                "through with a professional.",
                blocked=True,
            ))
        elif target_bf < floor:
            flags.append(_flag(
                "warning", "TARGET_BELOW_FLOOR",
                "That's contest-stage lean",
                f"A {target_bf}% target is below the {floor}% healthy floor for "
                f"{'women' if sex == 'female' else 'men'}. It's where physique "
                "competitors go for a single day on stage — and they don't stay "
                "there. Expect hunger, low energy, poor sleep, dropping "
                "hormones, and training performance falling off.",
                "If you're peaking for a show, plan the return to maintenance "
                "before you start the cut. If you're not, aim for the athletic "
                "range instead — you'll look better year-round and feel far "
                "better doing it.",
            ))
        elif target_bf > current_bf:
            flags.append(_flag(
                "info", "TARGET_ABOVE_CURRENT",
                "Your target is above your current estimate",
                f"You're at about {current_bf}% and asked for {target_bf}%. "
                "That's a gaining plan, not a cut — which is completely valid if "
                "you're intentionally building.",
                "Check the lean-bulk targets rather than the cut ones.",
            ))

    return flags


# ---------------------------------------------------------------------------
#  Energy and macro targets
# ---------------------------------------------------------------------------

# Absolute calorie floors. Below these, hitting micronutrient needs from food
# becomes essentially impossible, regardless of bodyweight.
MIN_KCAL = {"male": 1500, "female": 1200}


def check_energy(*, sex: str, kcal_target: float, bmr: float, tdee: float,
                 weight_kg: float, rate_pct_bw: float,
                 goal: str) -> list[dict]:
    """Deficit depth, calorie floors, and eating below BMR."""
    flags = []
    floor = MIN_KCAL.get(sex, 1500)
    deficit_pct = (tdee - kcal_target) / tdee * 100 if tdee else 0

    if kcal_target < floor:
        flags.append(_flag(
            "danger", "BELOW_KCAL_FLOOR",
            f"Below the {floor} kcal floor",
            f"A target of {round(kcal_target)} kcal is under the minimum where "
            "you can realistically meet vitamin, mineral and protein needs from "
            "food. Sustained intakes this low cost muscle and bone, disrupt "
            "hormones and slow your metabolic rate — which makes the next diet "
            "harder, not easier.",
            "Raise calories, or extend the timeline instead of deepening the "
            "deficit. Very-low-calorie diets are a medically supervised "
            "intervention, not a self-directed one.",
            blocked=True,
        ))

    if kcal_target < bmr * 0.95 and goal == "cut":
        flags.append(_flag(
            "warning", "BELOW_BMR",
            "Target is below your estimated BMR",
            f"You'd be eating {round(kcal_target)} kcal against an estimated BMR "
            f"of {round(bmr)} kcal — less than your body uses at complete rest. "
            "It works on paper, but in practice it drives fatigue, muscle loss "
            "and the metabolic adaptation that stalls progress.",
            "Widen the gap with activity rather than by cutting food further — "
            "more steps and a moderate deficit beat a severe one.",
        ))

    # Threshold sits just under 25 on purpose. The "aggressive cut" option is
    # defined as exactly 25% below maintenance, and rounding could otherwise land
    # it at 24.98% and skip the warning — the one option that most needs it.
    if deficit_pct >= 24:
        flags.append(_flag(
            "warning", "AGGRESSIVE_DEFICIT",
            f"That's a {round(deficit_pct)}% deficit",
            "Past about 25% below maintenance, the extra weight lost comes "
            "increasingly from muscle rather than fat, and hunger, fatigue and "
            "irritability rise faster than results do. This is the range where "
            "diets get abandoned.",
            "A 15–20% deficit gets you to the same place with more muscle and a "
            "far better chance of finishing.",
        ))

    if rate_pct_bw > 1.0 and goal == "cut":
        flags.append(_flag(
            "warning", "RATE_TOO_FAST",
            f"Losing {rate_pct_bw}% of bodyweight per week is too fast",
            "The evidence-backed band for keeping muscle while losing fat is "
            "0.5–1.0% of bodyweight per week. Above that, lean-mass loss rises "
            "sharply — you end up smaller rather than leaner.",
            "Slow the rate. Losing 8 kg over 16 weeks and keeping your muscle "
            "beats losing it in 8 weeks and not.",
        ))

    if goal == "bulk" and rate_pct_bw > 0.5:
        flags.append(_flag(
            "info", "BULK_TOO_FAST",
            "That's a fast rate of gain",
            "Muscle accrues at roughly 0.25–0.5% of bodyweight per week at best, "
            "and slower the more trained you are. Gaining faster than that means "
            "the extra is mostly fat.",
            "Trim the surplus. A smaller one for longer gives you more muscle "
            "and a shorter cut afterwards.",
        ))

    return flags


def check_macros(*, macro_block: dict, weight_kg: float,
                 sex: str) -> list[dict]:
    """
    Macro-level guardrails — fat floor, carbs squeezed to nothing, protein
    extremes.
    """
    flags = []
    fat = macro_block["fat"]
    carbs = macro_block["carbs"]
    protein = macro_block["protein"]

    if fat["below_floor"]:
        flags.append(_flag(
            "warning", "FAT_RAISED_TO_FLOOR",
            "Fat was raised to its safe floor",
            f"Your calorie target and goal wanted less fat than the "
            f"{fat['floor_g']} g floor (the higher of 0.5 g/kg bodyweight and "
            f"{fat['floor_pct']}% of calories). Below that, testosterone and "
            "oestrogen production suffer, and absorption of vitamins A, D, E and "
            "K falls off. Fat has been set to the floor and the difference taken "
            "from carbs.",
            "If that leaves carbs too low to train on, the fix is a smaller "
            "deficit — not less fat.",
        ))

    if carbs["impossible"]:
        flags.append(_flag(
            "danger", "CARBS_IMPOSSIBLE",
            "These numbers don't fit together",
            "Your protein and fat minimums alone use up the entire calorie "
            "target, leaving nothing for carbohydrate. That's a sign the calorie "
            "target is too low for your lean mass, not a plan to follow — you "
            "would be training with no fuel at all.",
            "Raise calories. Your lean mass needs more energy than this target "
            "provides.",
            blocked=True,
        ))
    elif carbs["g_per_kg_bw"] < 1.5:
        flags.append(_flag(
            "warning", "CARBS_VERY_LOW",
            f"Carbs are very low at {carbs['g_per_kg_bw']} g/kg",
            "Below roughly 2 g/kg, hard training quality drops noticeably — "
            "you'll lose reps at the same weights, muscles look flat, and "
            "chronically low carbs plus a chronic deficit lowers active thyroid "
            "hormone (T3) and leptin.",
            "Consider a smaller deficit, or shift some fat calories into carbs "
            "on your heaviest training days.",
        ))

    if protein["g_per_kg_bw"] > 3.2:
        flags.append(_flag(
            "info", "PROTEIN_VERY_HIGH",
            f"Protein is high at {protein['g_per_kg_bw']} g/kg bodyweight",
            "Not harmful for healthy kidneys, but past roughly 2.2 g/kg there's "
            "no added muscle benefit — and those calories are displacing training "
            "fuel and hormone support. It also raises your water needs.",
            "Fine to keep if you like the fullness it gives you. If training "
            "feels flat, move some of it into carbs.",
        ))

    return flags


def check_hydration(*, water_ml: int, weight_kg: float) -> list[dict]:
    """Sanity check the fluid target and add the electrolyte caveat."""
    flags = []
    if water_ml > 5000:
        flags.append(_flag(
            "info", "HIGH_WATER",
            "That's a high fluid target",
            "Above about 5 litres a day, replacing electrolytes matters as much "
            "as replacing water. Drinking large volumes of plain water while "
            "sweating heavily can dilute blood sodium (hyponatraemia), which is "
            "rare but genuinely dangerous.",
            "Add electrolytes — a pinch of salt with lemon, coconut water, curd, "
            "or an ORS sachet after long hot sessions. Sip through the day "
            "rather than drinking large volumes at once.",
        ))
    return flags


# ---------------------------------------------------------------------------
#  Prep planner
# ---------------------------------------------------------------------------

def check_prep_plan(*, plan: dict, sex: str) -> list[dict]:
    """Rate and target checks for the goal planner."""
    flags = []

    if plan["risk"] == "danger":
        flags.append(_flag(
            "danger", "PREP_RATE_UNSAFE",
            "This timeline isn't safe",
            f"Reaching that target by your date needs "
            f"{plan['per_week_kg']} kg/week — {plan['per_week_pct_bw']}% of your "
            "bodyweight every week. That is far beyond the 0.5–1.0% band where "
            "muscle is preserved. At this rate you'd lose substantial muscle, "
            "your hormones and training would suffer, and the physique at the end "
            "wouldn't be the one you're picturing.",
            f"At a sustainable rate this takes about "
            f"{plan['weeks_at_safe_rate']} weeks. Moving the date is the fix — "
            "the deadline is the only part of this that's negotiable without "
            "cost.",
            blocked=True,
        ))
    elif plan["risk"] == "caution":
        flags.append(_flag(
            "warning", "PREP_RATE_FAST",
            "This timeline is aggressive",
            f"{plan['per_week_kg']} kg/week is {plan['per_week_pct_bw']}% of your "
            "bodyweight — above the 1.0%/week upper limit for keeping muscle. "
            "It's doable, but expect to give up some lean mass and to feel it in "
            "the gym.",
            f"Giving yourself {plan['weeks_at_safe_rate']} weeks instead would "
            "keep more muscle. If the date is fixed, keep protein at the top of "
            "its range and don't add cardio on top of the deficit.",
        ))

    if plan["target_bf_below_floor"]:
        flags.append(_flag(
            "warning", "PREP_TARGET_LOW",
            "Contest-stage target",
            f"Your goal is below the {plan['floor_for_sex']}% healthy floor for "
            f"{'women' if sex == 'female' else 'men'}. Competitors reach that for "
            "one day and then come back up — it isn't a place to live.",
            "Plan the reverse diet back to maintenance before you start. Prep "
            "without an exit plan is where the rebound happens.",
        ))

    return flags


# ---------------------------------------------------------------------------
#  Assembly
# ---------------------------------------------------------------------------

def summarise(flags: list[dict]) -> dict:
    """
    Collapse all flags into a single verdict the UI can act on.

    `blocked` True means: we ran the numbers, but we are not presenting them as
    a recommendation. The frontend greys the plan and leads with the flags.
    """
    danger = [f for f in flags if f["level"] == "danger"]
    warning = [f for f in flags if f["level"] == "warning"]
    info = [f for f in flags if f["level"] == "info"]
    blocked = any(f.get("blocked") for f in flags)

    if blocked:
        verdict = "This plan isn't safe to follow as calculated."
        level = "danger"
    elif danger:
        verdict = "There are serious issues to address before following this."
        level = "danger"
    elif warning:
        verdict = "Workable, with the cautions below worth reading first."
        level = "warning"
    else:
        verdict = "No safety concerns flagged for these inputs."
        level = "good"

    return {
        "level": level,
        "verdict": verdict,
        "blocked": blocked,
        "counts": {"danger": len(danger), "warning": len(warning), "info": len(info)},
        "flags": danger + warning + info,      # most severe first
    }
