"""
intake.py — the client onboarding questionnaire, and what it tells the coach.

This is a sales asset as much as a data-collection form. The reasoning: most
trainers ask weight, goal, done. If a client is asked thirty careful questions —
sleep, shift work, who cooks at home, which foods they genuinely hate, what broke
their last diet attempt — their reaction is "nobody has ever asked me this."
That feeling happens before any coaching has been delivered, and it is what
closes the sale.

Two things make it work, and both are encoded in the schema:

1. **Every question carries a `why`.** Same instinct as the calculator's "Why
   this number?" panels — explaining the question demonstrates competence and
   earns the answer. It also means a client never feels interrogated.

2. **It ends with a personalised observation, not a plan.** `derive_priorities()`
   reflects back what their answers imply, referencing what they actually said,
   and stops short of the numbers. The numbers are the paid deliverable; the
   insight is the reason to book the call.

Questions live here rather than in the HTML so the form is generated from one
source — the same pattern as /api/meta. Adding a question is a one-line change
that the frontend picks up automatically, and the "why" text sits next to the
question it explains.
"""

from __future__ import annotations

CONSENT_VERSION = "2026-08-v1"

# ---------------------------------------------------------------------------
#  THE QUESTIONNAIRE
# ---------------------------------------------------------------------------

SECTIONS: list[dict] = [
    {
        "id": "basics",
        "title": "The basics",
        "intro": "Enough to work out your starting numbers. Two minutes.",
        "fields": [
            {"key": "full_name", "label": "Your name", "type": "text", "required": True,
             "placeholder": "As you'd like me to write it on your plan"},
            {"key": "contact", "label": "Phone or email", "type": "text", "required": True,
             "placeholder": "So I can send your plan",
             "why": "I only use this to reach you about your coaching. It isn't shared with anyone."},
            {"key": "age", "label": "Age", "type": "number", "required": True, "min": 10, "max": 100},
            {"key": "sex", "label": "Sex", "type": "radio", "required": True,
             "options": [{"value": "male", "label": "Male"}, {"value": "female", "label": "Female"}],
             "why": "Body-fat equations, healthy fat floors and iron requirements genuinely "
                    "differ by sex — a plan that ignores this gets one of them wrong."},
            {"key": "height_cm", "label": "Height", "type": "number", "unit": "cm",
             "required": True, "min": 100, "max": 250},
            {"key": "weight_kg", "label": "Weight", "type": "number", "unit": "kg",
             "required": True, "min": 25, "max": 300},
            {"key": "goal", "label": "What do you want to change?", "type": "radio", "required": True,
             "options": [
                 {"value": "cut", "label": "Lose fat"},
                 {"value": "maintain", "label": "Stay the same, get fitter"},
                 {"value": "bulk", "label": "Build muscle"},
                 {"value": "recomp", "label": "Both — leaner and stronger"},
             ]},
            {"key": "goal_detail", "label": "In your own words, what does success look like in six months?",
             "type": "textarea",
             "placeholder": "A number, a photo, fitting into something, keeping up with your kids — anything",
             "why": "\"Lose weight\" and \"look good at my sister's wedding in March\" need different "
                    "plans. The specific version is what I actually coach toward."},
        ],
    },
    {
        "id": "training",
        "title": "Your training",
        "intro": "So I program around your body and your gym, not a textbook.",
        "fields": [
            {"key": "experience", "label": "How long have you trained seriously?", "type": "radio",
             "options": [
                 {"value": "none", "label": "Never / just starting"},
                 {"value": "under1", "label": "Under a year"},
                 {"value": "1to3", "label": "1–3 years"},
                 {"value": "3plus", "label": "3+ years"},
             ],
             "why": "Beginners gain far faster than experienced lifters. Promising you a "
                    "beginner's rate of progress after five years of training would be a lie."},
            {"key": "sessions_per_week", "label": "Sessions per week you can realistically commit to",
             "type": "number", "min": 0, "max": 14,
             "why": "Realistically, not ideally. I'd rather build a 3-day plan you finish "
                    "than a 6-day plan you abandon in week two."},
            {"key": "training_now", "label": "What does your training look like right now?",
             "type": "textarea",
             "placeholder": "e.g. push/pull/legs at a commercial gym, or cricket twice a week and nothing else",
             "why": "I need your starting point. Cutting your volume in half or doubling it "
                    "overnight both go badly."},
            {"key": "gym_access", "label": "Where will you train?", "type": "select",
             "options": [
                 {"value": "full_gym", "label": "Full commercial gym"},
                 {"value": "basic_gym", "label": "Basic gym — barbell, dumbbells, a few machines"},
                 {"value": "home_equipped", "label": "Home with some equipment"},
                 {"value": "home_bodyweight", "label": "Home, bodyweight only"},
                 {"value": "none", "label": "Nothing yet"},
             ],
             "why": "There's no point writing a cable-heavy plan for someone with a barbell "
                    "and two dumbbells."},
            {"key": "injuries", "label": "Any injuries, past or present? Anything that hurts?",
             "type": "textarea",
             "placeholder": "Lower back, shoulder, knee, an old fracture — and whether it's current or historic",
             "why": "This is the question most trainers skip and then aggravate. I program "
                    "around an injury, not through it. Tell me even if it's old."},
            {"key": "lifts", "label": "Know any of your numbers?", "type": "textarea",
             "placeholder": "e.g. squat 100kg × 5, or \"no idea\" — both are fine",
             "why": "Only if you have them. If you don't, we'll establish them together — "
                    "there's no wrong answer here."},
        ],
    },
    {
        "id": "life",
        "title": "Your actual day",
        "intro": "This is the section that changes plans the most, and the one almost nobody asks about.",
        "fields": [
            {"key": "work_type", "label": "What's your work day like?", "type": "select",
             "options": [
                 {"value": "desk", "label": "Desk job, mostly sitting"},
                 {"value": "mixed", "label": "Mix of sitting and moving"},
                 {"value": "onfeet", "label": "On my feet most of the day"},
                 {"value": "physical", "label": "Physically demanding work"},
                 {"value": "shift", "label": "Shift work / nights"},
                 {"value": "student", "label": "Studying"},
                 {"value": "home", "label": "At home / not working right now"},
             ],
             "why": "Your calorie needs are set far more by the other 23 hours than by your "
                    "hour in the gym. Shift work in particular changes everything about meal timing."},
            {"key": "sleep_hours", "label": "Hours of sleep on a typical night", "type": "number",
             "min": 2, "max": 14, "unit": "hrs",
             "why": "Under-sleeping raises hunger hormones, lowers training performance and "
                    "slows recovery. If this number is low, fixing it will do more for you "
                    "than any tweak to your macros."},
            {"key": "sleep_quality", "label": "How well do you sleep?", "type": "radio",
             "options": [
                 {"value": "good", "label": "Well"},
                 {"value": "ok", "label": "Okay"},
                 {"value": "poor", "label": "Badly"},
             ]},
            {"key": "stress", "label": "Current stress level", "type": "radio",
             "options": [
                 {"value": "low", "label": "Low"},
                 {"value": "medium", "label": "Manageable"},
                 {"value": "high", "label": "High"},
             ],
             "why": "High stress makes a big calorie deficit much harder to sustain, and it's "
                    "a reason to start gentler rather than to try harder."},
            {"key": "steps", "label": "Roughly how much do you walk daily?", "type": "select",
             "options": [
                 {"value": "very_low", "label": "Barely at all"},
                 {"value": "low", "label": "A little — under 4,000 steps"},
                 {"value": "moderate", "label": "Moderate — 4,000–8,000"},
                 {"value": "high", "label": "A lot — 8,000+"},
                 {"value": "unknown", "label": "No idea"},
             ]},
            {"key": "climate", "label": "How hot is it where you live and train?", "type": "select",
             "options": [
                 {"value": "temperate", "label": "Mild, or air-conditioned most of the day"},
                 {"value": "warm", "label": "Warm — 25–30°C"},
                 {"value": "hot", "label": "Hot — 30–38°C"},
                 {"value": "very_hot", "label": "Very hot or humid — above 38°C"},
             ],
             "why": "Sweat losses in Indian summer are large enough to change your fluid and "
                    "electrolyte targets, and they're a common hidden cause of cramping and flat sessions."},
        ],
    },
    {
        "id": "food",
        "title": "How you actually eat",
        "intro": "A plan built from food you don't like is a plan you'll quit. Be honest here.",
        "fields": [
            {"key": "diet", "label": "How do you eat?", "type": "radio", "required": True,
             "options": [
                 {"value": "omnivore", "label": "Everything"},
                 {"value": "eggetarian", "label": "Eggs and dairy, no meat or fish"},
                 {"value": "vegetarian", "label": "Vegetarian — dairy yes, no egg"},
                 {"value": "vegan", "label": "Vegan"},
             ]},
            {"key": "who_cooks", "label": "Who cooks your food?", "type": "select",
             "options": [
                 {"value": "self", "label": "I cook for myself"},
                 {"value": "family", "label": "Family cooks at home"},
                 {"value": "help", "label": "Cook or help at home"},
                 {"value": "mess", "label": "Mess / hostel / canteen"},
                 {"value": "outside", "label": "Mostly outside food or delivery"},
             ],
             "why": "If someone else cooks, your plan has to work with what's already being "
                    "made. Handing you a plan your mother isn't cooking is useless."},
            {"key": "eat_out", "label": "How often do you eat out or order in?", "type": "select",
             "options": [
                 {"value": "rare", "label": "Rarely"},
                 {"value": "weekly", "label": "Once or twice a week"},
                 {"value": "often", "label": "Several times a week"},
                 {"value": "daily", "label": "Most days"},
             ],
             "why": "I'd rather build this in than pretend it won't happen. Restaurant food "
                    "is mostly hidden oil, and there are easy ways to work around it."},
            {"key": "dislikes", "label": "Foods you genuinely dislike or won't eat",
             "type": "textarea",
             "placeholder": "Be specific — if you hate paneer, I need to know before I build your plan around it",
             "why": "The fastest way to make someone quit is to fill their plan with food they "
                    "dread. There's always an alternative with the same numbers."},
            {"key": "allergies", "label": "Allergies or intolerances", "type": "textarea",
             "placeholder": "Lactose, gluten, nuts, anything — or \"none\"",
             "why": "Safety first, and lactose intolerance in particular changes where your "
                    "protein and calcium come from."},
            {"key": "fasting", "label": "Do you fast, or follow religious food practices?",
             "type": "textarea",
             "placeholder": "Ekadashi, Navratri, Ramadan, Karwa Chauth, no meat on certain days, Jain restrictions…",
             "why": "These are real, recurring and completely plannable — but only if I know "
                    "in advance. Most plans ignore them and then break every festival."},
            {"key": "tea_coffee", "label": "Cups of tea or coffee a day", "type": "number",
             "min": 0, "max": 20,
             "why": "The tannins in tea and coffee block iron absorption. If you're "
                    "vegetarian and drink chai with meals, that combination alone can be the "
                    "cause of feeling tired — and the fix is just timing."},
            {"key": "alcohol", "label": "Alcohol", "type": "select",
             "options": [
                 {"value": "none", "label": "None"},
                 {"value": "occasional", "label": "Occasionally"},
                 {"value": "weekly", "label": "Weekly"},
                 {"value": "frequent", "label": "Several times a week"},
             ],
             "why": "Asked without judgement — it's calories, and it affects sleep and "
                    "recovery. I plan around your life, not an imaginary one."},
            {"key": "supplements", "label": "Supplements you take now", "type": "textarea",
             "placeholder": "Whey, creatine, vitamins, anything prescribed — or \"none\"",
             "why": "So I don't double up, and so I can tell you honestly which of them are "
                    "doing nothing for you."},
            {"key": "budget", "label": "Any budget constraints on food?", "type": "select",
             "options": [
                 {"value": "tight", "label": "Yes, keep it cheap"},
                 {"value": "moderate", "label": "Reasonable"},
                 {"value": "flexible", "label": "Not a concern"},
             ],
             "why": "Dal, eggs, curd, soya and peanuts do the same job as expensive imported "
                    "protein. I'd rather build a plan you can afford every month."},
        ],
    },
    {
        "id": "history",
        "title": "What you've already tried",
        "intro": "The most useful section in this whole form. What failed before tells me what to do differently.",
        "fields": [
            {"key": "dieted_before", "label": "Have you dieted before?", "type": "radio",
             "options": [
                 {"value": "never", "label": "Never"},
                 {"value": "once", "label": "Once or twice"},
                 {"value": "many", "label": "Many times"},
             ]},
            {"key": "what_broke_it", "label": "What made you stop last time?",
             "type": "textarea",
             "placeholder": "Hunger, boredom, travel, no results, family food, gave up in week three — anything",
             "why": "This is the single most valuable thing you can tell me. Almost nobody "
                    "fails from bad numbers — they fail from a plan that didn't fit their "
                    "life. If I know where it broke, I can build around it."},
            {"key": "biggest_obstacle", "label": "What's the hardest part for you?",
             "type": "textarea",
             "placeholder": "Evening cravings, no time to cook, eating at work, motivation, weekends…"},
            {"key": "tracking_ok", "label": "Are you willing to weigh and log food, at least at first?",
             "type": "radio",
             "options": [
                 {"value": "yes", "label": "Yes"},
                 {"value": "some", "label": "For a while, not forever"},
                 {"value": "no", "label": "I'd rather not"},
             ],
             "why": "There's no wrong answer. If logging isn't for you I'll build a "
                    "portion-based plan instead — it works, it's just less precise."},
        ],
    },
    {
        "id": "health",
        "title": "Health and safety",
        "intro": "I need this to keep you safe. If anything here applies, it changes what I'll recommend — "
                 "and in some cases it means working with your doctor rather than around them.",
        "fields": [
            {"key": "conditions", "label": "Any diagnosed medical conditions?",
             "type": "textarea",
             "placeholder": "Diabetes, thyroid, PCOS, blood pressure, kidney or liver, heart, digestive — or \"none\"",
             "why": "These genuinely change what's safe. Kidney conditions change safe protein "
                    "intake; thyroid changes energy expenditure; diabetes changes carb timing. "
                    "I'd rather coordinate with your doctor than guess."},
            {"key": "medications", "label": "Medications or supplements prescribed to you",
             "type": "textarea", "placeholder": "Or \"none\"",
             "why": "Some interact with diet directly — blood thinners and vitamin K, for "
                    "instance, need consistent green-vegetable intake rather than a sudden change."},
            {"key": "pregnant", "label": "Are you pregnant or breastfeeding?", "type": "radio",
             "options": [
                 {"value": "no", "label": "No"},
                 {"value": "yes", "label": "Yes"},
                 {"value": "na", "label": "Not applicable"},
             ],
             "why": "Requirements change substantially, and a fat-loss plan isn't appropriate. "
                    "If yes, we work with your doctor."},
            {"key": "eating_disorder_history", "label": "Any history of disordered eating?",
             "type": "radio",
             "options": [
                 {"value": "no", "label": "No"},
                 {"value": "yes", "label": "Yes"},
                 {"value": "prefer_not", "label": "I'd rather discuss it in person"},
             ],
             "why": "Asked with care, and it stays between us. If yes, tracking and deficits "
                    "can do real harm, and I'd want a registered dietitian involved. Saying so "
                    "changes my approach for the better, not your eligibility."},
            {"key": "bloodwork", "label": "Had bloodwork done recently?", "type": "radio",
             "options": [
                 {"value": "yes", "label": "Yes, I can share it"},
                 {"value": "old", "label": "A while ago"},
                 {"value": "no", "label": "No"},
             ],
             "why": "Vitamin D, B12 and ferritin are commonly low in India and are worth "
                    "knowing rather than guessing. Not required — just useful if you have it."},
            {"key": "anything_else", "label": "Anything else I should know?",
             "type": "textarea",
             "placeholder": "Anything at all — this is a free space"},
        ],
    },
]


