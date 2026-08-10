"""
sources.py — the citation registry.

Every number this app prints has to be traceable to a published standard.
Rather than scattering "(ISSN 2017)" strings through the code, each source gets
one entry here with a short key, and the rest of the app refers to it by key.

Why do it this way?
  * One place to verify. A nutritionist can read this file alone and check that
    the standards we lean on are the right ones.
  * If a body updates its guidance (ICMR-NIN did in 2020), we edit one entry and
    every explanation that cites it updates with it.
  * The frontend renders `label` as a citation chip and links to `url`.

Keys are short and stable — treat them as an API. `cite("ISSN_PROTEIN")` in a
knowledge file resolves at request time via `resolve()`.
"""

# ---------------------------------------------------------------------------
#  The registry.
#  org   — who published it (the authority a coach would name)
#  label — short human-readable citation for the UI chip
#  title — what the document actually is
#  url   — where to read it
#  note  — why we use it / what it covers, in plain language
# ---------------------------------------------------------------------------

SOURCES: dict[str, dict] = {
    # ---- Protein & macronutrients ----------------------------------------
    "ISSN_PROTEIN": {
        "org": "ISSN",
        "label": "ISSN Position Stand: Protein & Exercise (2017)",
        "title": "International Society of Sports Nutrition Position Stand: protein and exercise",
        "url": "https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0177-8",
        "note": "The reference standard for athlete protein intake. Source of the "
                "1.4–2.0 g/kg general range and the 2.3–3.1 g/kg fat-free mass "
                "recommendation for lifters in a calorie deficit.",
    },
    "ISSN_DIET": {
        "org": "ISSN",
        "label": "ISSN Position Stand: Diets & Body Composition (2017)",
        "title": "ISSN Position Stand: diets and body composition",
        "url": "https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0174-y",
        "note": "Reviews how different macronutrient splits affect body "
                "composition. Backs the 'set protein and fat first, carbs fill "
                "the rest' ordering used here.",
    },
    "HELMS_NATURAL": {
        "org": "Helms et al.",
        "label": "Helms et al. (2014) — Natural Bodybuilding Contest Prep",
        "title": "Evidence-based recommendations for natural bodybuilding contest "
                 "preparation: nutrition and supplementation",
        "url": "https://jissn.biomedcentral.com/articles/10.1186/1550-2783-11-20",
        "note": "The peer-reviewed contest-prep paper. Source of the safe rate of "
                "loss (~0.5–1.0% bodyweight/week), the fat floor of ~15–20% of "
                "calories, and protein at the high end while dieting.",
    },
    "ACSM_ENERGY": {
        "org": "ACSM / AND / DC",
        "label": "ACSM Joint Position Stand: Nutrition & Athletic Performance (2016)",
        "title": "Nutrition and Athletic Performance — Joint Position Statement",
        "url": "https://journals.lww.com/acsm-msse/fulltext/2016/03000/nutrition_and_athletic_performance.25.aspx",
        "note": "American College of Sports Medicine consensus on energy "
                "availability, carbohydrate needs by training load, and "
                "hydration for athletes.",
    },
    "IOM_MACRO": {
        "org": "IOM / NASEM",
        "label": "IOM Dietary Reference Intakes — Macronutrients (2005)",
        "title": "DRIs for Energy, Carbohydrate, Fibre, Fat, Fatty Acids, "
                 "Cholesterol, Protein and Amino Acids",
        "url": "https://nap.nationalacademies.org/catalog/10490",
        "note": "Origin of the Acceptable Macronutrient Distribution Ranges "
                "(fat 20–35% of calories, carbs 45–65%) and the 14 g fibre per "
                "1000 kcal rule used for the fibre target.",
    },
    "WHO_FATS": {
        "org": "WHO",
        "label": "WHO Guideline: Total Fat Intake (2023)",
        "title": "WHO guideline on total fat intake for the prevention of "
                 "unhealthy weight gain",
        "url": "https://www.who.int/publications/i/item/9789240073654",
        "note": "WHO recommends total fat at or below 30% of energy, with a "
                "shift toward unsaturated sources. Used as the upper anchor on "
                "the fat range.",
    },

    # ---- Energy expenditure ----------------------------------------------
    "MIFFLIN": {
        "org": "Mifflin & St Jeor",
        "label": "Mifflin–St Jeor (1990)",
        "title": "A new predictive equation for resting energy expenditure in "
                 "healthy individuals",
        "url": "https://academic.oup.com/ajcn/article-abstract/51/2/241/4695104",
        "note": "The most accurate general-population BMR equation in validation "
                "studies. Uses total bodyweight, so it cannot see body "
                "composition — that is why we also run Katch–McArdle.",
    },
    "KATCH_MCARDLE": {
        "org": "Katch & McArdle",
        "label": "Katch–McArdle / Cunningham lean-mass BMR",
        "title": "Katch-McArdle resting metabolic rate from fat-free mass",
        "url": "https://pubmed.ncbi.nlm.nih.gov/7361681/",
        "note": "Predicts BMR from lean body mass alone. Better for trained "
                "lifters, whose lean mass is far above what bodyweight-only "
                "equations assume.",
    },

    # ---- Body composition -------------------------------------------------
    "NAVY_TAPE": {
        "org": "U.S. Navy / Hodgdon & Beckett",
        "label": "U.S. Navy circumference method (Hodgdon & Beckett, 1984)",
        "title": "Prediction of percent body fat for U.S. Navy men and women "
                 "from body circumferences and height",
        "url": "https://apps.dtic.mil/sti/citations/ADA143890",
        "note": "Tape-measure body fat. Needs only a tape, so it is the most "
                "repeatable field method — but it infers fat from girths, so it "
                "misreads very lean or very muscular people.",
    },
    "JACKSON_POLLOCK_M": {
        "org": "Jackson & Pollock",
        "label": "Jackson & Pollock (1978) — men, skinfolds",
        "title": "Generalized equations for predicting body density of men",
        "url": "https://pubmed.ncbi.nlm.nih.gov/718832/",
        "note": "Skinfold-to-body-density regressions for men (3-site and "
                "7-site). Accurate in trained hands; error grows fast with "
                "sloppy calliper technique.",
    },
    "JACKSON_POLLOCK_W": {
        "org": "Jackson, Pollock & Ward",
        "label": "Jackson, Pollock & Ward (1980) — women, skinfolds",
        "title": "Generalized equations for predicting body density of women",
        "url": "https://pubmed.ncbi.nlm.nih.gov/7402053/",
        "note": "The female counterpart to the 1978 men's equations, with "
                "different sites and coefficients.",
    },
    "SIRI": {
        "org": "Siri",
        "label": "Siri equation (1961)",
        "title": "Body composition from fluid spaces and density",
        "url": "https://pubmed.ncbi.nlm.nih.gov/8286893/",
        "note": "Converts body density into body-fat percent: %BF = 495/Db − 450. "
                "Assumes fixed densities for fat and lean tissue, which is where "
                "part of the skinfold error comes from.",
    },
    "DEURENBERG": {
        "org": "Deurenberg et al.",
        "label": "Deurenberg et al. (1991) — BMI-based body fat",
        "title": "Body mass index as a measure of body fatness: age- and "
                 "sex-specific prediction formulas",
        "url": "https://pubmed.ncbi.nlm.nih.gov/2043597/",
        "note": "Estimates body fat from BMI, age and sex. Included as a "
                "sanity check only — it cannot distinguish muscle from fat, so "
                "it systematically over-reads lifters.",
    },
    "KOURI_FFMI": {
        "org": "Kouri et al.",
        "label": "Kouri et al. (1995) — FFMI in athletes",
        "title": "Fat-free mass index in users and non-users of "
                 "anabolic-androgenic steroids",
        "url": "https://pubmed.ncbi.nlm.nih.gov/7496846/",
        "note": "The study behind the often-quoted FFMI ~25 'natural ceiling'. "
                "Read it as a population observation, not a hard biological "
                "limit for any one person.",
    },
    "ACE_BODYFAT": {
        "org": "ACE / ACSM",
        "label": "ACE & ACSM body-fat reference ranges",
        "title": "Body composition classification norms",
        "url": "https://www.acefitness.org/resources/everyone/tools-calculators/percent-body-fat-calculator/",
        "note": "Population ranges for essential fat, athletic, fitness and "
                "average categories — different floors for men and women.",
    },
    "WHTR": {
        "org": "NICE",
        "label": "NICE CG189 — Waist-to-height ratio",
        "title": "Obesity: identification, assessment and management",
        "url": "https://www.nice.org.uk/guidance/ng246",
        "note": "Supports keeping waist under half your height as a simple "
                "central-adiposity screen, independent of BMI.",
    },

    # ---- Fibre, water, electrolytes --------------------------------------
    "WHO_FIBRE": {
        "org": "WHO",
        "label": "WHO Guideline: Carbohydrate Intake (2023)",
        "title": "WHO guideline on carbohydrate intake for adults and children",
        "url": "https://www.who.int/publications/i/item/9789240073593",
        "note": "WHO recommends at least 25 g/day of naturally occurring dietary "
                "fibre for adults, from whole grains, vegetables, fruit and pulses.",
    },
    "EFSA_WATER": {
        "org": "EFSA",
        "label": "EFSA Dietary Reference Values for Water (2010)",
        "title": "Scientific opinion on dietary reference values for water",
        "url": "https://www.efsa.europa.eu/en/efsajournal/pub/1459",
        "note": "Adequate total water intake of 2.5 L/day for men and 2.0 L/day "
                "for women in a temperate climate, before adding sweat losses.",
    },
    "ACSM_HYDRATION": {
        "org": "ACSM",
        "label": "ACSM Position Stand: Exercise & Fluid Replacement (2007)",
        "title": "American College of Sports Medicine position stand: exercise "
                 "and fluid replacement",
        "url": "https://pubmed.ncbi.nlm.nih.gov/17277604/",
        "note": "Source of the '2% bodyweight loss measurably impairs "
                "performance' figure and of per-hour sweat-replacement guidance.",
    },
    "WHO_SODIUM": {
        "org": "WHO",
        "label": "WHO Guideline: Sodium Intake (2023)",
        "title": "WHO guideline: sodium intake for adults and children",
        "url": "https://www.who.int/publications/i/item/9789240073432",
        "note": "Under 2000 mg sodium (5 g salt) per day for general adults. "
                "Athletes losing salt in sweat sit above this — which is why the "
                "app flags sodium rather than capping it.",
    },
    "WHO_POTASSIUM": {
        "org": "WHO",
        "label": "WHO Guideline: Potassium Intake (2012)",
        "title": "Guideline: potassium intake for adults and children",
        "url": "https://www.who.int/publications/i/item/9789241504829",
        "note": "At least 3510 mg/day potassium for adults, to blunt the blood-"
                "pressure effect of sodium.",
    },

    # ---- Micronutrients ---------------------------------------------------
    "ICMR_NIN_2020": {
        "org": "ICMR-NIN",
        "label": "ICMR-NIN RDA for Indians (2020)",
        "title": "Nutrient Requirements for Indians — Recommended Dietary "
                 "Allowances and Estimated Average Requirements",
        "url": "https://www.nin.res.in/RDA_short_Report_2020.html",
        "note": "The Indian national reference. Matters here because several "
                "values differ from Western DRIs — Indian iron and zinc RDAs are "
                "higher to account for the low bioavailability of a "
                "cereal- and pulse-based diet.",
    },
    "IFCT_2017": {
        "org": "ICMR-NIN",
        "label": "Indian Food Composition Tables (IFCT, 2017)",
        "title": "Indian Food Composition Tables 2017",
        "url": "https://www.nin.res.in/ebooks/IFCT2017.pdf",
        "note": "Nutrient values for Indian foods — dal, roti, paneer, curd and "
                "the rest. The food portions in this app are rounded from IFCT "
                "and USDA entries.",
    },
    "NIH_ODS": {
        "org": "NIH ODS",
        "label": "NIH Office of Dietary Supplements — Fact Sheets",
        "title": "Vitamin and mineral fact sheets for health professionals",
        "url": "https://ods.od.nih.gov/factsheets/list-all/",
        "note": "Used for function, deficiency signs and upper limits for each "
                "vitamin and mineral in the micronutrient panel.",
    },
    "IOM_MICRO": {
        "org": "IOM / NASEM",
        "label": "IOM Dietary Reference Intakes — Vitamins & Minerals",
        "title": "DRI tables for vitamins, minerals and electrolytes",
        "url": "https://www.nationalacademies.org/our-work/summary-report-of-the-dietary-reference-intakes",
        "note": "The Western reference set, shown alongside ICMR-NIN so the "
                "difference between the two is visible rather than hidden.",
    },
    "EFSA_OMEGA3": {
        "org": "EFSA",
        "label": "EFSA — EPA & DHA Dietary Reference Values (2010)",
        "title": "Scientific opinion on dietary reference values for fats",
        "url": "https://www.efsa.europa.eu/en/efsajournal/pub/1461",
        "note": "250–500 mg/day combined EPA + DHA for adult cardiovascular "
                "health. The basis of the omega-3 target.",
    },
    "VITD_ENDO": {
        "org": "Endocrine Society",
        "label": "Endocrine Society — Vitamin D Guideline",
        "title": "Evaluation, treatment and prevention of vitamin D deficiency",
        "url": "https://academic.oup.com/jcem/article/96/7/1911/2833671",
        "note": "Clinical guidance on vitamin D status and repletion. Cited "
                "because vitamin D deficiency is very common in urban India "
                "despite the latitude.",
    },

    # ---- Strength ---------------------------------------------------------
    "EPLEY": {
        "org": "Epley",
        "label": "Epley (1985) — 1RM estimate",
        "title": "Poundage chart, Boyd Epley Workout",
        "url": "https://en.wikipedia.org/wiki/One-repetition_maximum",
        "note": "1RM = w × (1 + reps/30). Identical to Brzycki at exactly 10 "
                "reps; returns the higher estimate below 10 reps and the lower "
                "one above.",
    },
    "BRZYCKI": {
        "org": "Brzycki",
        "label": "Brzycki (1993) — 1RM estimate",
        "title": "Strength testing: predicting a one-rep max from reps to fatigue",
        "url": "https://www.tandfonline.com/doi/abs/10.1080/07303084.1993.10606684",
        "note": "1RM = w × 36/(37 − reps). The mirror of Epley: lower below 10 "
                "reps, higher above. Showing both brackets the true value.",
    },
    "IPF_DOTS": {
        "org": "IPF / DOTS",
        "label": "DOTS scoring coefficients",
        "title": "DOTS — bodyweight-adjusted strength score",
        "url": "https://en.wikipedia.org/wiki/Wilks_coefficient",
        "note": "Modern replacement for Wilks. Normalises a total against "
                "bodyweight so lifters in different weight classes compare "
                "fairly.",
    },
    "WILKS": {
        "org": "Wilks",
        "label": "Wilks coefficient (1994)",
        "title": "Wilks formula for powerlifting totals",
        "url": "https://en.wikipedia.org/wiki/Wilks_coefficient",
        "note": "The long-standing federation standard. Included alongside DOTS "
                "because most historical meet results are recorded in Wilks.",
    },

    # ---- Safety -----------------------------------------------------------
    "RED_S": {
        "org": "IOC",
        "label": "IOC Consensus: RED-S (2018)",
        "title": "Relative Energy Deficiency in Sport (RED-S) consensus update",
        "url": "https://bjsm.bmj.com/content/52/11/687",
        "note": "What goes wrong when energy intake stays too low for too long: "
                "hormonal, bone, immune and performance consequences. The basis "
                "of this app's deficit-depth warnings.",
    },
    "NEDA_SCREEN": {
        "org": "NEDA",
        "label": "National Eating Disorders Association",
        "title": "Screening, warning signs and support resources",
        "url": "https://www.nationaleatingdisorders.org/",
        "note": "Referenced when a requested target crosses into territory that "
                "needs a clinician rather than a calculator.",
    },
}


