"""
models.py — request and response schemas (Pydantic).

Validation lives here so the rest of the app can trust its inputs. Every numeric
field carries physiological bounds, which does two jobs: it blocks nonsense that
would produce a garbage plan (a 400 kg bodyweight, a 12-year-old's age), and it
returns a clear 422 instead of a stack trace.

The bounds are deliberately wide — wide enough for a real range of humans,
narrow enough to catch a typo like entering height in metres (1.75) instead of
centimetres (175).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Sex = Literal["male", "female"]
Goal = Literal["cut", "aggressive_cut", "maintain", "bulk"]
Diet = Literal["omnivore", "eggetarian", "vegetarian", "vegan"]
Climate = Literal["temperate", "warm", "hot", "very_hot"]
Activity = Literal["sedentary", "light", "moderate", "active", "very_active"]


class Girths(BaseModel):
    """
    Tape measurements in cm, for the U.S. Navy method.

    Measure relaxed, at the end of a normal exhale, with the tape snug but not
    compressing the skin. Same spots every time — consistency matters more than
    perfect placement.
    """
    neck: float | None = Field(None, ge=20, le=70, description="Below the larynx, tape sloping slightly down at the front")
    waist: float | None = Field(None, ge=40, le=200, description="Men: at the navel. Women: at the narrowest point")
    hip: float | None = Field(None, ge=50, le=200, description="Widest point of the glutes — needed for women")
    chest: float | None = Field(None, ge=50, le=200)
    thigh: float | None = Field(None, ge=25, le=110)
    arm: float | None = Field(None, ge=15, le=80)


class Skinfolds(BaseModel):
    """
    Calliper readings in mm, for the Jackson–Pollock equations.

    Pinch the skin and fat (not muscle), read 2 seconds after the callipers
    close, and take the median of three readings per site. Technique dominates
    accuracy here — an inconsistent measurer produces an inconsistent trend, and
    the trend is the whole point.
    """
    chest: float | None = Field(None, ge=1, le=80)
    abdomen: float | None = Field(None, ge=1, le=80)
    thigh: float | None = Field(None, ge=1, le=80)
    triceps: float | None = Field(None, ge=1, le=80)
    suprailiac: float | None = Field(None, ge=1, le=80)
    subscapular: float | None = Field(None, ge=1, le=80)
    midaxillary: float | None = Field(None, ge=1, le=80)


class AssessmentIn(BaseModel):
    """The main assessment payload."""

    # ---- Identity (optional — the tool works fully anonymously) ----------
    name: str | None = Field(None, max_length=80)

    # ---- Required basics --------------------------------------------------
    sex: Sex
    age: int = Field(..., ge=10, le=100, description="Years. Under-18s get a safety block, not a plan.")
    weight_kg: float = Field(..., ge=25, le=300)
    height_cm: float = Field(..., ge=100, le=250, description="In centimetres — 175, not 1.75")

    # ---- Goal & lifestyle -------------------------------------------------
    goal: Goal = "cut"
    activity: Activity = "moderate"
    diet: Diet = "omnivore"
    climate: Climate = "hot"           # India-first default
    training_hours: float = Field(1.0, ge=0, le=8, description="Average hours of training per day")
    meals: int = Field(4, ge=1, le=8)

    # ---- Measurements (any subset — more methods run with more data) -----
    girths: Girths | None = None
    skinfolds: Skinfolds | None = None
    bodyfat_pct: float | None = Field(
        None, ge=2, le=70,
        description="If you already have a trusted figure (DEXA, InBody), it overrides the estimates",
    )

    # ---- Optional goal & safety context ----------------------------------
    target_bodyfat_pct: float | None = Field(None, ge=2, le=60)
    contest_prep: bool = False
    pregnant: bool = False
    medical_conditions: bool = Field(
        False,
        description="Kidney, liver, thyroid, diabetes, heart conditions — anything that changes safe targets",
    )

    @field_validator("height_cm")
    @classmethod
    def _catch_metres(cls, v: float) -> float:
        """
        Catch the classic unit slip. A height under 100 cm on an adult form is
        almost always metres entered by mistake — the ge=100 bound already
        rejects it, but this makes the error message say why.
        """
        if v < 100:
            raise ValueError(
                "Height looks like metres. Enter it in centimetres — e.g. 175, not 1.75."
            )
        return v


class PrepPlanIn(BaseModel):
    """Contest / goal prep planner payload."""
    sex: Sex
    weight_kg: float = Field(..., ge=25, le=300)
    current_bodyfat_pct: float = Field(..., ge=2, le=70)
    target_bodyfat_pct: float = Field(..., ge=2, le=60)
    weeks: int = Field(..., ge=1, le=104, description="Weeks until the target date")


class StrengthIn(BaseModel):
    """1RM estimator, plus optional DOTS/Wilks scoring."""
    weight: float = Field(..., ge=1, le=600, description="Weight lifted, kg")
    reps: int = Field(..., ge=1, le=20, description="Reps completed — must be a set close to failure")
    # Optional powerlifting-total scoring
    sex: Sex | None = "male"
    bodyweight_kg: float | None = Field(None, ge=25, le=300)
    total_kg: float | None = Field(None, ge=50, le=1500, description="Squat + bench + deadlift")


class BodyfatIn(BaseModel):
    """Standalone body-fat method comparison."""
    sex: Sex
    age: int = Field(..., ge=10, le=100)
    weight_kg: float = Field(..., ge=25, le=300)
    height_cm: float = Field(..., ge=100, le=250)
    girths: Girths | None = None
    skinfolds: Skinfolds | None = None


# ---------------------------------------------------------------------------
#  Client tracking
# ---------------------------------------------------------------------------

class ClientIn(BaseModel):
    """A saved client profile."""
    name: str = Field(..., min_length=1, max_length=80)
    sex: Sex
    age: int = Field(..., ge=10, le=100)
    height_cm: float = Field(..., ge=100, le=250)
    diet: Diet = "omnivore"
    goal: Goal = "cut"
    notes: str | None = Field(None, max_length=2000)


class MeasurementIn(BaseModel):
    """
    One dated measurement entry for a client.

    `taken_on` is a plain ISO date string (YYYY-MM-DD) so the chart can sort
    without timezone ambiguity — these are dates a coach wrote on a sheet, not
    instants.
    """
    taken_on: str = Field(..., description="ISO date, YYYY-MM-DD")
    weight_kg: float = Field(..., ge=25, le=300)
    bodyfat_pct: float | None = Field(None, ge=2, le=70)
    waist_cm: float | None = Field(None, ge=40, le=200)
    neck_cm: float | None = Field(None, ge=20, le=70)
    hip_cm: float | None = Field(None, ge=50, le=200)
    chest_cm: float | None = Field(None, ge=50, le=200)
    arm_cm: float | None = Field(None, ge=15, le=80)
    thigh_cm: float | None = Field(None, ge=25, le=110)
    note: str | None = Field(None, max_length=500)

    @field_validator("taken_on")
    @classmethod
    def _iso_date(cls, v: str) -> str:
        from datetime import date
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("taken_on must be an ISO date, e.g. 2026-08-10")
        return v


# ---------------------------------------------------------------------------
#  Coach authentication
# ---------------------------------------------------------------------------

class LoginIn(BaseModel):
    """
    Coach login.

    No username: there's exactly one coach. Adding a username field would imply a
    user table that doesn't exist and give an attacker a second thing to enumerate.
    """
    password: str = Field(..., min_length=1, max_length=200)


# ---------------------------------------------------------------------------
#  Onboarding
# ---------------------------------------------------------------------------

class InviteIn(BaseModel):
    """Create a one-time onboarding link."""
    label: str | None = Field(
        None, max_length=80,
        description="A note to yourself about who this link is for — the client never sees it",
    )
    ttl_days: int = Field(14, ge=1, le=90, description="How long the link stays usable")


class IntakeIn(BaseModel):
    """
    A submitted questionnaire.

    `answers` is deliberately a free-form dict rather than 30 typed fields. The
    questionnaire is defined in `app/intake.py` and will keep changing, so pinning
    it into a Pydantic model here would mean editing two files for every question
    and would reject older submissions. Required fields and value sanity are
    checked against that schema at the route instead, which keeps one source of
    truth.

    The consent flag is typed, because that one is a promise rather than data.
    """
    answers: dict = Field(..., description="key → value, keyed by the intake field keys")
    consent: bool = Field(..., description="Must be true — the client ticked the consent box")

    @field_validator("answers")
    @classmethod
    def _reasonable_size(cls, v: dict) -> dict:
        """
        Bound the payload.

        This endpoint is reachable by anyone holding a link, so it shouldn't accept
        an arbitrarily large body. Generous enough for long free-text answers,
        small enough that it can't be used to fill the disk.
        """
        if len(v) > 200:
            raise ValueError("Too many fields in this submission.")
        for key, value in v.items():
            if isinstance(value, str) and len(value) > 5000:
                raise ValueError(f"The answer for '{key}' is too long.")
        return v

    @field_validator("consent")
    @classmethod
    def _must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "We can't store your answers without your consent. "
                "Please tick the consent box."
            )
        return v


class MealPlanIn(AssessmentIn):
    """
    An assessment, plus the three things that decide what food the plan may use.

    All three come straight from the onboarding questionnaire, which is the point:
    the coach shouldn't have to re-type what the client already told them, and a
    plan built without them is the kind that gets politely ignored — full of food
    the client can't afford, doesn't eat, or is allergic to.
    """

    budget: Literal["tight", "moderate", "flexible"] = "moderate"
    dislikes: str = Field("", max_length=500,
                          description="Free text from the intake — foods they won't eat")
    allergies: str = Field("", max_length=500,
                           description="Free text from the intake — allergies and intolerances")


class PriceIn(BaseModel):
    """
    One grocery price, as the coach's shop actually charges.

    Bounded rather than open: a price of zero would make a food look free and
    quietly skew every total that includes it, and an absurd upper figure is
    almost always a typo — a stray zero on ₹280 becomes ₹2,800 and the coach
    quotes a client a monthly food budget four times too high.
    """

    price: float = Field(..., gt=0, le=100_000,
                         description="Rupees per kg, per litre, or per piece")


# The diet category a coach picks, and the tags it becomes. Offered as one
# choice rather than a free tag list because the tag vocabulary is an internal
# detail — a coach should not have to know that "veg" and "vegan" are separate
# flags for `foods.diet_ok` to filter correctly.
FOOD_CATEGORY_TAGS = {
    "meat_fish": ["nonveg"],
    "egg":       ["egg"],
    "dairy":     ["veg", "dairy"],
    "plant":     ["veg", "vegan"],
}


class CustomFoodIn(BaseModel):
    """
    A food the coach adds themselves.

    Macros are asked for **per 100 g**, because that is how every food label in
    the country is written — a coach copying numbers off a packet should not have
    to do arithmetic first. The portion is asked separately, and the per-portion
    figures the planner needs are derived from the two.

    The calorie figure is checked against the macros rather than trusted. Protein
    and carbohydrate carry 4 kcal per gram and fat 9, so the three imply a
    calorie total; if what was typed disagrees badly, something was mistyped, and
    a wrong food silently poisons every plan it appears in and every grocery bill
    derived from those plans. Catching it at the point of entry is the only place
    it is cheap.
    """

    name: str = Field(..., min_length=2, max_length=60)
    household: str = Field(..., min_length=2, max_length=60,
                           description='How a client says it — "1 katori", "2 rotis"')
    portion_grams: float = Field(..., gt=0, le=2000,
                                 description="What one portion weighs, in grams")
    category: Literal["meat_fish", "egg", "dairy", "plant"]

    # Per 100 g, straight off the label.
    kcal_100g: float = Field(..., ge=0, le=900)
    protein_100g: float = Field(..., ge=0, le=100)
    carb_100g: float = Field(..., ge=0, le=100)
    fat_100g: float = Field(..., ge=0, le=100)
    fibre_100g: float = Field(0, ge=0, le=100)

    # How it is bought.
    unit: Literal["kg", "litre", "piece"] = "kg"
    price: float = Field(..., gt=0, le=100_000, description="Rupees per kg / litre / piece")
    piece_grams: float | None = Field(None, gt=0, le=5000,
                                      description="Weight of one piece, if sold by the piece")
    raw_factor: float = Field(1.0, gt=0, le=5,
                              description="Buy this much per gram eaten — >1 if it "
                                          "loses weight cooking, <1 if it absorbs water")

    @field_validator("carb_100g")
    @classmethod
    def _macros_fit_in_100g(cls, v: float, info) -> float:
        """Protein plus carbohydrate plus fat cannot exceed the 100 g they are in."""
        data = info.data
        total = v + data.get("protein_100g", 0) + data.get("fat_100g", 0)
        if total > 100:
            raise ValueError(
                f"Protein, carbs and fat come to {total:.0f} g, which is more than "
                "the 100 g they're measured in. Check the label."
            )
        return v

    @field_validator("fat_100g")
    @classmethod
    def _calories_match_the_macros(cls, v: float, info) -> float:
        """
        Reconcile the stated calories against 4/4/9.

        Tolerance is wide on purpose. Labels round, fibre is counted differently
        by different manufacturers, and sugar alcohols do not carry 4 kcal — so a
        small disagreement is normal and rejecting it would be pedantic. A large
        one is a typo: a stray zero, or grams typed into the calorie box.
        """
        data = info.data
        stated = data.get("kcal_100g")
        protein, carb = data.get("protein_100g"), data.get("carb_100g")
        if stated is None or protein is None or carb is None:
            return v                            # an earlier field already failed

        implied = protein * 4 + carb * 4 + v * 9
        if implied == 0 and stated == 0:
            return v
        if stated == 0 or abs(implied - stated) > max(30, stated * 0.25):
            raise ValueError(
                f"These don't add up: {protein:g} g protein + {carb:g} g carbs + "
                f"{v:g} g fat works out to about {implied:.0f} kcal, but you typed "
                f"{stated:g}. Protein and carbs are 4 kcal per gram, fat is 9. "
                "One of the four numbers is probably mistyped."
            )
        return v

    @field_validator("piece_grams")
    @classmethod
    def _pieces_need_a_weight(cls, v, info):
        if info.data.get("unit") == "piece" and not v:
            raise ValueError(
                "Sold by the piece, so I need to know what one piece weighs — "
                "otherwise there's no way to turn grams into a number to buy."
            )
        return v