# ---------------------------------------------------------------------------
#  Consent — shown before submit, stored with the answers
# ---------------------------------------------------------------------------

CONSENT = {
    "version": CONSENT_VERSION,
    "title": "Your data, and what happens to it",
    "points": [
        "What you enter here is used only to build and adjust your coaching plan.",
        "It is stored privately and is not sold, shared or used for advertising.",
        "Health information is sensitive, and it's treated that way — only your coach sees it.",
        "You can ask for a copy of your data, or ask for it to be deleted, at any time.",
        "This form is not a medical consultation. Coaching guidance is general nutrition "
        "and training support, not medical advice, diagnosis or treatment.",
        "If anything in the health section applies to you, your coach may ask you to speak "
        "to a doctor before starting.",
    ],
    "checkbox_label": "I've read the above and I'm happy for my answers to be used to build my plan.",
}


# ---------------------------------------------------------------------------
#  What the coach sees back: a personalised observation, not a plan
# ---------------------------------------------------------------------------

def _n(answers: dict, key: str, default: float = 0) -> float:
    """Read a numeric answer that may arrive as a string or be missing."""
    try:
        v = answers.get(key)
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _has_content(answers: dict, key: str) -> bool:
    """
    Did they write something meaningful, rather than a dismissal?

    "none", "nil", "-" and friends are the polite way of saying nothing, and
    treating them as content would produce embarrassing feedback.
    """
    v = (answers.get(key) or "").strip().lower()
    if len(v) < 3:
        return False
    return v not in {"none", "nil", "no", "na", "n/a", "nothing", "-", "--", "nope", "no idea"}


