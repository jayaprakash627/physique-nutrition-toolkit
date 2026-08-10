"""
formulas.py — every calculation in one place, and nothing else.

Pure functions: numbers in, numbers out. No database, no FastAPI, no content.
That separation is on purpose — these are the parts that must be *correct*, so
they're kept small enough to check line by line against the published paper, and
testable without starting a server.

Each function's docstring carries the actual equation and the source key from
`knowledge/sources.py`. If you change a coefficient here, you should be able to
point at the paper that says so.

Units, fixed throughout to avoid the classic imperial/metric bug:
    weight  kg
    height  cm
    girths  cm
    skinfolds mm
    energy  kcal
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9

# Energy stored in a kilogram of body fat. The textbook figure is 7700 kcal
# (9 kcal/g × 1000 g × ~0.85 fat fraction of adipose tissue). Real-world weight
# change also involves lean tissue and water, so treat it as a planning estimate.
KCAL_PER_KG_FAT = 7700

# Activity multipliers applied to BMR to reach TDEE. Broad brackets by nature —
# the labels describe total daily life, not just gym time, which is the most
# common way people overestimate here.
ACTIVITY_LEVELS = {
    "sedentary":    {"factor": 1.20, "label": "Sedentary — desk job, little movement, no training"},
    "light":        {"factor": 1.375, "label": "Light — light exercise or sport 1–3 days/week"},
    "moderate":     {"factor": 1.55, "label": "Moderate — training 3–5 days/week"},
    "active":       {"factor": 1.725, "label": "Active — hard training 6–7 days/week"},
    "very_active":  {"factor": 1.90, "label": "Very active — physical job plus hard daily training"},
}

# Body-fat reference bands (ACE/ACSM), separate for men and women because the
# essential minimums genuinely differ: women carry sex-specific fat required for
# hormonal function, so their healthy floor is meaningfully higher.
BODYFAT_BANDS = {
    "male": [
        {"label": "Below essential fat", "min": 0.0, "max": 3.0, "risk": "danger"},
        {"label": "Essential fat", "min": 3.0, "max": 6.0, "risk": "caution"},
        {"label": "Competition lean", "min": 6.0, "max": 10.0, "risk": "caution"},
        {"label": "Athletic", "min": 10.0, "max": 14.0, "risk": "good"},
        {"label": "Fitness", "min": 14.0, "max": 18.0, "risk": "good"},
        {"label": "Average", "min": 18.0, "max": 25.0, "risk": "ok"},
        {"label": "Above average", "min": 25.0, "max": 100.0, "risk": "caution"},
    ],
    "female": [
        {"label": "Below essential fat", "min": 0.0, "max": 10.0, "risk": "danger"},
        {"label": "Essential fat", "min": 10.0, "max": 14.0, "risk": "caution"},
        {"label": "Competition lean", "min": 14.0, "max": 18.0, "risk": "caution"},
        {"label": "Athletic", "min": 18.0, "max": 22.0, "risk": "good"},
        {"label": "Fitness", "min": 22.0, "max": 26.0, "risk": "good"},
        {"label": "Average", "min": 26.0, "max": 32.0, "risk": "ok"},
        {"label": "Above average", "min": 32.0, "max": 100.0, "risk": "caution"},
    ],
}

# The lowest body fat this app will plan toward. Below these, we still show the
# maths but refuse to present it as a recommendation — see safety.py.
SAFE_BODYFAT_FLOOR = {"male": 8.0, "female": 16.0}


# ---------------------------------------------------------------------------
#  BODY FAT — four methods
# ---------------------------------------------------------------------------

def bodyfat_navy(*, sex: str, height_cm: float, neck_cm: float,
                 waist_cm: float, hip_cm: float | None = None) -> float | None:
    """
    U.S. Navy circumference method (Hodgdon & Beckett, 1984). [NAVY_TAPE]

    Men:
        %BF = 495 / (1.0324 − 0.19077·log10(waist − neck)
                            + 0.15456·log10(height)) − 450
    Women:
        %BF = 495 / (1.29579 − 0.35004·log10(waist + hip − neck)
                             + 0.22100·log10(height)) − 450

    All girths in cm. Returns None when inputs are missing or produce a
    non-physical result (e.g. waist ≤ neck, which the log can't take).
    """
    if not all([height_cm, neck_cm, waist_cm]):
        return None
    try:
        if sex == "male":
            girth = waist_cm - neck_cm
            if girth <= 0:
                return None
            bf = 495 / (
                1.0324
                - 0.19077 * math.log10(girth)
                + 0.15456 * math.log10(height_cm)
            ) - 450
        else:
            if not hip_cm:
                return None
            girth = waist_cm + hip_cm - neck_cm
            if girth <= 0:
                return None
            bf = 495 / (
                1.29579
                - 0.35004 * math.log10(girth)
                + 0.22100 * math.log10(height_cm)
            ) - 450
    except (ValueError, ZeroDivisionError):
        return None
    return round(bf, 1) if 1 <= bf <= 70 else None


def _siri(body_density: float) -> float | None:
    """
    Siri equation (1961) — body density to body-fat percent. [SIRI]

        %BF = (495 / Db) − 450

    Assumes fat has a density of 0.9 g/cm³ and lean tissue 1.1 g/cm³ for
    everyone. Those constants vary with age, sex and ethnicity, which is one
    source of skinfold error that better calliper technique cannot fix.
    """
    if not body_density or body_density <= 0:
        return None
    bf = (495 / body_density) - 450
    return round(bf, 1) if 1 <= bf <= 70 else None


def bodyfat_jp3(*, sex: str, age: int, chest: float | None = None,
                abdomen: float | None = None, thigh: float | None = None,
                triceps: float | None = None,
                suprailiac: float | None = None) -> float | None:
    """
    Jackson–Pollock 3-site skinfold. [JACKSON_POLLOCK_M / _W, SIRI]

    Men — chest, abdomen, thigh (Jackson & Pollock 1978):
        Db = 1.10938 − 0.0008267·S + 0.0000016·S² − 0.0002574·age
    Women — triceps, suprailiac, thigh (Jackson, Pollock & Ward 1980):
        Db = 1.099421 − 0.0009929·S + 0.0000023·S² − 0.0001392·age

    S = sum of the three skinfolds in mm. Note the sites differ by sex — this is
    not the same measurement with a different equation.
    """
    if sex == "male":
        sites = [chest, abdomen, thigh]
    else:
        sites = [triceps, suprailiac, thigh]
    if not all(s and s > 0 for s in sites):
        return None

    s = sum(sites)
    if sex == "male":
        db = 1.10938 - 0.0008267 * s + 0.0000016 * s * s - 0.0002574 * age
    else:
        db = 1.099421 - 0.0009929 * s + 0.0000023 * s * s - 0.0001392 * age
    return _siri(db)


def bodyfat_jp7(*, sex: str, age: int, chest: float, midaxillary: float,
                triceps: float, subscapular: float, abdomen: float,
                suprailiac: float, thigh: float) -> float | None:
    """
    Jackson–Pollock 7-site skinfold. [JACKSON_POLLOCK_M / _W, SIRI]

    Men:
        Db = 1.112 − 0.00043499·S + 0.00000055·S² − 0.00028826·age
    Women:
        Db = 1.097 − 0.00046971·S + 0.00000056·S² − 0.00012828·age

    S = sum of all seven sites in mm. Same sites for both sexes here, unlike the
    3-site version.
    """
    sites = [chest, midaxillary, triceps, subscapular, abdomen, suprailiac, thigh]
    if not all(s and s > 0 for s in sites):
        return None

    s = sum(sites)
    if sex == "male":
        db = 1.112 - 0.00043499 * s + 0.00000055 * s * s - 0.00028826 * age
    else:
        db = 1.097 - 0.00046971 * s + 0.00000056 * s * s - 0.00012828 * age
    return _siri(db)


def bodyfat_deurenberg(*, sex: str, age: int, bmi: float) -> float | None:
    """
    Deurenberg et al. (1991) — body fat from BMI. [DEURENBERG]

        %BF = 1.20·BMI + 0.23·age − 10.8·sex − 5.4     (sex: male=1, female=0)

    Included as a contrast, not a recommendation. It can only see height and
    weight, so it reads muscle as fat and over-estimates trained lifters — which
    is exactly the point worth showing a client.
    """
    if not bmi or bmi <= 0:
        return None
    sex_term = 1 if sex == "male" else 0
    bf = 1.20 * bmi + 0.23 * age - 10.8 * sex_term - 5.4
    return round(bf, 1) if 1 <= bf <= 70 else None


def classify_bodyfat(sex: str, bf_pct: float) -> dict:
    """Which reference band does this body-fat percentage fall into?"""
    for band in BODYFAT_BANDS.get(sex, BODYFAT_BANDS["male"]):
        if band["min"] <= bf_pct < band["max"]:
            return band
    return BODYFAT_BANDS[sex][-1]


# ---------------------------------------------------------------------------
#  BODY COMPOSITION
# ---------------------------------------------------------------------------

def bmi(*, weight_kg: float, height_cm: float) -> float:
    """BMI = kg / m². Useful as a population screen, near-useless for lifters."""
    h = height_cm / 100
    return round(weight_kg / (h * h), 1)


def lean_mass(*, weight_kg: float, bf_pct: float) -> float:
    """Fat-free mass in kg — bone, muscle, organs, water. Everything but fat."""
    return round(weight_kg * (1 - bf_pct / 100), 1)


def fat_mass(*, weight_kg: float, bf_pct: float) -> float:
    """Fat mass in kg."""
    return round(weight_kg * bf_pct / 100, 1)


def ffmi(*, lbm_kg: float, height_cm: float) -> dict:
    """
    Fat-Free Mass Index — lean mass scaled to height. [KOURI_FFMI]

        FFMI = FFM(kg) / height(m)²
        Normalised FFMI = FFMI + 6.1 × (1.8 − height in m)

    The normalisation adjusts to a 1.8 m reference height, because taller people
    score lower on raw FFMI at the same visual muscularity. Reported alongside
    the raw value rather than instead of it.
    """
    h = height_cm / 100
    raw = lbm_kg / (h * h)
    normalised = raw + 6.1 * (1.8 - h)
    return {"raw": round(raw, 1), "normalised": round(normalised, 1)}


def ffmi_band(value: float) -> str:
    """Plain-language bracket for an FFMI value. See FFMI_CONTEXT for caveats."""
    if value < 18:
        return "Below average muscularity"
    if value < 20:
        return "Average — untrained to lightly trained"
    if value < 22:
        return "Athletic — visibly trained"
    if value < 24:
        return "Well-trained — years of consistent lifting"
    if value < 25.5:
        return "Exceptional — top end of the drug-free range"
    return "Above the range Kouri et al. observed in drug-free lifters"


def waist_to_height(*, waist_cm: float, height_cm: float) -> dict:
    """
    Waist-to-height ratio. [WHTR]

    A simple central-adiposity screen: keep your waist under half your height.
    Better than BMI at flagging visceral fat, and it needs no equation a client
    can't do in their head.
    """
    ratio = waist_cm / height_cm
    if ratio < 0.40:
        band, risk = "Below the healthy range", "caution"
    elif ratio < 0.50:
        band, risk = "Healthy", "good"
    elif ratio < 0.60:
        band, risk = "Increased risk", "caution"
    else:
        band, risk = "High risk", "danger"
    return {"ratio": round(ratio, 3), "band": band, "risk": risk}


def target_weight_for_bodyfat(*, lbm_kg: float, target_bf_pct: float) -> float:
    """
    What you'd weigh at a goal body fat, assuming you keep all your lean mass.

        target weight = LBM / (1 − target%/100)

    That assumption is the catch, and the UI says so: a slow cut with enough
    protein and hard training gets close to it; a crash diet does not, because
    lean mass goes too.
    """
    if target_bf_pct >= 100:
        return 0.0
    return round(lbm_kg / (1 - target_bf_pct / 100), 1)


# ---------------------------------------------------------------------------
#  ENERGY
# ---------------------------------------------------------------------------

def bmr_mifflin(*, sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    """
    Mifflin–St Jeor (1990). [MIFFLIN]

        Men:   10·kg + 6.25·cm − 5·age + 5
        Women: 10·kg + 6.25·cm − 5·age − 161

    The most accurate general-population BMR equation in validation studies —
    but it uses total bodyweight, so it cannot see body composition.
    """
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return round(base + (5 if sex == "male" else -161))


def bmr_katch_mcardle(*, lbm_kg: float) -> float:
    """
    Katch–McArdle (from fat-free mass). [KATCH_MCARDLE]

        BMR = 370 + 21.6 × LBM(kg)

    No sex term — because once you know someone's lean mass, most of the male/
    female difference in metabolic rate is already accounted for. Preferred for
    trained lifters, whose lean mass sits well above what a bodyweight-only
    equation assumes. Requires a body-fat estimate, so it inherits that error.
    """
    return round(370 + 21.6 * lbm_kg)


def tdee(*, bmr: float, activity: str) -> float:
    """Total Daily Energy Expenditure = BMR × activity factor."""
    factor = ACTIVITY_LEVELS.get(activity, ACTIVITY_LEVELS["moderate"])["factor"]
    return round(bmr * factor)


def energy_targets(*, tdee_kcal: float, weight_kg: float) -> dict:
    """
    Cut / maintain / lean-bulk calorie targets at evidence-backed rates.

    Cut at 20% below maintenance — deep enough to progress visibly, shallow
    enough to keep muscle and stay sane. Lean bulk at 10% above, because muscle
    can only be built so fast and a bigger surplus just adds fat.
    [HELMS_NATURAL, ACSM_ENERGY]
    """
    def rate(delta_kcal: float) -> dict:
        kg_week = delta_kcal * 7 / KCAL_PER_KG_FAT
        return {
            "kg_per_week": round(kg_week, 2),
            "pct_bw_per_week": round(abs(kg_week) / weight_kg * 100, 2),
        }

    cut_kcal = round(tdee_kcal * 0.80)
    bulk_kcal = round(tdee_kcal * 1.10)
    aggressive_kcal = round(tdee_kcal * 0.75)

    return {
        "cut": {"kcal": cut_kcal, "delta": cut_kcal - round(tdee_kcal),
                "pct": 20, **rate(cut_kcal - tdee_kcal)},
        "aggressive_cut": {"kcal": aggressive_kcal, "delta": aggressive_kcal - round(tdee_kcal),
                           "pct": 25, **rate(aggressive_kcal - tdee_kcal)},
        "maintain": {"kcal": round(tdee_kcal), "delta": 0, "pct": 0,
                     "kg_per_week": 0.0, "pct_bw_per_week": 0.0},
        "bulk": {"kcal": bulk_kcal, "delta": bulk_kcal - round(tdee_kcal),
                 "pct": 10, **rate(bulk_kcal - tdee_kcal)},
    }


# ---------------------------------------------------------------------------
#  MACRONUTRIENTS
#
#  The ordering is the whole method: protein from lean mass, fat to its floor,
#  carbs get the remainder. See knowledge/explanations.py for why.
# ---------------------------------------------------------------------------

# Protein in g per kg of LEAN body mass, by goal. Derived from the ISSN's
# 2.3–3.1 g/kg FFM range for lifters in a deficit [ISSN_PROTEIN] and Helms et
# al.'s contest-prep recommendations [HELMS_NATURAL]. Cutting is highest because
# that is when muscle is most at risk.
PROTEIN_PER_KG_LBM = {
    "cut": 2.4,
    "maintain": 2.1,
    "bulk": 2.0,
}

# Fat as a share of total calories, by goal, and the floors below which we refuse
# to plan. [IOM_MACRO, WHO_FATS, HELMS_NATURAL]
FAT_PCT_KCAL = {"cut": 0.25, "maintain": 0.28, "bulk": 0.25}
FAT_FLOOR_PCT_KCAL = 0.20      # 20% of calories
FAT_FLOOR_G_PER_KG = 0.5       # or 0.5 g/kg bodyweight — whichever is higher


def macros(*, kcal: float, weight_kg: float, lbm_kg: float, goal: str) -> dict:
    """
    Build the macro split for one client.

    Three steps, in this order and for these reasons:
      1. Protein from LEAN mass — fat tissue doesn't need feeding.
      2. Fat as a % of calories, then raised to its floor if that % falls short.
         Fat is claimed before carbs because it has a hard biological minimum.
      3. Carbs take whatever calories are left — the widest safe range, so the
         right place to absorb the adjustment.

    Returns grams, kcal and % for each, plus flags the safety layer reads.
    """
    goal = goal if goal in PROTEIN_PER_KG_LBM else "maintain"

    # --- 1. Protein --------------------------------------------------------
    protein_g = round(lbm_kg * PROTEIN_PER_KG_LBM[goal])
    protein_kcal = protein_g * KCAL_PER_G_PROTEIN

    # --- 2. Fat, then floor check -----------------------------------------
    fat_g = round(kcal * FAT_PCT_KCAL[goal] / KCAL_PER_G_FAT)
    floor_from_pct = kcal * FAT_FLOOR_PCT_KCAL / KCAL_PER_G_FAT
    floor_from_bw = weight_kg * FAT_FLOOR_G_PER_KG
    fat_floor_g = round(max(floor_from_pct, floor_from_bw))

    fat_below_floor = fat_g < fat_floor_g
    if fat_below_floor:
        fat_g = fat_floor_g
    fat_kcal = fat_g * KCAL_PER_G_FAT

    # --- 3. Carbs take the remainder --------------------------------------
    carb_g = round((kcal - protein_kcal - fat_kcal) / KCAL_PER_G_CARB)
    # Recompute from the ROUNDED grams, not the exact remainder. The client sees
    # grams, so the calorie figures have to be the ones those grams actually add
    # up to — otherwise a coach totals the column and gets a different number
    # than the header, and stops trusting the tool over a 1 kcal discrepancy.
    carb_kcal = carb_g * KCAL_PER_G_CARB

    # Guard rail: if protein + fat already exceed the calorie target (happens at
    # very low calories with high lean mass), carbs would go negative. Clamp to
    # zero and let safety.py raise it — silently producing "-30 g carbs" would be
    # worse than an explicit flag.
    carbs_impossible = carb_g < 0
    if carbs_impossible:
        carb_g = 0
        carb_kcal = 0

    total_kcal = protein_kcal + fat_kcal + carb_kcal

    def pct(part: float) -> float:
        return round(part / total_kcal * 100) if total_kcal else 0

    return {
        "kcal_target": round(kcal),
        "kcal_from_macros": round(total_kcal),
        "protein": {
            "grams": protein_g,
            "kcal": protein_kcal,
            "pct_kcal": pct(protein_kcal),
            "g_per_kg_bw": round(protein_g / weight_kg, 2),
            "g_per_kg_lbm": round(protein_g / lbm_kg, 2) if lbm_kg else 0,
        },
        "fat": {
            "grams": fat_g,
            "kcal": fat_kcal,
            "pct_kcal": pct(fat_kcal),
            "g_per_kg_bw": round(fat_g / weight_kg, 2),
            "floor_g": fat_floor_g,
            "floor_pct": int(FAT_FLOOR_PCT_KCAL * 100),
            "below_floor": fat_below_floor,
        },
        "carbs": {
            "grams": carb_g,
            "kcal": carb_kcal,
            "pct_kcal": pct(carb_kcal),
            "g_per_kg_bw": round(carb_g / weight_kg, 2),
            "impossible": carbs_impossible,
        },
    }


def meal_split(*, protein_g: int, carb_g: int, fat_g: int,
               meals: int = 4) -> list[dict]:
    """
    Split the daily macros across meals.

    Protein is spread evenly on purpose: muscle protein synthesis responds to
    each dose, so 4 × 40 g beats 160 g in one sitting. [ISSN_PROTEIN]

    Carbs are weighted slightly toward the middle of the day (around training),
    and fat slightly away from it — fat slows digestion, which you don't want
    sitting in your stomach during a session. Rounding is absorbed by the last
    meal so the totals always add up exactly.
    """
    meals = max(1, min(8, meals))

    # Relative carb / fat weights per meal, normalised below. Deliberately gentle
    # — nutrient timing matters far less than daily totals.
    if meals >= 3:
        carb_w = [1.0] * meals
        fat_w = [1.0] * meals
        mid = meals // 2
        carb_w[mid] = 1.35                    # meal around training
        fat_w[mid] = 0.65
        carb_w[-1] = 0.85
        fat_w[-1] = 1.35                      # more fat in the last meal
    else:
        carb_w = [1.0] * meals
        fat_w = [1.0] * meals

    carb_total_w, fat_total_w = sum(carb_w), sum(fat_w)
    labels = _meal_labels(meals)

    out, p_used, c_used, f_used = [], 0, 0, 0
    for i in range(meals):
        last = i == meals - 1
        if last:
            p, c, f = protein_g - p_used, carb_g - c_used, fat_g - f_used
        else:
            p = round(protein_g / meals)
            c = round(carb_g * carb_w[i] / carb_total_w)
            f = round(fat_g * fat_w[i] / fat_total_w)
            p_used, c_used, f_used = p_used + p, c_used + c, f_used + f
        out.append({
            "meal": labels[i],
            "protein_g": max(0, p),
            "carb_g": max(0, c),
            "fat_g": max(0, f),
            "kcal": max(0, p) * 4 + max(0, c) * 4 + max(0, f) * 9,
        })
    return out


def _meal_labels(meals: int) -> list[str]:
    """Meal names that read like a real Indian day rather than 'Meal 1..N'."""
    presets = {
        1: ["Single meal"],
        2: ["Lunch", "Dinner"],
        3: ["Breakfast", "Lunch", "Dinner"],
        4: ["Breakfast", "Lunch", "Post-workout / snack", "Dinner"],
        5: ["Breakfast", "Mid-morning", "Lunch", "Post-workout", "Dinner"],
        6: ["Breakfast", "Mid-morning", "Lunch", "Evening snack", "Post-workout", "Dinner"],
    }
    if meals in presets:
        return presets[meals]
    return [f"Meal {i + 1}" for i in range(meals)]


# ---------------------------------------------------------------------------
#  FIBRE & WATER
# ---------------------------------------------------------------------------

FIBRE_G_PER_1000_KCAL = 14      # [IOM_MACRO]
FIBRE_MIN_G = 25                # WHO floor for adults [WHO_FIBRE]
FIBRE_MAX_TARGET_G = 45         # above this, gut tolerance becomes the limit


def fibre_target(*, kcal: float) -> dict:
    """
    Fibre from calorie intake: 14 g per 1000 kcal. [IOM_MACRO, WHO_FIBRE]

    Scaled to intake rather than fixed, because fibre needs track how much food
    is actually moving through you. Clamped to the 25–45 g range so a very small
    or very large intake doesn't produce a silly target.
    """
    raw = kcal / 1000 * FIBRE_G_PER_1000_KCAL
    target = max(FIBRE_MIN_G, min(FIBRE_MAX_TARGET_G, round(raw)))
    return {
        "grams": target,
        "unclamped": round(raw),
        "per_1000_kcal": FIBRE_G_PER_1000_KCAL,
        "kcal": round(kcal),
        "clamped": target != round(raw),
    }


WATER_ML_PER_KG = 35            # athlete-facing end of the 30–35 ml/kg range
WATER_ML_PER_TRAINING_HOUR = 600  # midpoint of ACSM's 500–750 ml/h [ACSM_HYDRATION]
CLIMATE_EXTRA_ML = {
    "temperate": 0,
    "warm": 300,
    "hot": 600,
    "very_hot": 900,
}


def water_target(*, weight_kg: float, training_hours: float,
                 climate: str, protein_g: float) -> dict:
    """
    Daily fluid target, built from four additive parts. [EFSA_WATER, ACSM_HYDRATION]

        baseline  35 ml/kg bodyweight
        training  +600 ml per hour of training
        climate   +0 to 900 ml (Indian summer sits at 'hot' or 'very_hot')
        protein   +250 ml if protein is above 2 g/kg — clearing nitrogen through
                  the kidneys costs fluid

    This is TOTAL fluid: food contributes roughly 20–30% of it (dal, curd, fruit,
    sabzi, chai all count), which the UI states so nobody tries to drink 5 L of
    plain water.
    """
    baseline = round(weight_kg * WATER_ML_PER_KG)
    training = round(training_hours * WATER_ML_PER_TRAINING_HOUR)
    climate_ml = CLIMATE_EXTRA_ML.get(climate, 0)
    protein_ml = 250 if protein_g / max(weight_kg, 1) > 2.0 else 0

    total = baseline + training + climate_ml + protein_ml
    return {
        "total_ml": total,
        "total_l": round(total / 1000, 1),
        "baseline_ml": baseline,
        "training_ml": training,
        "climate_ml": climate_ml,
        "protein_ml": protein_ml,
        "per_kg": WATER_ML_PER_KG,
        "from_food_ml": round(total * 0.25),
        "from_drinks_ml": round(total * 0.75),
    }


# ---------------------------------------------------------------------------
#  GOAL / CONTEST PREP PLANNER
# ---------------------------------------------------------------------------

def prep_plan(*, weight_kg: float, current_bf: float, target_bf: float,
              weeks: int, sex: str) -> dict:
    """
    Week-by-week projection from current body fat to a goal by a deadline.

    The honest version of contest prep maths. We hold lean mass constant — the
    best case, achievable with a moderate deficit, enough protein and hard
    training — then work out the weekly rate required and check it against the
    0.5–1.0% bodyweight/week safe band. [HELMS_NATURAL]

    If the required rate is unsafe we still show the projection, but we also
    compute how many weeks it would actually take at a safe rate, so the client
    can see the real choice: move the date, or accept muscle loss.
    """
    weeks = max(1, min(104, weeks))
    lbm = lean_mass(weight_kg=weight_kg, bf_pct=current_bf)
    goal_weight = target_weight_for_bodyfat(lbm_kg=lbm, target_bf_pct=target_bf)
    total_change = weight_kg - goal_weight

    per_week_kg = total_change / weeks
    per_week_pct = abs(per_week_kg) / weight_kg * 100

    # Weeks needed at a sustainable 0.75%/week — the middle of the safe band.
    safe_rate_kg = weight_kg * 0.0075
    weeks_at_safe_rate = (
        math.ceil(abs(total_change) / safe_rate_kg) if safe_rate_kg > 0 else 0
    )

    direction = "loss" if total_change > 0 else "gain"

    # Build the week-by-week table. Lean mass held constant, so all change is fat.
    projection = []
    for w in range(weeks + 1):
        wt = weight_kg - per_week_kg * w
        fat_kg = max(0.0, wt - lbm)
        bf = (fat_kg / wt * 100) if wt > 0 else 0
        projection.append({
            "week": w,
            "weight_kg": round(wt, 1),
            "bodyfat_pct": round(bf, 1),
            "fat_mass_kg": round(fat_kg, 1),
            "lean_mass_kg": round(lbm, 1),
        })

    # Verdict on the rate.
    if direction == "loss":
        if per_week_pct <= 0.5:
            verdict, risk = "Comfortable", "good"
        elif per_week_pct <= 1.0:
            verdict, risk = "Achievable but demanding", "ok"
        elif per_week_pct <= 1.5:
            verdict, risk = "Too fast — expect muscle loss", "caution"
        else:
            verdict, risk = "Unsafe", "danger"
    else:
        if per_week_pct <= 0.5:
            verdict, risk = "Reasonable lean-gain rate", "good"
        else:
            verdict, risk = "Faster than muscle can be built — mostly fat gain", "caution"

    return {
        "direction": direction,
        "current_weight_kg": round(weight_kg, 1),
        "goal_weight_kg": goal_weight,
        "lean_mass_kg": round(lbm, 1),
        "total_change_kg": round(abs(total_change), 1),
        "weeks": weeks,
        "per_week_kg": round(abs(per_week_kg), 2),
        "per_week_pct_bw": round(per_week_pct, 2),
        "weeks_at_safe_rate": weeks_at_safe_rate,
        "safe_rate_kg_per_week": round(safe_rate_kg, 2),
        "verdict": verdict,
        "risk": risk,
        "target_bf_below_floor": target_bf < SAFE_BODYFAT_FLOOR.get(sex, 8.0),
        "floor_for_sex": SAFE_BODYFAT_FLOOR.get(sex, 8.0),
        "projection": projection,
        # Daily deficit implied by the requested rate — useful sanity check
        # against the calorie targets elsewhere in the report.
        "implied_daily_kcal_delta": round(abs(per_week_kg) * KCAL_PER_KG_FAT / 7),
    }


# ---------------------------------------------------------------------------
#  STRENGTH
# ---------------------------------------------------------------------------

def one_rep_max(*, weight: float, reps: int) -> dict:
    """
    Estimate a 1RM from a set taken close to failure.

    Epley:   1RM = w × (1 + reps/30)          [EPLEY]
    Brzycki: 1RM = w × 36 / (37 − reps)       [BRZYCKI]

    Both are shown because they disagree in a useful way, and the disagreement
    flips: the two are identical at exactly 10 reps (both give w × 1.333). Below
    10 reps Epley returns the higher estimate; above 10 reps Brzycki does. So the
    pair brackets the true value from either side depending on the rep range.

    Accuracy falls off above ~10 reps either way — a 20-rep set says more about
    conditioning than maximal strength.
    """
    reps = max(1, min(20, reps))
    epley = weight * (1 + reps / 30)
    brzycki = weight * 36 / (37 - reps) if reps < 37 else weight
    avg = (epley + brzycki) / 2
    return {
        "epley": round(epley, 1),
        "brzycki": round(brzycki, 1),
        "average": round(avg, 1),
        "reps": reps,
        "weight": weight,
        "confidence": "high" if reps <= 5 else ("moderate" if reps <= 10 else "low"),
    }


# Percentage-of-1RM training table. Rep figures are typical trained-lifter
# expectations, not guarantees — they vary by exercise and by individual.
PCT_1RM_TABLE = [
    {"pct": 100, "reps": "1",     "use": "Max attempt / competition single"},
    {"pct": 95,  "reps": "2",     "use": "Peaking work, very heavy doubles"},
    {"pct": 90,  "reps": "3–4",   "use": "Strength — low reps, long rest"},
    {"pct": 85,  "reps": "5–6",   "use": "Strength, the classic 5×5 zone"},
    {"pct": 80,  "reps": "7–8",   "use": "Strength / hypertrophy overlap"},
    {"pct": 75,  "reps": "9–10",  "use": "Hypertrophy — the money zone for size"},
    {"pct": 70,  "reps": "11–12", "use": "Hypertrophy, higher volume"},
    {"pct": 65,  "reps": "13–15", "use": "Volume and technique work"},
    {"pct": 60,  "reps": "16–20", "use": "Muscular endurance, warm-up sets"},
    {"pct": 50,  "reps": "20+",   "use": "Warm-ups, deloads, technique practice"},
]


def pct_table(one_rm: float) -> list[dict]:
    """Turn a 1RM into a loading table, rounded to the nearest 2.5 kg plate."""
    out = []
    for row in PCT_1RM_TABLE:
        raw = one_rm * row["pct"] / 100
        out.append({**row, "weight": round(raw * 2) / 2, "plate_rounded": round(raw / 2.5) * 2.5})
    return out


# DOTS coefficients. [IPF_DOTS]
_DOTS_COEF = {
    "male":   (-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -0.000001093),
    "female": (-57.96288, 13.6175032, -0.1126655495, 0.0005158568, -0.0000010706),
}

# Original Wilks coefficients. [WILKS]
_WILKS_COEF = {
    "male":   (-216.0475144, 16.2606339, -0.002388645, -0.00113732, 7.01863e-06, -1.291e-08),
    "female": (594.31747775582, -27.23842536447, 0.82112226871, -0.00930733913,
               4.731582e-05, -9.054e-08),
}


def dots_score(*, sex: str, bodyweight_kg: float, total_kg: float) -> float | None:
    """
    DOTS score — a total normalised for bodyweight. [IPF_DOTS]

        coefficient = 500 / (a + b·bw + c·bw² + d·bw³ + e·bw⁴)
        DOTS = total × coefficient

    Lets a 66 kg lifter and a 105 kg lifter compare fairly. Bodyweight is
    clamped to the range the polynomial was fitted over, since it misbehaves
    outside it.
    """
    coef = _DOTS_COEF.get(sex)
    if not coef or bodyweight_kg <= 0 or total_kg <= 0:
        return None
    bw = max(40.0, min(210.0 if sex == "male" else 150.0, bodyweight_kg))
    a, b, c, d, e = coef
    denom = a + b * bw + c * bw**2 + d * bw**3 + e * bw**4
    if denom <= 0:
        return None
    return round(total_kg * 500 / denom, 2)


def wilks_score(*, sex: str, bodyweight_kg: float, total_kg: float) -> float | None:
    """
    Wilks coefficient (1994). [WILKS]

        coefficient = 500 / (a + bx + cx² + dx³ + ex⁴ + fx⁵)
        Wilks = total × coefficient

    Superseded by DOTS in most federations, but included because virtually every
    historical meet result is recorded in Wilks.
    """
    coef = _WILKS_COEF.get(sex)
    if not coef or bodyweight_kg <= 0 or total_kg <= 0:
        return None
    x = max(40.0, min(200.0, bodyweight_kg))
    a, b, c, d, e, f = coef
    denom = a + b * x + c * x**2 + d * x**3 + e * x**4 + f * x**5
    if denom <= 0:
        return None
    return round(total_kg * 500 / denom, 2)


def strength_band(dots: float | None) -> str:
    """Rough DOTS brackets, for context rather than judgement."""
    if dots is None:
        return "—"
    if dots < 200:
        return "Novice"
    if dots < 300:
        return "Intermediate"
    if dots < 400:
        return "Advanced"
    if dots < 500:
        return "Elite"
    return "World class"
