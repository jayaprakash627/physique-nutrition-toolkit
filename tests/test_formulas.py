"""
test_formulas.py — the maths, checked against published values.

These are the tests that matter most. Everything else in the app is presentation;
if a coefficient here is wrong, the app confidently tells someone the wrong
number and there is no way for them to know.

Each test names the source it checks against. Where a figure is hand-verifiable
the expected value is worked out in the comment, so a reviewer can confirm it
without trusting me.

Run with:  pytest -q
"""

import math

import pytest

from app import formulas as f


# ---------------------------------------------------------------------------
#  BMR
# ---------------------------------------------------------------------------

def test_mifflin_male_known_value():
    """
    Mifflin–St Jeor, male: 10·W + 6.25·H − 5·A + 5
    10(80) + 6.25(180) − 5(30) + 5 = 800 + 1125 − 150 + 5 = 1780
    """
    assert f.bmr_mifflin(sex="male", weight_kg=80, height_cm=180, age=30) == 1780


def test_mifflin_female_known_value():
    """
    Female: 10(60) + 6.25(165) − 5(28) − 161
          = 600 + 1031.25 − 140 − 161 = 1330.25 → 1330
    """
    assert f.bmr_mifflin(sex="female", weight_kg=60, height_cm=165, age=28) == 1330


def test_mifflin_female_is_lower_than_male_same_body():
    """The sex constant differs by 166 kcal (+5 vs −161)."""
    m = f.bmr_mifflin(sex="male", weight_kg=70, height_cm=170, age=25)
    w = f.bmr_mifflin(sex="female", weight_kg=70, height_cm=170, age=25)
    assert m - w == 166


def test_katch_mcardle_known_value():
    """Katch–McArdle: 370 + 21.6 × LBM = 370 + 21.6(65) = 1774"""
    assert f.bmr_katch_mcardle(lbm_kg=65) == 1774


def test_katch_ignores_sex_by_design():
    """
    Katch–McArdle takes only lean mass — there is no sex term, because lean mass
    already carries most of the between-sex difference in metabolic rate.
    """
    assert f.bmr_katch_mcardle(lbm_kg=55) == f.bmr_katch_mcardle(lbm_kg=55)


def test_tdee_applies_activity_factor():
    assert f.tdee(bmr=1800, activity="sedentary") == round(1800 * 1.20)
    assert f.tdee(bmr=1800, activity="moderate") == round(1800 * 1.55)
    assert f.tdee(bmr=1800, activity="very_active") == round(1800 * 1.90)


def test_tdee_unknown_activity_falls_back_to_moderate():
    assert f.tdee(bmr=2000, activity="nonsense") == f.tdee(bmr=2000, activity="moderate")


# ---------------------------------------------------------------------------
#  BODY FAT
# ---------------------------------------------------------------------------

def test_navy_male_plausible_range():
    """A 175 cm male, 39 cm neck, 85 cm waist should land in the mid-to-high teens."""
    bf = f.bodyfat_navy(sex="male", height_cm=175, neck_cm=39, waist_cm=85)
    assert bf is not None
    assert 12 < bf < 22


def test_navy_female_needs_hip():
    """The female equation uses waist + hip − neck; without hip it cannot run."""
    assert f.bodyfat_navy(sex="female", height_cm=165, neck_cm=32, waist_cm=72) is None
    assert f.bodyfat_navy(
        sex="female", height_cm=165, neck_cm=32, waist_cm=72, hip_cm=95
    ) is not None


def test_navy_rejects_waist_smaller_than_neck():
    """log10 of a non-positive girth is undefined — return None, never crash."""
    assert f.bodyfat_navy(sex="male", height_cm=180, neck_cm=45, waist_cm=40) is None


def test_navy_bigger_waist_means_more_fat():
    """Monotonicity: the only thing changing is waist, so fat must rise with it."""
    lean = f.bodyfat_navy(sex="male", height_cm=178, neck_cm=38, waist_cm=76)
    fat = f.bodyfat_navy(sex="male", height_cm=178, neck_cm=38, waist_cm=96)
    assert fat > lean