def derive_priorities(answers: dict) -> list[dict]:
    """
    Turn intake answers into the two or three things worth tackling first.

    Deliberately **qualitative — no calorie or macro numbers.** Those are the paid
    deliverable, and handing them over here would answer the client's question
    entirely and remove the reason to book a call. What this does instead is prove
    their answers were read: it quotes what they said back at them and names the
    mechanism. That earns the conversation.

    Rules are ordered by how much they actually change an outcome, and only the
    top three fire. A screen full of concerns reads as alarming rather than
    competent.
    """
    found: list[dict] = []

    def add(title: str, because: str, weight: int) -> None:
        found.append({"title": title, "because": because, "_w": weight})

    # --- Safety first, and phrased so nobody feels shut out -----------------
    if answers.get("pregnant") == "yes":
        add("We'll involve your doctor before anything else",
            "You've said you're pregnant or breastfeeding. Requirements change a lot, and a "
            "fat-loss plan isn't appropriate right now — so the first step is coordinating "
            "with your doctor, not a diet.", 100)

    if _n(answers, "age") < 18:
        add("We'll build this around growth, not restriction",
            "You're under 18, so you're still growing and laying down bone. That means eating "
            "enough and training well — not dieting. It's a different plan, and honestly a "
            "more enjoyable one.", 99)

    if answers.get("eating_disorder_history") in ("yes", "prefer_not"):
        add("We'll go carefully, and not with calorie counting",
            "Thank you for telling me. Given that history I won't start you on tracking and a "
            "deficit, and I'd like a registered dietitian involved alongside me. That's the "
            "right way to do this, and it doesn't change whether I'll work with you.", 98)

    if _has_content(answers, "conditions"):
        add("Your plan gets built around your medical history",
            "You've mentioned a diagnosed condition. That genuinely changes what's safe — "
            "protein targets, carb timing and sodium all shift depending on what it is — so "
            "I'd want to work alongside your doctor rather than around them.", 95)

    # --- The things that most often decide whether a plan works -------------
    if _has_content(answers, "what_broke_it"):
        add("We start from what broke last time",
            "You told me what made you stop before, which is the most useful thing in this "
            "whole form. Almost nobody fails from bad numbers — they fail from a plan that "
            "didn't fit their life. That's the first thing I'll design around.", 90)

    sleep = _n(answers, "sleep_hours", 8)
    if 0 < sleep < 6.5 or answers.get("sleep_quality") == "poor":
        add("Sleep comes before any change to your food",
            f"{'You’re averaging under 7 hours' if 0 < sleep < 6.5 else 'You said you sleep badly'}"
            ", and that raises hunger hormones, lowers training performance and slows recovery. "
            "Fixing this will do more for you than any adjustment to your macros — so we'll "
            "treat it as part of the plan, not an excuse.", 85)

    if _has_content(answers, "injuries"):
        add("We program around your injury, not through it",
            "You've flagged something that hurts or used to. Most plans ignore this and then "
            "aggravate it. I'll pick exercises that train the same muscle without loading the "
            "thing that complains.", 82)

    if answers.get("stress") == "high":
        add("We start gentler than you probably expect",
            "You've said stress is high. A steep deficit on top of that is how people burn out "
            "and quit in week three. Starting smaller isn't going easy on you — it's the "
            "version that still exists in month six.", 78)

    # --- Diet-specific, using the same knowledge base as the calculator ------
    diet = answers.get("diet")
    tea = _n(answers, "tea_coffee")
    if diet in ("vegetarian", "vegan", "eggetarian") and tea >= 3:
        add("Your chai timing is probably costing you iron",
            f"You're {diet if diet != 'eggetarian' else 'eggetarian'} and drinking around "
            f"{int(tea)} cups of tea or coffee a day. Tannins block iron absorption, and plant "
            "iron is poorly absorbed to begin with. Moving chai an hour away from meals is "
            "free, takes no willpower, and often fixes unexplained tiredness.", 75)
    elif diet == "vegan":
        add("A few nutrients need planning on a vegan diet",
            "B12 has no reliable plant source, and calcium, iron, omega-3 and zinc all need "
            "deliberate attention rather than luck. This is very workable — it just needs to be "
            "designed rather than assumed.", 72)
    elif diet in ("vegetarian", "eggetarian"):
        add("We'll be deliberate about protein and iron",
            "A vegetarian diet can absolutely support building muscle — it just needs planning, "
            "because plant protein is less concentrated and plant iron is absorbed less "
            "readily. Dal, paneer, curd and soya will do the work.", 65)

    # --- Practical fit ------------------------------------------------------
    if answers.get("who_cooks") in ("family", "mess", "help"):
        add("Your plan has to work with the food already being cooked",
            "Someone else cooks for you, so a plan that assumes you control every meal is "
            "useless. I'll build it around what's already on the table, with small changes "
            "rather than a separate menu.", 70)

    if _has_content(answers, "fasting"):
        add("Your fasting and festival days get planned in, not ignored",
            "You've told me about fasting or religious food practices. These are completely "
            "plannable — but only when I know in advance. Most plans quietly break every "
            "festival and the client assumes they failed.", 68)

    if _has_content(answers, "dislikes"):
        add("Nothing you hate is going in your plan",
            "You've listed food you don't want to eat, and I'll take that seriously. There's "
            "always another option with the same numbers — filling a plan with food you dread "
            "is the fastest way to make you quit.", 62)

    if answers.get("eat_out") in ("often", "daily"):
        add("Eating out gets built in rather than banned",
            "You eat out regularly, so I'll plan for it instead of pretending it won't happen. "
            "Restaurant food is mostly hidden oil, and there are simple ways to order around that.", 60)

    if answers.get("tracking_ok") == "no":
        add("We'll do this with portions, not a food scale",
            "You'd rather not log food — that's completely fine, and it's a legitimate way to "
            "coach. Portion-based plans work; they're just a little less precise, so we lean "
            "more on the weekly weight trend.", 58)

    if answers.get("gym_access") in ("home_bodyweight", "none"):
        add("We build with what you've actually got",
            "You don't have full gym access, so there's no point in a machine-heavy programme. "
            "Plenty of progress is available with very little equipment when the progression is "
            "designed properly.", 55)

    if answers.get("work_type") == "shift":
        add("Shift work changes meal timing, so we'll design for it",
            "Working nights or rotating shifts disrupts appetite, sleep and training energy. "
            "It needs a plan built for your actual clock rather than a standard "
            "breakfast-lunch-dinner template.", 74)

    if answers.get("experience") in ("none", "under1"):
        add("You're at the best point for fast progress",
            "Early on, you can build muscle and lose fat at the same time — something that gets "
            "much harder later. It's worth using that window properly instead of rushing into "
            "an aggressive diet.", 50)

    if _n(answers, "sessions_per_week") and _n(answers, "sessions_per_week") <= 2:
        add("Two or three good sessions is enough to start",
            "You've been honest about the time you have, which I'd much rather know now. A "
            "programme built for your real week beats an ideal one you can't finish.", 48)

    found.sort(key=lambda p: -p["_w"])
    return [{"title": p["title"], "because": p["because"]} for p in found[:3]]