def resolve(*keys: str) -> list[dict]:
    """
    Turn source keys into full citation dicts for the API response.

    Unknown keys are skipped rather than raising: a typo in a knowledge file
    should never take down a whole assessment. `validate_keys()` (below) is the
    place that catches those, and it runs in the test suite.
    """
    out = []
    for k in keys:
        src = SOURCES.get(k)
        if src:
            out.append({"key": k, **src})
    return out


def validate_keys(keys: list[str]) -> list[str]:
    """Return any keys that are not in the registry — used by tests."""
    return [k for k in keys if k not in SOURCES]


# The blanket disclaimer. Shown in the UI header, on every report, and on the
# printable summary. Deliberately kept in the knowledge layer so it travels with
# the content rather than living only in the HTML.
DISCLAIMER = (
    "This toolkit produces population-level estimates for education and "
    "coaching support. It is not medical advice, diagnosis or treatment. Every "
    "formula here carries real error bars, and no equation can see your health "
    "history, medication, bloodwork or training context. Talk to a doctor or a "
    "registered dietitian before making significant changes — especially if you "
    "are pregnant or breastfeeding, under 18, managing a medical condition such "
    "as diabetes or kidney or thyroid disease, or have any history of disordered "
    "eating."
)

SAFEGUARDING_NOTE = (
    "This tool will not help you pursue a target that is likely to harm you. If "
    "food or bodyweight feels like it is taking over, that is worth talking to "
    "someone about — a GP, a registered dietitian, or a helpline. That is a "
    "sign of how much you care, not a weakness."
)