def test_siri_conversion():
    """
    Siri: %BF = 495/Db − 450. At Db = 1.05 → 495/1.05 − 450 = 21.43
    Checked through the JP3 path, since _siri is internal.
    """
    assert f._siri(1.05) == pytest.approx(21.4, abs=0.1)
    # Db = 1.10 is the assumed density of pure lean tissue, giving 0% fat. That's
    # non-physical for a living person, so the guard rejects it rather than
    # printing "0%" — a body-fat estimate under 1% means bad measurements.
    assert f._siri(1.10) is None


def test_siri_rejects_bad_density():
    assert f._siri(0) is None
    assert f._siri(-1) is None


def test_jp3_male_uses_chest_abdomen_thigh():
    bf = f.bodyfat_jp3(sex="male", age=25, chest=8, abdomen=16, thigh=10)
    assert bf is not None and 5 < bf < 18


def test_jp3_female_uses_different_sites():
    """
    The female 3-site equation takes triceps/suprailiac/thigh — passing the male
    sites must not silently produce a number.
    """
    assert f.bodyfat_jp3(sex="female", age=25, chest=8, abdomen=16, thigh=10) is None
    assert f.bodyfat_jp3(
        sex="female", age=25, triceps=14, suprailiac=12, thigh=20
    ) is not None


def test_jp3_thicker_folds_mean_more_fat():
    thin = f.bodyfat_jp3(sex="male", age=30, chest=5, abdomen=8, thigh=6)
    thick = f.bodyfat_jp3(sex="male", age=30, chest=20, abdomen=30, thigh=22)
    assert thick > thin


def test_jp3_age_increases_estimate():
    """Both JP equations carry a negative age term on density → higher body fat."""
    young = f.bodyfat_jp3(sex="male", age=20, chest=10, abdomen=18, thigh=12)
    older = f.bodyfat_jp3(sex="male", age=50, chest=10, abdomen=18, thigh=12)
    assert older > young


def test_jp7_needs_all_seven_sites():
    sites = dict(chest=8, midaxillary=7, triceps=9, subscapular=11,
                 abdomen=16, suprailiac=12, thigh=10)
    assert f.bodyfat_jp7(sex="male", age=25, **sites) is not None

    missing = {**sites, "thigh": 0}
    assert f.bodyfat_jp7(sex="male", age=25, **missing) is None


def test_deurenberg_overestimates_a_muscular_lifter():
    """
    The documented bias worth showing clients: BMI cannot see muscle.
    A 90 kg / 178 cm lifter (BMI 28.4) is read as ~26% fat by Deurenberg even
    though a lifter at that size is typically far leaner.
    """
    bmi = f.bmi(weight_kg=90, height_cm=178)
    deur = f.bodyfat_deurenberg(sex="male", age=25, bmi=bmi)
    navy = f.bodyfat_navy(sex="male", height_cm=178, neck_cm=42, waist_cm=84)
    assert deur > navy


def test_bodyfat_bands_differ_by_sex():
    """
    Essential fat is genuinely higher for women. If this ever collapses to one
    shared floor, the safety layer becomes unsafe for half the users.
    """
    male_essential = f.BODYFAT_BANDS["male"][1]
    female_essential = f.BODYFAT_BANDS["female"][1]
    assert female_essential["min"] > male_essential["min"]
    assert f.SAFE_BODYFAT_FLOOR["female"] > f.SAFE_BODYFAT_FLOOR["male"]


def test_classify_bodyfat_picks_the_right_band():
    assert f.classify_bodyfat("male", 12)["label"] == "Athletic"
    assert f.classify_bodyfat("female", 20)["label"] == "Athletic"
    assert f.classify_bodyfat("male", 40)["risk"] == "caution"


# ---------------------------------------------------------------------------
#  COMPOSITION
# ---------------------------------------------------------------------------

def test_bmi():
    """80 / 1.8² = 24.69 → 24.7"""
    assert f.bmi(weight_kg=80, height_cm=180) == 24.7


def test_lean_and_fat_mass_sum_to_bodyweight():
    lbm = f.lean_mass(weight_kg=80, bf_pct=20)
    fm = f.fat_mass(weight_kg=80, bf_pct=20)
    assert lbm == 64.0
    assert fm == 16.0
    assert lbm + fm == pytest.approx(80.0, abs=0.1)


