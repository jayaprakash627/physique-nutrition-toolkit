"""
test_safety.py — the guardrails.

These tests exist because the failure mode here is the worst one the app has: a
plausible-looking plan handed to someone it could hurt. A silent regression in
this layer wouldn't break any page — it would just quietly stop warning people.

So each test asserts a specific flag code fires for a specific unsafe input, and
that the ones that should block do block.
"""

import pytest

from app import engine, safety


def codes(flags):
    return {fl["code"] for fl in flags}


# ---------------------------------------------------------------------------
#  Demographic gates
# ---------------------------------------------------------------------------

def test_under_18_is_blocked():
    flags = safety.check_demographics(age=16, sex="male")
    assert "UNDER_18" in codes(flags)
    assert any(fl["blocked"] for fl in flags)


def test_late_teens_gets_a_warning_not_a_block():
    flags = safety.check_demographics(age=19, sex="female")
    assert "YOUNG_ADULT" in codes(flags)
    assert not any(fl["blocked"] for fl in flags)


def test_adult_with_no_risk_factors_is_clean():
    assert safety.check_demographics(age=28, sex="male") == []


def test_pregnancy_is_blocked():
    flags = safety.check_demographics(age=30, sex="female", pregnant=True)
    assert "PREGNANCY" in codes(flags)
    assert any(fl["blocked"] for fl in flags)


def test_medical_condition_warns_without_blocking():
    """
    A medical condition means "take this to a clinician", not "no numbers for
    you" — blocking would just push the person to a tool with no warning at all.
    """
    flags = safety.check_demographics(age=40, sex="male", medical_conditions=True)
    assert "MEDICAL_CONDITION" in codes(flags)
    assert not any(fl["blocked"] for fl in flags)


def test_older_adult_gets_the_higher_protein_note():
    flags = safety.check_demographics(age=70, sex="male")
    assert "OLDER_ADULT" in codes(flags)


# ---------------------------------------------------------------------------
#  Body-fat floors — different by sex, which is the point
# ---------------------------------------------------------------------------

def test_below_essential_bodyfat_is_blocked():
    flags = safety.check_bodyfat_target(sex="male", current_bf=2.5)
    assert "BF_BELOW_ESSENTIAL" in codes(flags)
    assert any(fl["blocked"] for fl in flags)


def test_female_essential_floor_is_higher_than_male():
    """
    12% body fat is athletic for a man and below essential fat for a woman. If
    this ever returns the same verdict for both, the layer is unsafe.
    """
    male = safety.check_bodyfat_target(sex="male", current_bf=12)
    female = safety.check_bodyfat_target(sex="female", current_bf=12)
    assert codes(male) == set()
    assert "BF_BELOW_FLOOR" in codes(female)


def test_target_below_essential_is_blocked():
    flags = safety.check_bodyfat_target(sex="female", current_bf=25, target_bf=8)
    assert "TARGET_BELOW_ESSENTIAL" in codes(flags)
    assert any(fl["blocked"] for fl in flags)


def test_contest_stage_target_warns():
    flags = safety.check_bodyfat_target(sex="male", current_bf=15, target_bf=6)
    assert "TARGET_BELOW_FLOOR" in codes(flags)
    assert not any(fl["blocked"] for fl in flags)


def test_target_above_current_is_just_information():
    flags = safety.check_bodyfat_target(sex="male", current_bf=12, target_bf=15)
    assert "TARGET_ABOVE_CURRENT" in codes(flags)
    assert all(fl["level"] == "info" for fl in flags)


# ---------------------------------------------------------------------------
#  Energy
# ---------------------------------------------------------------------------

def test_below_absolute_calorie_floor_is_blocked():
    flags = safety.check_energy(
        sex="female", kcal_target=1000, bmr=1300, tdee=2000,
        weight_kg=55, rate_pct_bw=1.2, goal="cut",
    )
    assert "BELOW_KCAL_FLOOR" in codes(flags)
    assert any(fl["blocked"] for fl in flags)


def test_aggressive_cut_always_warns():
    """
    The 'aggressive cut' option is exactly 25% below maintenance. The threshold
    is set just under 25 so rounding can never let this slip through unflagged —
    the option that most needs its trade-offs explained.
    """
    tdee = 2800
    flags = safety.check_energy(
        sex="male", kcal_target=round(tdee * 0.75), bmr=1800, tdee=tdee,
        weight_kg=80, rate_pct_bw=0.9, goal="cut",
    )
    assert "AGGRESSIVE_DEFICIT" in codes(flags)


def test_standard_20_percent_cut_does_not_warn_about_depth():
    tdee = 2800
    flags = safety.check_energy(
        sex="male", kcal_target=round(tdee * 0.80), bmr=1800, tdee=tdee,
        weight_kg=80, rate_pct_bw=0.7, goal="cut",
    )
    assert "AGGRESSIVE_DEFICIT" not in codes(flags)


def test_eating_below_bmr_warns():
    flags = safety.check_energy(
        sex="male", kcal_target=1700, bmr=1900, tdee=2600,
        weight_kg=80, rate_pct_bw=0.8, goal="cut",
    )
    assert "BELOW_BMR" in codes(flags)