def closing_message(answers: dict) -> dict:
    """The last screen — thanks, what happens next, and the reason to talk."""
    name = (answers.get("full_name") or "").strip().split(" ")[0] or "there"
    return {
        "heading": f"Thanks, {name} — that's genuinely useful.",
        "body": (
            "I've read all of it. Below is what stood out to me straight away, before I've "
            "even worked out your numbers.\n\n"
            "Your actual calorie and macro targets, your training programme and the "
            "week-by-week plan are what we'll go through together — those depend on the things "
            "I want to ask you about in person, and on how your body responds over the first "
            "few weeks. That's the part a calculator can't do."
        ),
        "next_steps": [
            "I'll go through your answers properly and build your starting numbers.",
            "We'll talk through the plan together, so you understand every number in it — not just what to eat.",
            "You'll get a written plan with the reasoning included, and we adjust it from your real results.",
        ],
    }


def flatten_fields() -> list[dict]:
    """Every field across all sections, in questionnaire order."""
    return [f for section in SECTIONS for f in section["fields"]]


def label_for_answer(field: dict, raw) -> str:
    """
    The human-readable form of one stored answer.

    Stored values for radio and select fields are machine keys ("very_hot",
    "basic_gym"). Anywhere a person reads an answer — the coach's view, an export,
    a printout — it has to show the label the client actually saw, or it reads
    like a database dump.
    """
    if raw is None or str(raw).strip() == "":
        return ""
    if field.get("options"):
        match = next((o for o in field["options"] if o["value"] == raw), None)
        if match:
            return match["label"]
    text = str(raw)
    return f"{text} {field['unit']}" if field.get("unit") else text


def to_csv(answers: dict, *, meta: dict | None = None) -> str:
    """
    One submission as CSV — question, answer, and which section it came from.

    Long-form, one row per question, rather than one wide row per client. A coach
    exporting this is handing it to a dietitian or filing it for a single person,
    so readability beats being able to stack many clients in a spreadsheet.

    Built with the `csv` module rather than string joins so an answer containing a
    comma, quote or newline (very likely — most of these are free text) can't
    corrupt the file.
    """
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

    writer.writerow(["Section", "Question", "Answer"])
    for section in SECTIONS:
        for field in section["fields"]:
            value = label_for_answer(field, answers.get(field["key"]))
            if value:
                writer.writerow([section["title"], field["label"], value])

    # Any answer whose question has since been removed or renamed. Without this,
    # editing the questionnaire would silently drop data a client already gave.
    known = {f["key"] for f in flatten_fields()}
    for key, value in answers.items():
        if key not in known and str(value).strip():
            writer.writerow(["Other (question since changed)", key, str(value)])

    if meta:
        writer.writerow([])
        for label, value in meta.items():
            writer.writerow(["Record", label, value])

    return buf.getvalue()