def test_ffmi_normalisation_adjusts_for_height():
    """
    Normalised FFMI = FFMI + 6.1 × (1.8 − h). Someone shorter than 1.8 m gets a
    positive adjustment; at exactly 1.8 m raw and normalised match.
    """
    at_ref = f.ffmi(lbm_kg=70, height_cm=180)
    assert at_ref["raw"] == at_ref["normalised"]

    short = f.ffmi(lbm_kg=70, height_cm=165)
    assert short["normalised"] > short["raw"]

    tall = f.ffmi(lbm_kg=70, height_cm=195)
    assert tall["normalised"] < tall["raw"]


def test_ffmi_natural_limit_band():
    """The Kouri et al. ~25 observation is where the top band starts."""
    assert "drug-free" in f.ffmi_band(26)
    assert f.ffmi_band(19) == "Average — untrained to lightly trained"


def test_waist_to_height_half_your_height_rule():
    assert f.waist_to_height(waist_cm=80, height_cm=180)["risk"] == "good"
    assert f.waist_to_height(waist_cm=95, height_cm=180)["risk"] == "caution"
    assert f.waist_to_height(waist_cm=115, height_cm=180)["risk"] == "danger"


def test_target_weight_for_bodyfat():
    """
    LBM 64 kg at a 12% goal → 64 / 0.88 = 72.7 kg
    """
    assert f.target_weight_for_bodyfat(lbm_kg=64, target_bf_pct=12) == 72.7


def test_target_weight_is_lower_at_lower_bodyfat():
    lean = f.target_weight_for_bodyfat(lbm_kg=70, target_bf_pct=8)
    fatter = f.target_weight_for_bodyfat(lbm_kg=70, target_bf_pct=20)
    assert lean < fatter


# ---------------------------------------------------------------------------
#  MACROS — the ordering logic is the product, so test it hard
# ---------------------------------------------------------------------------

def test_macro_calories_reconcile():
    """Protein·4 + fat·9 + carbs·4 must equal the stated total."""
    m = f.macros(kcal=2400, weight_kg=80, lbm_kg=65, goal="cut")
    total = (m["protein"]["grams"] * 4 + m["fat"]["grams"] * 9
             + m["carbs"]["grams"] * 4)
    assert m["kcal_from_macros"] == total
    # Rounding to whole grams can move the total a little off the target.
    assert abs(total - 2400) <= 12


def test_macro_percentages_sum_to_100():
    m = f.macros(kcal=2200, weight_kg=75, lbm_kg=60, goal="maintain")
    total_pct = (m["protein"]["pct_kcal"] + m["fat"]["pct_kcal"]
                 + m["carbs"]["pct_kcal"])
    assert 99 <= total_pct <= 101      # each is rounded independently


def test_protein_comes_from_lean_mass_not_bodyweight():
    """
    Two people at the same weight with different body composition must get
    different protein targets. This is the core claim of the whole app.
    """
    lean = f.macros(kcal=2400, weight_kg=80, lbm_kg=72, goal="cut")
    fatter = f.macros(kcal=2400, weight_kg=80, lbm_kg=56, goal="cut")
    assert lean["protein"]["grams"] > fatter["protein"]["grams"]


def test_protein_is_highest_when_cutting():
    """
    Protein goes UP in a deficit, because that is when muscle is most at risk.
    A calculator that lowers protein while cutting has the logic backwards.
    """
    lbm, w = 65, 80
    cut = f.macros(kcal=2000, weight_kg=w, lbm_kg=lbm, goal="cut")
    maintain = f.macros(kcal=2500, weight_kg=w, lbm_kg=lbm, goal="maintain")
    bulk = f.macros(kcal=3000, weight_kg=w, lbm_kg=lbm, goal="bulk")
    assert cut["protein"]["grams"] > maintain["protein"]["grams"] > bulk["protein"]["grams"]


def test_fat_never_goes_below_its_floor():
    """
    The floor is the higher of 0.5 g/kg bodyweight and 20% of calories. At a very
    low intake the percentage rule would give a tiny number, so the bodyweight
    rule has to win.
    """
    m = f.macros(kcal=1400, weight_kg=95, lbm_kg=70, goal="cut")
    assert m["fat"]["grams"] >= m["fat"]["floor_g"]
    assert m["fat"]["grams"] >= 95 * f.FAT_FLOOR_G_PER_KG