def test_fast_loss_rate_warns():
    flags = safety.check_energy(
        sex="male", kcal_target=2000, bmr=1800, tdee=2600,
        weight_kg=80, rate_pct_bw=1.6, goal="cut",
    )
    assert "RATE_TOO_FAST" in codes(flags)


def test_fast_bulk_is_flagged_as_info_only():
    flags = safety.check_energy(
        sex="male", kcal_target=3400, bmr=1800, tdee=2900,
        weight_kg=80, rate_pct_bw=0.9, goal="bulk",
    )
    assert "BULK_TOO_FAST" in codes(flags)
    assert not any(fl["blocked"] for fl in flags)


# ---------------------------------------------------------------------------
#  Macros
# ---------------------------------------------------------------------------

def test_fat_floor_breach_is_reported():
    from app.formulas import macros
    m = macros(kcal=1300, weight_kg=100, lbm_kg=75, goal="cut")
    flags = safety.check_macros(macro_block=m, weight_kg=100, sex="male")
    assert "FAT_RAISED_TO_FLOOR" in codes(flags)


def test_impossible_macros_are_blocked():
    from app.formulas import macros
    m = macros(kcal=900, weight_kg=110, lbm_kg=95, goal="cut")
    flags = safety.check_macros(macro_block=m, weight_kg=110, sex="male")
    assert "CARBS_IMPOSSIBLE" in codes(flags)
    assert any(fl["blocked"] for fl in flags)


def test_very_low_carbs_warn_about_training_quality():
    from app.formulas import macros
    m = macros(kcal=1600, weight_kg=90, lbm_kg=72, goal="cut")
    flags = safety.check_macros(macro_block=m, weight_kg=90, sex="male")
    assert "CARBS_VERY_LOW" in codes(flags)


# ---------------------------------------------------------------------------
#  Summary assembly
# ---------------------------------------------------------------------------

def test_summarise_orders_most_severe_first():
    flags = [
        {"level": "info", "code": "I", "title": "", "message": "", "action": "", "blocked": False},
        {"level": "danger", "code": "D", "title": "", "message": "", "action": "", "blocked": False},
        {"level": "warning", "code": "W", "title": "", "message": "", "action": "", "blocked": False},
    ]
    s = safety.summarise(flags)
    assert [fl["code"] for fl in s["flags"]] == ["D", "W", "I"]
    assert s["level"] == "danger"


def test_summarise_clean_input():
    s = safety.summarise([])
    assert s["level"] == "good"
    assert s["blocked"] is False
    assert s["counts"] == {"danger": 0, "warning": 0, "info": 0}


def test_summarise_propagates_blocked():
    flags = [{"level": "danger", "code": "X", "title": "", "message": "",
              "action": "", "blocked": True}]
    assert safety.summarise(flags)["blocked"] is True


# ---------------------------------------------------------------------------
#  End-to-end through the engine — the flags must survive the whole pipeline
# ---------------------------------------------------------------------------

BASE = dict(
    sex="male", age=28, weight_kg=80, height_cm=178, goal="cut",
    activity="moderate", diet="omnivore", climate="hot", training_hours=1.0,
    meals=4, girths={"neck": 39, "waist": 85, "hip": None}, skinfolds=None,
    bodyfat_pct=None, target_bodyfat_pct=None, contest_prep=False,
    pregnant=False, medical_conditions=False, name=None,
)


def test_engine_blocks_a_minor():
    r = engine.assess({**BASE, "age": 15})
    assert r["safety"]["blocked"] is True
    assert "UNDER_18" in codes(r["safety"]["flags"])
    # The numbers are still computed — we mark them, we don't hide them.
    assert r["nutrition"]["protein"]["number"] > 0


def test_engine_flags_pregnancy():
    r = engine.assess({
        **BASE, "sex": "female",
        "girths": {"neck": 32, "waist": 72, "hip": 95}, "pregnant": True,
    })
    assert "PREGNANCY" in codes(r["safety"]["flags"])
    assert r["safety"]["blocked"] is True


def test_engine_clean_case_has_no_warnings():
    r = engine.assess(BASE)
    assert r["safety"]["level"] == "good"
    assert r["safety"]["blocked"] is False


def test_engine_always_attaches_the_disclaimer():
    r = engine.assess(BASE)
    assert "not medical advice" in r["disclaimer"].lower()
    assert len(r["safeguarding"]) > 50


def test_prep_report_blocks_an_impossible_timeline():
    r = engine.prep_report(dict(
        sex="male", weight_kg=85, current_bodyfat_pct=22,
        target_bodyfat_pct=8, weeks=4,
    ))
    assert r["safety"]["blocked"] is True
    assert "PREP_RATE_UNSAFE" in codes(r["safety"]["flags"])


def test_prep_report_accepts_a_reasonable_timeline():
    r = engine.prep_report(dict(
        sex="male", weight_kg=85, current_bodyfat_pct=18,
        target_bodyfat_pct=14, weeks=14,
    ))
    assert r["safety"]["blocked"] is False