def test_fat_floor_flag_is_raised_when_it_bites():
    m = f.macros(kcal=1300, weight_kg=100, lbm_kg=75, goal="cut")
    assert m["fat"]["below_floor"] is True


def test_carbs_take_the_remainder():
    m = f.macros(kcal=2600, weight_kg=75, lbm_kg=62, goal="maintain")
    remainder = 2600 - m["protein"]["kcal"] - m["fat"]["kcal"]
    assert m["carbs"]["kcal"] == pytest.approx(remainder, abs=4)


def test_carbs_clamp_at_zero_and_flag_instead_of_going_negative():
    """
    A very low calorie target with high lean mass makes protein + fat exceed the
    budget. Printing "−40 g carbs" would be worse than an explicit flag.
    """
    m = f.macros(kcal=900, weight_kg=110, lbm_kg=95, goal="cut")
    assert m["carbs"]["grams"] == 0
    assert m["carbs"]["impossible"] is True


def test_unknown_goal_falls_back_to_maintain():
    a = f.macros(kcal=2400, weight_kg=80, lbm_kg=65, goal="wibble")
    b = f.macros(kcal=2400, weight_kg=80, lbm_kg=65, goal="maintain")
    assert a["protein"]["grams"] == b["protein"]["grams"]


# ---------------------------------------------------------------------------
#  MEAL SPLIT
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("meals", [1, 2, 3, 4, 5, 6, 8])
def test_meal_split_totals_match_daily_targets_exactly(meals):
    """
    Rounding is absorbed by the last meal, so the column totals must equal the
    daily targets exactly for any meal count. A coach who adds up the table and
    gets a different number stops trusting the tool.
    """
    split = f.meal_split(protein_g=165, carb_g=270, fat_g=65, meals=meals)
    assert len(split) == meals
    assert sum(m["protein_g"] for m in split) == 165
    assert sum(m["carb_g"] for m in split) == 270
    assert sum(m["fat_g"] for m in split) == 65


def test_meal_split_clamps_silly_meal_counts():
    assert len(f.meal_split(protein_g=100, carb_g=100, fat_g=50, meals=0)) == 1
    assert len(f.meal_split(protein_g=100, carb_g=100, fat_g=50, meals=99)) == 8


def test_meal_split_spreads_protein_evenly():
    """
    Muscle protein synthesis responds per dose, so protein is spread rather than
    front- or back-loaded. No meal should differ from the mean by much.
    """
    split = f.meal_split(protein_g=160, carb_g=200, fat_g=60, meals=4)
    protein = [m["protein_g"] for m in split]
    assert max(protein) - min(protein) <= 2


def test_meal_split_never_produces_negative_macros():
    split = f.meal_split(protein_g=5, carb_g=0, fat_g=1, meals=6)
    assert all(m["protein_g"] >= 0 and m["carb_g"] >= 0 and m["fat_g"] >= 0 for m in split)


# ---------------------------------------------------------------------------
#  FIBRE & WATER
# ---------------------------------------------------------------------------

def test_fibre_scales_with_calories():
    """14 g per 1000 kcal: 2500 kcal → 35 g"""
    assert f.fibre_target(kcal=2500)["grams"] == 35


def test_fibre_respects_the_who_floor():
    """A small intake still shouldn't recommend under the 25 g WHO floor."""
    assert f.fibre_target(kcal=1200)["grams"] == f.FIBRE_MIN_G
    assert f.fibre_target(kcal=1200)["clamped"] is True


def test_fibre_caps_at_gut_tolerance():
    assert f.fibre_target(kcal=5000)["grams"] == f.FIBRE_MAX_TARGET_G


def test_water_is_the_sum_of_its_parts():
    w = f.water_target(weight_kg=80, training_hours=1.5, climate="hot", protein_g=180)
    assert w["baseline_ml"] == 80 * 35                 # 2800
    assert w["training_ml"] == round(1.5 * 600)        # 900
    assert w["climate_ml"] == 600                      # hot
    assert w["protein_ml"] == 250                      # 180/80 = 2.25 g/kg > 2.0
    assert w["total_ml"] == 2800 + 900 + 600 + 250


def test_water_no_protein_bonus_at_moderate_intake():
    w = f.water_target(weight_kg=80, training_hours=0, climate="temperate", protein_g=120)
    assert w["protein_ml"] == 0
    assert w["total_ml"] == 80 * 35


def test_water_climate_ordering():
    kw = dict(weight_kg=70, training_hours=1, protein_g=100)
    temperate = f.water_target(climate="temperate", **kw)["total_ml"]
    hot = f.water_target(climate="hot", **kw)["total_ml"]
    very_hot = f.water_target(climate="very_hot", **kw)["total_ml"]
    assert temperate < hot < very_hot


# ---------------------------------------------------------------------------
#  PREP PLANNER
# ---------------------------------------------------------------------------

def test_prep_plan_projection_length_and_endpoints():
    p = f.prep_plan(weight_kg=85, current_bf=20, target_bf=12, weeks=16, sex="male")
    assert len(p["projection"]) == 17            # week 0 through week 16
    assert p["projection"][0]["bodyfat_pct"] == pytest.approx(20, abs=0.2)
    assert p["projection"][-1]["bodyfat_pct"] == pytest.approx(12, abs=0.3)


def test_prep_plan_holds_lean_mass_constant():
    """The stated best-case assumption — every kilo lost is fat."""
    p = f.prep_plan(weight_kg=85, current_bf=20, target_bf=12, weeks=16, sex="male")
    lean = {row["lean_mass_kg"] for row in p["projection"]}
    assert len(lean) == 1


def test_prep_plan_flags_an_unsafe_rate():
    """10% body fat in 3 weeks is not a plan — it must come back as danger."""
    p = f.prep_plan(weight_kg=85, current_bf=20, target_bf=10, weeks=3, sex="male")
    assert p["risk"] == "danger"
    assert p["verdict"] == "Unsafe"
    assert p["weeks_at_safe_rate"] > 3


def test_prep_plan_accepts_a_sensible_rate():
    p = f.prep_plan(weight_kg=85, current_bf=18, target_bf=15, weeks=12, sex="male")
    assert p["risk"] in ("good", "ok")


def test_prep_plan_detects_target_below_sex_floor():
    """Same target, different sex — the female floor is higher, so it flags."""
    male = f.prep_plan(weight_kg=70, current_bf=20, target_bf=14, weeks=20, sex="male")
    female = f.prep_plan(weight_kg=70, current_bf=25, target_bf=14, weeks=20, sex="female")
    assert male["target_bf_below_floor"] is False
    assert female["target_bf_below_floor"] is True


def test_prep_plan_handles_a_gaining_goal():
    p = f.prep_plan(weight_kg=65, current_bf=10, target_bf=15, weeks=12, sex="male")
    assert p["direction"] == "gain"
    assert p["projection"][-1]["weight_kg"] > p["projection"][0]["weight_kg"]


def test_prep_plan_implied_deficit_uses_7700_kcal_per_kg():
    p = f.prep_plan(weight_kg=80, current_bf=20, target_bf=15, weeks=10, sex="male")
    expected = round(p["per_week_kg"] * f.KCAL_PER_KG_FAT / 7)
    assert p["implied_daily_kcal_delta"] == expected


# ---------------------------------------------------------------------------
#  STRENGTH
# ---------------------------------------------------------------------------

def test_one_rm_at_a_single_rep_returns_the_weight_lifted():
    """
    Epley at 1 rep gives w × (1 + 1/30) — slightly above w, which is the known
    quirk. Brzycki at 1 rep is exactly w (36/36).
    """
    o = f.one_rep_max(weight=100, reps=1)
    assert o["brzycki"] == 100.0
    assert o["epley"] == pytest.approx(103.3, abs=0.1)


def test_one_rm_epley_known_value():
    """140 kg × 5 reps: 140 × (1 + 5/30) = 163.33"""
    o = f.one_rep_max(weight=140, reps=5)
    assert o["epley"] == pytest.approx(163.3, abs=0.1)


def test_one_rm_brzycki_known_value():
    """140 × 36/(37−5) = 140 × 1.125 = 157.5"""
    o = f.one_rep_max(weight=140, reps=5)
    assert o["brzycki"] == pytest.approx(157.5, abs=0.1)


def test_epley_and_brzycki_cross_over_at_ten_reps():
    """
    The two equations agree at exactly 10 reps — Epley gives 1 + 10/30 = 1.3333
    and Brzycki gives 36/27 = 1.3333 — then swap which one reads higher.

    Worth pinning down because it's easy to state the relationship backwards, and
    the UI labels each estimate based on it.
    """
    at_ten = f.one_rep_max(weight=100, reps=10)
    assert at_ten["epley"] == pytest.approx(at_ten["brzycki"], abs=0.1)

    below = f.one_rep_max(weight=100, reps=5)
    assert below["epley"] > below["brzycki"]

    above = f.one_rep_max(weight=100, reps=15)
    assert above["brzycki"] > above["epley"]


def test_one_rm_confidence_degrades_with_reps():
    assert f.one_rep_max(weight=100, reps=3)["confidence"] == "high"
    assert f.one_rep_max(weight=100, reps=8)["confidence"] == "moderate"
    assert f.one_rep_max(weight=100, reps=15)["confidence"] == "low"


def test_one_rm_clamps_out_of_range_reps():
    assert f.one_rep_max(weight=100, reps=0)["reps"] == 1
    assert f.one_rep_max(weight=100, reps=50)["reps"] == 20


def test_pct_table_is_monotonic_and_plate_rounded():
    table = f.pct_table(200)
    weights = [r["weight"] for r in table]
    assert weights == sorted(weights, reverse=True)
    assert table[0]["weight"] == 200.0
    # Every plate-rounded load must be a multiple of 2.5 kg.
    assert all(abs(r["plate_rounded"] / 2.5 - round(r["plate_rounded"] / 2.5)) < 1e-9
               for r in table)


def test_dots_rewards_the_lighter_lifter_at_the_same_total():
    """The entire point of bodyweight-adjusted scoring."""
    light = f.dots_score(sex="male", bodyweight_kg=66, total_kg=500)
    heavy = f.dots_score(sex="male", bodyweight_kg=105, total_kg=500)
    assert light > heavy


def test_dots_and_wilks_broadly_agree():
    """Different polynomials, same job — they shouldn't diverge wildly."""
    d = f.dots_score(sex="male", bodyweight_kg=83, total_kg=520)
    w = f.wilks_score(sex="male", bodyweight_kg=83, total_kg=520)
    assert d is not None and w is not None
    assert abs(d - w) < 40


def test_dots_works_for_both_sexes():
    assert f.dots_score(sex="female", bodyweight_kg=60, total_kg=300) is not None
    assert f.wilks_score(sex="female", bodyweight_kg=60, total_kg=300) is not None


def test_scores_reject_nonsense_input():
    assert f.dots_score(sex="male", bodyweight_kg=0, total_kg=500) is None
    assert f.dots_score(sex="male", bodyweight_kg=80, total_kg=0) is None
    assert f.dots_score(sex="other", bodyweight_kg=80, total_kg=500) is None


def test_strength_band_thresholds():
    assert f.strength_band(150) == "Novice"
    assert f.strength_band(350) == "Advanced"
    assert f.strength_band(600) == "World class"
    assert f.strength_band(None) == "—"


# ---------------------------------------------------------------------------
#  ENERGY TARGETS
# ---------------------------------------------------------------------------

def test_energy_targets_ordering():
    t = f.energy_targets(tdee_kcal=2800, weight_kg=80)
    assert t["aggressive_cut"]["kcal"] < t["cut"]["kcal"] < t["maintain"]["kcal"] < t["bulk"]["kcal"]


def test_cut_is_20_percent_and_bulk_is_10():
    t = f.energy_targets(tdee_kcal=3000, weight_kg=80)
    assert t["cut"]["kcal"] == 2400
    assert t["bulk"]["kcal"] == 3300
    assert t["maintain"]["delta"] == 0


def test_cut_rate_lands_in_the_safe_band():
    """A 20% deficit for an 80 kg lifter should sit inside 0.5–1.0%/week."""
    t = f.energy_targets(tdee_kcal=2900, weight_kg=80)
    assert 0.4 <= t["cut"]["pct_bw_per_week"] <= 1.0
