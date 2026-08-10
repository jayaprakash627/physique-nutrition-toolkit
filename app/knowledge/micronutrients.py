"""
micronutrients.py — the vitamin & mineral panel.

The part almost every macro calculator skips. Macros decide how you look; micros
decide whether you feel like a functioning human while getting there. Deep cuts
are exactly when intake falls (less food = fewer micronutrients) and needs rise
(more sweat, more training stress) — the worst possible combination, and nobody
warns clients about it.

Two reference sets per nutrient, deliberately shown side by side:
  * ICMR-NIN 2020 — the Indian RDA. Several values are HIGHER than Western ones
    (iron, zinc) because a cereal-and-pulse diet is high in phytates, which block
    absorption. Same nutrient, different food matrix, different requirement.
  * IOM/WHO/EFSA — the Western reference, so the gap is visible rather than
    hidden behind one "official" number.

Where they differ we show both and say why. A coach can then make a judgement
instead of trusting one table blindly.

Values are adult, non-pregnant, non-lactating. Pregnancy and lactation change
several of these substantially — that is a clinical conversation, and the app
says so rather than printing a number.

Field reference
    key                stable id; matches the `micros` tags in foods.py
    name, unit, group  display + which panel section it lands in
    icmr / western     {male, female} targets, or None where no Indian RDA is set
    what_it_does       the physiology, plain English
    why_short          why athletes and dieters specifically fall short
    deficiency_signs   what a client would actually notice
    upper_limit        the safe ceiling, and what happens past it
    athlete_note       the training-specific angle
    risk_tags          which client profiles get flagged for this nutrient
    source_keys        keys into sources.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
#  THE PANEL
# ---------------------------------------------------------------------------

MICRONUTRIENTS: list[dict] = [

    # ===== The big four for Indian lifters ================================
    {
        "key": "vitamin_d",
        "name": "Vitamin D",
        "unit": "IU/day",
        "group": "priority",
        "icmr": {"male": 600, "female": 600},
        "western": {"male": 600, "female": 600},
        "note_on_targets": "ICMR-NIN 2020 and the US DRI agree at 600 IU "
                           "(15 µg). Many clinicians target higher when blood "
                           "levels are already low — that is a decision for a "
                           "doctor with a test result, not a calculator.",
        "what_it_does": "Acts more like a hormone than a vitamin. It controls how "
                        "much calcium you absorb from food (without it you absorb "
                        "only ~10–15%), regulates bone remodelling, supports immune "
                        "function, and there are vitamin D receptors in muscle "
                        "tissue itself — low levels are associated with reduced "
                        "strength and slower recovery.",
        "why_short": "This is the single most common deficiency in urban India, "
                     "despite the sunshine — because people work indoors, cover up "
                     "outdoors, use sunscreen, and darker skin needs longer sun "
                     "exposure to make the same amount. Very few foods contain it "
                     "naturally, and Indian diets are low in oily fish. Studies "
                     "regularly report deficiency in 70–90% of Indian adults.",
        "deficiency_signs": [
            "Deep muscle and bone aching, often in the lower back, hips and thighs",
            "Unexplained fatigue that sleep doesn't fix",
            "Frequent infections, especially respiratory",
            "Reduced strength and slower recovery between sessions",
            "Long term: soft bones (osteomalacia), higher fracture and stress-fracture risk",
        ],
        "upper_limit": "4000 IU/day without medical supervision. Vitamin D is fat-"
                       "soluble and accumulates — very high doses cause "
                       "hypercalcaemia (nausea, kidney damage, calcification). "
                       "Weekly mega-doses should only be taken on medical advice.",
        "athlete_note": "One of the few worth actually testing (25-hydroxyvitamin D "
                        "blood test) rather than guessing, because deficiency is "
                        "common, symptoms are vague, and it's cheap to correct. "
                        "15–20 minutes of midday sun on arms and legs helps, but is "
                        "rarely enough alone in a city routine.",
        "risk_tags": ["all", "indoor", "vegetarian", "vegan"],
        "source_keys": ["ICMR_NIN_2020", "VITD_ENDO", "NIH_ODS"],
    },
    {
        "key": "b12",
        "name": "Vitamin B12",
        "unit": "µg/day",
        "group": "priority",
        "icmr": {"male": 2.2, "female": 2.2},
        "western": {"male": 2.4, "female": 2.4},
        "note_on_targets": "ICMR-NIN 2020 sets 2.2 µg; the US DRI is 2.4 µg. "
                           "Effectively the same target — the difference is "
                           "smaller than the error in any food table.",
        "what_it_does": "Needed to make red blood cells (which carry oxygen to your "
                        "muscles), to build and maintain the myelin sheath insulating "
                        "your nerves, and for DNA synthesis. It also clears "
                        "homocysteine, a compound linked to cardiovascular risk when "
                        "it builds up.",
        "why_short": "B12 is made by bacteria, and in practice reaches us almost "
                     "entirely through animal foods — meat, fish, eggs and dairy. "
                     "Plants contain essentially none. India has one of the world's "
                     "highest rates of B12 deficiency because of widespread "
                     "vegetarianism. Absorption also needs stomach acid and intrinsic "
                     "factor, so it drops with age and with long-term antacid use.",
        "deficiency_signs": [
            "Tiredness and breathlessness from megaloblastic anaemia",
            "Tingling, pins and needles or numbness in hands and feet",
            "Brain fog, poor memory, low mood, irritability",
            "Sore or swollen tongue, mouth ulcers",
            "Left untreated, nerve damage can become permanent — this one is worth acting on early",
        ],
        "upper_limit": "No established upper limit — it's water-soluble and excess "
                       "is excreted. High-dose oral supplements are routinely used "
                       "to correct deficiency.",
        "athlete_note": "If you're vegetarian or vegan, treat a B12 supplement as "
                        "non-negotiable rather than optional. Dairy contributes some "
                        "(a glass of milk ≈ 1.2 µg), so lacto-vegetarians do better "
                        "than vegans, but hitting the target on dairy alone takes "
                        "more milk and curd than most people eat. Stores last years, "
                        "so deficiency creeps in slowly and gets noticed late.",
        "risk_tags": ["vegetarian", "vegan", "older"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS", "IOM_MICRO"],
    },
    {
        "key": "iron",
        "name": "Iron",
        "unit": "mg/day",
        "group": "priority",
        "icmr": {"male": 19, "female": 29},
        "western": {"male": 8, "female": 18},
        "note_on_targets": "The biggest ICMR–Western gap in the whole panel, and "
                           "it isn't an error. Indian RDAs are far higher because "
                           "iron from a cereal-and-pulse diet is poorly absorbed: "
                           "phytates in grains and pulses, tannins in tea and "
                           "coffee, and calcium in dairy all block it. Same "
                           "biology, much less absorbable food.",
        "what_it_does": "The core of haemoglobin, which carries oxygen in your blood, "
                        "and of myoglobin, which stores oxygen in muscle. It's also "
                        "part of the enzymes that produce ATP. Low iron means less "
                        "oxygen delivered per heartbeat — endurance and work capacity "
                        "fall directly.",
        "why_short": "Menstruating women lose iron monthly, which is why their RDA is "
                     "much higher. Athletes lose more through sweat, gut microbleeding "
                     "and foot-strike haemolysis, and hard training raises hepcidin, "
                     "which further reduces absorption. Vegetarians get non-haem iron, "
                     "absorbed at roughly 2–10% versus 15–35% for haem iron from meat.",
        "deficiency_signs": [
            "Unusual fatigue and breathlessness during sets that used to feel easy",
            "Pale skin, pale inner eyelids, brittle nails, hair shedding",
            "Cold hands and feet; dizziness on standing",
            "Poor endurance and a noticeably higher heart rate at the same effort",
            "Restless legs; unusual cravings for ice or clay (pica)",
        ],
        "upper_limit": "45 mg/day from supplements. Iron is genuinely dangerous in "
                       "excess: it accumulates and damages liver, heart and pancreas "
                       "(haemochromatosis). Never supplement iron 'just in case' — "
                       "test ferritin first. Iron overdose is a leading cause of "
                       "poisoning in children, so store it out of reach.",
        "athlete_note": "Two practical absorption levers, both free. Pair non-haem "
                        "iron with vitamin C — lemon on your dal, or an orange with "
                        "your meal — which can multiply absorption several times "
                        "over. And keep tea and coffee at least an hour away from "
                        "iron-rich meals, because tannins block it. Cast-iron "
                        "cookware genuinely adds iron to food.",
        "risk_tags": ["vegetarian", "vegan", "female", "endurance", "deep_cut"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS", "IOM_MICRO"],
    },
    {
        "key": "calcium",
        "name": "Calcium",
        "unit": "mg/day",
        "group": "priority",
        "icmr": {"male": 1000, "female": 1000},
        "western": {"male": 1000, "female": 1000},
        "note_on_targets": "ICMR-NIN raised the Indian RDA to 1000 mg in 2020, "
                           "matching the US DRI. Adults over 50 and "
                           "post-menopausal women are usually advised 1200 mg.",
        "what_it_does": "Beyond bone — and 99% of it is in bone — calcium is what "
                        "makes muscle fibres actually contract. Every rep you perform "
                        "is calcium being released inside muscle cells. It also drives "
                        "nerve signalling, blood clotting and heart rhythm.",
        "why_short": "Blood calcium is defended so tightly that if intake is low, your "
                     "body dissolves bone to maintain it — so you feel nothing while "
                     "losing bone density for years. Dairy-avoiders and vegans are "
                     "most at risk. High sweat losses add up: hard training can cost "
                     "a meaningful amount of calcium in sweat, and low calcium plus "
                     "low energy availability is a documented stress-fracture risk.",
        "deficiency_signs": [
            "Usually silent for years — the first sign is often a fracture",
            "Muscle cramps and twitches, tingling around the mouth and fingers",
            "Weak, brittle nails",
            "Long term: osteopenia and osteoporosis, higher stress-fracture risk while training",
        ],
        "upper_limit": "2000–2500 mg/day. Excess raises kidney-stone risk and, from "
                       "high-dose supplements specifically, has been linked to "
                       "arterial calcification. Food sources don't carry the same "
                       "concern — get it from food where you can.",
        "athlete_note": "Calcium is useless without vitamin D, which controls its "
                        "absorption — treat the two as a pair. Vegans should look at "
                        "ragi (finger millet), sesame/til, almonds, tofu set with "
                        "calcium, and fortified plant milks. Ragi is one of the "
                        "richest plant sources available in India.",
        "risk_tags": ["vegan", "no_dairy", "female", "deep_cut"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS", "IFCT_2017"],
    },

    # ===== Minerals =======================================================
    {
        "key": "magnesium",
        "name": "Magnesium",
        "unit": "mg/day",
        "group": "mineral",
        "icmr": {"male": 440, "female": 370},
        "western": {"male": 400, "female": 310},
        "note_on_targets": "ICMR-NIN 2020 sets slightly higher values than the US "
                           "DRI. Both are comfortably reachable from whole grains, "
                           "millets, dal, nuts and greens.",
        "what_it_does": "A cofactor in over 300 enzyme reactions — including every "
                        "single one that uses ATP, which is to say every muscle "
                        "contraction you make. It also relaxes muscle (calcium "
                        "contracts, magnesium releases), supports nerve function, "
                        "insulin sensitivity, and deep sleep.",
        "why_short": "Refining grains strips most of the magnesium out, so a diet "
                     "built on white rice and refined flour runs low. Athletes lose "
                     "more in sweat and urine, and hard training increases "
                     "requirements. It's one of the most commonly under-consumed "
                     "minerals worldwide.",
        "deficiency_signs": [
            "Muscle cramps, twitching eyelids, restless legs",
            "Poor sleep quality and trouble switching off after evening training",
            "Fatigue and general weakness",
            "Irritability and anxiety",
            "Severe deficiency: irregular heart rhythm",
        ],
        "upper_limit": "350 mg/day from supplements (food isn't capped). Excess "
                       "supplemental magnesium causes diarrhoea — magnesium oxide "
                       "is the worst offender; citrate and glycinate are gentler.",
        "athlete_note": "The classic 'I keep cramping' nutrient — though cramps are "
                        "usually a mix of magnesium, sodium, potassium and hydration "
                        "rather than magnesium alone. Switching some white rice for "
                        "millets (bajra, jowar, ragi) and adding a daily handful of "
                        "nuts usually fixes intake without a supplement.",
        "risk_tags": ["all", "heavy_sweater", "deep_cut"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS", "IFCT_2017"],
    },
    {
        "key": "zinc",
        "name": "Zinc",
        "unit": "mg/day",
        "group": "mineral",
        "icmr": {"male": 17, "female": 13},
        "western": {"male": 11, "female": 8},
        "note_on_targets": "Indian RDAs are higher for the same reason as iron: "
                           "phytates in cereals and pulses bind zinc and reduce "
                           "absorption, so more must be eaten to absorb the same "
                           "amount.",
        "what_it_does": "Required for protein synthesis and cell division — literally "
                        "the process of building new muscle tissue. Also central to "
                        "immune function, wound healing, and testosterone production. "
                        "Around 300 enzymes depend on it.",
        "why_short": "Lost in sweat, so heavy trainers in hot climates lose more. "
                     "Vegetarian diets provide less and absorb it less well. Deep "
                     "cuts reduce total intake. High-dose iron supplements compete "
                     "with zinc for absorption.",
        "deficiency_signs": [
            "Frequent colds and infections; wounds and cuts healing slowly",
            "Hair loss, acne, skin problems",
            "Reduced appetite and blunted sense of taste or smell",
            "Low testosterone symptoms in men — low libido, poor recovery",
        ],
        "upper_limit": "40 mg/day. Chronic high-dose zinc causes copper deficiency "
                       "(they compete for absorption), nausea and reduced immune "
                       "function. More is not better here — the supplement industry's "
                       "'zinc boosts testosterone' claim only holds if you were "
                       "deficient to begin with.",
        "athlete_note": "Soaking, sprouting and fermenting pulses and grains reduces "
                        "phytate and meaningfully improves zinc (and iron) "
                        "absorption. This is why idli and dosa batter is fermented "
                        "and why sprouted moong is nutritionally better than boiled "
                        "— traditional Indian cooking already solved this.",
        "risk_tags": ["vegetarian", "vegan", "heavy_sweater", "deep_cut"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS"],
    },
    {
        "key": "potassium",
        "name": "Potassium",
        "unit": "mg/day",
        "group": "electrolyte",
        "icmr": {"male": 3500, "female": 3500},
        "western": {"male": 3400, "female": 2600},
        "note_on_targets": "WHO recommends at least 3510 mg/day for adults. The US "
                           "AI is sex-specific (3400 mg men, 2600 mg women). Most "
                           "people fall short of all of these.",
        "what_it_does": "The main electrolyte inside your cells, working against "
                        "sodium outside them. That sodium–potassium gradient is what "
                        "lets nerves fire and muscles contract. It also lowers blood "
                        "pressure by helping the kidneys excrete sodium, and helps "
                        "store glycogen in muscle.",
        "why_short": "Potassium comes mostly from fruit, vegetables, pulses and "
                     "tubers — the first foods to shrink when someone cuts calories "
                     "or 'cuts carbs'. It's also lost in sweat. Most modern diets sit "
                     "well below the target while sitting well above the sodium one, "
                     "which is exactly the wrong ratio.",
        "deficiency_signs": [
            "Muscle weakness, cramps and fatigue",
            "Flat-feeling muscles and poor pumps despite eating carbs",
            "Higher blood pressure",
            "Severe deficiency (usually from illness or diuretics): heart-rhythm disturbance",
        ],
        "upper_limit": "No upper limit from food in healthy people — kidneys excrete "
                       "the excess. Supplements are capped low for good reason, and "
                       "anyone with kidney disease or on ACE inhibitors/ARBs or "
                       "potassium-sparing diuretics must not supplement without "
                       "medical advice: high blood potassium can be fatal.",
        "athlete_note": "Cramping mid-session is more often sodium and fluid than "
                        "potassium, but chronic low potassium makes it worse. Banana, "
                        "coconut water, curd, potato, sweet potato, rajma and palak "
                        "all move the needle. Coconut water is a genuinely good, "
                        "cheap post-training electrolyte drink in Indian summer.",
        "risk_tags": ["all", "deep_cut", "heavy_sweater", "low_carb"],
        "source_keys": ["WHO_POTASSIUM", "ICMR_NIN_2020", "NIH_ODS"],
    },
    {
        "key": "sodium",
        "name": "Sodium",
        "unit": "mg/day",
        "group": "electrolyte",
        "icmr": {"male": 2000, "female": 2000},
        "western": {"male": 2300, "female": 2300},
        "note_on_targets": "This is the one nutrient in the panel that is a CEILING "
                           "for most people and a FLOOR for heavy sweaters. WHO "
                           "advises under 2000 mg/day (5 g salt) for general "
                           "health, but an athlete losing 1–2 L of sweat per "
                           "session can lose 500–1500 mg in that session alone and "
                           "genuinely needs more. Both facts are true; which "
                           "applies depends on you.",
        "what_it_does": "The main electrolyte outside your cells. It controls fluid "
                        "balance and blood volume, and with potassium enables every "
                        "nerve impulse and muscle contraction. It's also what lets "
                        "you actually absorb and retain the water you drink.",
        "why_short": "Rarely short in a normal diet — Indian diets are typically well "
                     "above the WHO ceiling from salt, pickles, papad and packaged "
                     "food. The exception matters though: people on very clean "
                     "'no-salt' prep diets who also train hard in the heat can end up "
                     "genuinely sodium-depleted, and feel terrible for it.",
        "deficiency_signs": [
            "Cramping during or after long, sweaty sessions",
            "Dizziness or light-headedness on standing, especially in the heat",
            "Headache, nausea and unusual fatigue after training",
            "Flat, weak-feeling training despite eating enough carbs",
        ],
        "upper_limit": "WHO: under 2000 mg/day for the general population. Chronic "
                       "excess raises blood pressure, cardiovascular and stroke risk, "
                       "and in India is linked to high rates of hypertension. Cut "
                       "pickles, papad, packaged snacks and restaurant food before "
                       "cutting the salt in home cooking.",
        "athlete_note": "Do not fear salt around training if you sweat heavily. A "
                        "pinch of salt with lemon in your water, or an ORS sachet "
                        "after a long hot session, is sensible practice — not a "
                        "diet failure. Sodium is also why very-low-carb dieters feel "
                        "awful in week one: low insulin makes kidneys dump sodium, "
                        "and the 'keto flu' is mostly that.",
        "risk_tags": ["heavy_sweater", "low_carb", "contest_prep"],
        "source_keys": ["WHO_SODIUM", "ACSM_HYDRATION", "ICMR_NIN_2020"],
    },
    {
        "key": "iodine",
        "name": "Iodine",
        "unit": "µg/day",
        "group": "mineral",
        "icmr": {"male": 150, "female": 150},
        "western": {"male": 150, "female": 150},
        "note_on_targets": "150 µg/day for adults, both references agreeing. "
                           "India's universal salt-iodisation programme means most "
                           "people meet this through iodised salt alone.",
        "what_it_does": "The raw material for thyroid hormones (T3 and T4), which set "
                        "your metabolic rate. No iodine means no thyroid hormone, "
                        "which means a slower metabolism and every symptom that "
                        "follows.",
        "why_short": "Mostly a solved problem thanks to iodised salt — but it comes "
                     "back for people who switch to rock salt, pink Himalayan or sea "
                     "salt (mostly not iodised) while also cutting salt overall, "
                     "which is a common combination in prep diets.",
        "deficiency_signs": [
            "Fatigue, weight gain, feeling cold, dry skin — the classic low-thyroid picture",
            "Goitre (visible thyroid swelling in the neck)",
            "Brain fog and low mood",
            "In pregnancy: serious risk to the baby's brain development",
        ],
        "upper_limit": "1100 µg/day. Excess iodine can itself cause thyroid "
                       "dysfunction — kelp and seaweed supplements can massively "
                       "overshoot, so they're not a casual purchase.",
        "athlete_note": "If you've switched to non-iodised gourmet salt, check you're "
                        "getting iodine from somewhere else — dairy, eggs and fish "
                        "all contribute. Chronic dieting already lowers T3; there's "
                        "no reason to add an iodine shortfall to it.",
        "risk_tags": ["contest_prep", "vegan"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS"],
    },

    # ===== Fats & vitamins ================================================
    {
        "key": "omega3",
        "name": "Omega-3 (EPA + DHA)",
        "unit": "mg/day",
        "group": "priority",
        "icmr": None,
        "western": {"male": 500, "female": 500},
        "note_on_targets": "EFSA advises 250–500 mg/day combined EPA + DHA for "
                           "adults; we use 500 mg as an athlete-facing target. "
                           "ICMR-NIN sets a total fat and essential-fatty-acid "
                           "recommendation rather than a specific EPA/DHA number, "
                           "so there's no direct Indian RDA to show.",
        "what_it_does": "EPA and DHA are built into cell membranes and produce the "
                        "signalling molecules that resolve inflammation. That's the "
                        "training link: recovery isn't about blocking inflammation "
                        "(you need it to adapt) but about switching it off cleanly "
                        "afterwards. DHA is also a major structural fat in the brain "
                        "and retina.",
        "why_short": "Indian diets are typically heavy in omega-6 (sunflower, "
                     "safflower, groundnut oil) and light in omega-3, pushing the "
                     "ratio far from ideal. Vegetarian sources — flax, chia, walnuts "
                     "— provide ALA, and your body converts only about 5–10% of ALA "
                     "to EPA and far less to DHA, so plant sources alone rarely reach "
                     "the target.",
        "deficiency_signs": [
            "Dry skin, dry eyes, rough patches on the backs of the arms",
            "Joint stiffness and aching; slower recovery between hard sessions",
            "Low mood and poor concentration",
            "Not a dramatic clinical deficiency in most people — more a slow drift toward worse recovery",
        ],
        "upper_limit": "Up to about 3000 mg/day EPA+DHA is generally considered "
                       "safe. Very high doses thin the blood — relevant before "
                       "surgery or alongside blood thinners.",
        "athlete_note": "One of the few supplements with a genuine case for "
                        "vegetarians and vegans: algae-derived DHA/EPA is the only "
                        "plant source that supplies them directly. Omnivores can hit "
                        "it with two servings a week of oily fish — Indian sardines "
                        "(bangda), surmai and rohu all count and are far cheaper "
                        "than salmon.",
        "risk_tags": ["vegetarian", "vegan", "all"],
        "source_keys": ["EFSA_OMEGA3", "NIH_ODS", "ICMR_NIN_2020"],
    },
    {
        "key": "vitamin_a",
        "name": "Vitamin A",
        "unit": "µg RAE/day",
        "group": "vitamin",
        "icmr": {"male": 1000, "female": 840},
        "western": {"male": 900, "female": 700},
        "note_on_targets": "ICMR-NIN 2020 sets 1000 µg RAE for men and 840 µg for "
                           "women — above the US DRI, partly because much Indian "
                           "vitamin A comes as plant beta-carotene, which converts "
                           "inefficiently to retinol.",
        "what_it_does": "Vision — especially adapting to low light — plus immune "
                        "function, skin and mucous-membrane health, and cell "
                        "differentiation. It's fat-soluble, so you need dietary fat "
                        "in the same meal to absorb it.",
        "why_short": "Very-low-fat diets impair absorption even when intake looks "
                     "fine on paper. Beta-carotene from vegetables converts to active "
                     "retinol at a poor and variable rate, so a plant-only intake "
                     "needs to be considerably higher.",
        "deficiency_signs": [
            "Poor night vision — the earliest and most specific sign",
            "Dry, gritty eyes; dry, rough skin",
            "Frequent infections",
            "Severe deficiency is a leading cause of preventable childhood blindness worldwide",
        ],
        "upper_limit": "3000 µg/day of preformed retinol (from animal foods and "
                       "supplements). Excess is toxic — liver damage, bone loss, hair "
                       "loss — and is seriously teratogenic in pregnancy. "
                       "Beta-carotene from vegetables does not carry this risk; the "
                       "body just stops converting it, which is why heavy carrot "
                       "eaters go slightly orange rather than getting ill.",
        "athlete_note": "The clearest everyday example of why fat isn't optional: "
                        "carrots, palak and papaya cooked with a spoon of ghee or oil "
                        "deliver far more usable vitamin A than the same vegetables "
                        "boiled plain.",
        "risk_tags": ["low_fat", "deep_cut"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS", "IFCT_2017"],
    },
    {
        "key": "vitamin_c",
        "name": "Vitamin C",
        "unit": "mg/day",
        "group": "vitamin",
        "icmr": {"male": 80, "female": 65},
        "western": {"male": 90, "female": 75},
        "note_on_targets": "ICMR-NIN 2020: 80 mg men, 65 mg women. US DRI: 90 and "
                           "75. Both are met by one guava or two oranges, so this "
                           "is rarely the binding constraint.",
        "what_it_does": "Builds collagen — the protein in tendons, ligaments, skin "
                        "and the connective tissue that transmits every bit of force "
                        "your muscles produce. It's also a water-soluble antioxidant, "
                        "supports immune function, and dramatically increases "
                        "absorption of plant (non-haem) iron.",
        "why_short": "Rarely deficient in India given the fruit and vegetables "
                     "available, but it's water-soluble and destroyed by prolonged "
                     "cooking — the long-simmered vegetable habit loses a lot. Needs "
                     "rise with training stress, smoking and illness.",
        "deficiency_signs": [
            "Bleeding or swollen gums; easy bruising",
            "Slow wound healing; tendon and joint niggles that linger",
            "Frequent infections, fatigue",
            "Severe deficiency is scurvy — rare, but still seen in extremely restricted diets",
        ],
        "upper_limit": "2000 mg/day. Past that: diarrhoea, stomach cramps, and a "
                       "higher kidney-stone risk in susceptible people. Very high-dose "
                       "antioxidant supplementation around training may actually blunt "
                       "adaptation, so mega-dosing is not a free win.",
        "athlete_note": "Use it as a tool, not just a nutrient: lemon squeezed over "
                        "dal or a citrus fruit alongside an iron-rich vegetarian meal "
                        "can multiply iron absorption several times over. Cheapest "
                        "nutrition upgrade in this entire panel.",
        "risk_tags": ["vegetarian", "vegan"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS"],
    },
    {
        "key": "vitamin_e",
        "name": "Vitamin E",
        "unit": "mg/day",
        "group": "vitamin",
        "icmr": {"male": 10, "female": 8},
        "western": {"male": 15, "female": 15},
        "note_on_targets": "ICMR-NIN 2020 sets 10 mg for men and 8 mg for women "
                           "(as α-tocopherol); the US DRI is 15 mg. Nuts, seeds and "
                           "vegetable oils cover it easily.",
        "what_it_does": "The main fat-soluble antioxidant in your cell membranes, "
                        "protecting the fats there — including your omega-3s — from "
                        "oxidative damage. Also supports immune function and prevents "
                        "the oxidation of LDL cholesterol.",
        "why_short": "Almost entirely a fat-soluble-absorption story: very-low-fat "
                     "diets and diets stripped of nuts, seeds and oils run short. "
                     "Otherwise uncommon.",
        "deficiency_signs": [
            "Genuine deficiency is rare outside fat-malabsorption conditions",
            "When it occurs: muscle weakness, coordination problems, nerve issues",
            "Weakened immune response",
        ],
        "upper_limit": "1000 mg/day from supplements. High-dose vitamin E thins the "
                       "blood and has been associated with worse outcomes in some "
                       "trials — a good reminder that antioxidant supplements are not "
                       "harmless by default.",
        "athlete_note": "A daily handful of almonds or peanuts, or cooking in "
                        "sunflower or groundnut oil, covers the requirement. If you're "
                        "supplementing omega-3, adequate vitamin E is what protects it "
                        "from going rancid inside you.",
        "risk_tags": ["low_fat"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS"],
    },
    {
        "key": "vitamin_k",
        "name": "Vitamin K",
        "unit": "µg/day",
        "group": "vitamin",
        "icmr": {"male": 55, "female": 55},
        "western": {"male": 120, "female": 90},
        "note_on_targets": "ICMR-NIN 2020 sets 55 µg; the US AI is 120 µg for men "
                           "and 90 for women. A katori of cooked palak clears any "
                           "of these several times over.",
        "what_it_does": "Two jobs. It activates the proteins that clot your blood — "
                        "the K is from the German *Koagulation*. And it activates "
                        "osteocalcin, which binds calcium into bone, so bone health "
                        "needs vitamin D, calcium AND vitamin K working together.",
        "why_short": "Uncommon in anyone eating green vegetables. Risk rises with "
                     "very-low-fat diets (it's fat-soluble), long antibiotic courses "
                     "(gut bacteria make some K2), and diets with almost no greens.",
        "deficiency_signs": [
            "Easy bruising; bleeding that takes longer to stop",
            "Nosebleeds, bleeding gums",
            "Long term: reduced bone mineralisation",
        ],
        "upper_limit": "No established upper limit from food. One critical "
                       "interaction: if you take warfarin, keep vitamin K intake "
                       "CONSISTENT rather than high or low, and coordinate with your "
                       "doctor — sudden changes in green-vegetable intake directly "
                       "affect the medication.",
        "athlete_note": "Palak, methi, coriander, mint and cabbage are all rich "
                        "sources — cook them with some fat to absorb it. Fermented "
                        "foods contribute K2, the form more associated with directing "
                        "calcium into bone rather than arteries.",
        "risk_tags": ["low_fat"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS", "IFCT_2017"],
    },
    {
        "key": "folate",
        "name": "Folate (B9)",
        "unit": "µg/day",
        "group": "vitamin",
        "icmr": {"male": 300, "female": 220},
        "western": {"male": 400, "female": 400},
        "note_on_targets": "ICMR-NIN 2020: 300 µg men, 220 µg women. The US DRI is "
                           "400 µg. Anyone who could become pregnant is advised "
                           "400 µg plus a supplement — that is a medical "
                           "recommendation, not a training one.",
        "what_it_does": "Needed to make DNA and to divide cells, so it's essential "
                        "wherever cells turn over fast — red blood cells especially. "
                        "It works with B12; a shortage of either causes the same type "
                        "of anaemia.",
        "why_short": "Folate is destroyed by heat, so long cooking times cut it "
                     "sharply. Diets low in greens, pulses and fruit run short. Deep "
                     "cuts that squeeze out vegetables squeeze out folate.",
        "deficiency_signs": [
            "Fatigue and breathlessness from anaemia",
            "Mouth ulcers and a sore tongue",
            "Poor concentration, irritability",
            "In pregnancy: serious risk of neural tube defects — which is why supplementation is standard advice",
        ],
        "upper_limit": "1000 µg/day from supplements and fortified food. High "
                       "supplemental folate can mask a B12 deficiency — it fixes the "
                       "anaemia while nerve damage quietly continues. Get them "
                       "checked together, not one alone.",
        "athlete_note": "Lightly cooked or raw greens, sprouts, dal and citrus cover "
                        "it. Sprouting increases folate — another point for sprouted "
                        "moong over boiled.",
        "risk_tags": ["deep_cut", "vegan"],
        "source_keys": ["ICMR_NIN_2020", "NIH_ODS"],
    },
]

BY_KEY = {m["key"]: m for m in MICRONUTRIENTS}


# ---------------------------------------------------------------------------
#  RISK PROFILING
#
#  Rather than dumping all 15 nutrients with equal weight, the app works out
#  which ones THIS client is actually likely to be short on, and pushes those to
#  the top. That is the difference between a reference table and advice.
# ---------------------------------------------------------------------------

RISK_DEFINITIONS = {
    "vegetarian": {
        "label": "Vegetarian diet",
        "why": "No meat or fish means no haem iron and no natural B12, and omega-3 "
               "arrives only as ALA, which converts poorly to the EPA and DHA your "
               "body actually uses.",
        "watch": ["b12", "iron", "omega3", "zinc", "vitamin_d"],
    },
    "vegan": {
        "label": "Vegan diet",
        "why": "Everything in the vegetarian list, plus no dairy — so calcium and "
               "B12 both lose their main dietary source. B12 supplementation is not "
               "optional on a vegan diet.",
        "watch": ["b12", "iron", "calcium", "omega3", "zinc", "vitamin_d", "iodine"],
    },
    "no_dairy": {
        "label": "Little or no dairy",
        "why": "Dairy is the dominant calcium source in most Indian diets. Without "
               "it, calcium needs deliberate planning through ragi, til, almonds and "
               "fortified alternatives.",
        "watch": ["calcium", "b12", "vitamin_d"],
    },
    "deep_cut": {
        "label": "Aggressive calorie deficit",
        "why": "This is the trap nobody warns clients about: less total food means "
               "fewer micronutrients, at exactly the point where training stress is "
               "raising your needs. A deep cut is when deficiencies appear.",
        "watch": ["iron", "calcium", "magnesium", "zinc", "potassium", "folate", "vitamin_a"],
    },
    "heavy_sweater": {
        "label": "Heavy sweating / hot climate training",
        "why": "Sweat carries out sodium, potassium, magnesium and zinc. Training "
               "hard in Indian heat can mean losing 1–2 litres per session, and the "
               "electrolytes go with it.",
        "watch": ["sodium", "potassium", "magnesium", "zinc"],
    },
    "female": {
        "label": "Menstruating",
        "why": "Monthly blood loss roughly doubles iron requirements — the ICMR-NIN "
               "RDA is 29 mg versus 19 mg for men. Iron deficiency is the most "
               "common nutrient deficiency in female athletes worldwide.",
        "watch": ["iron", "calcium", "vitamin_d"],
    },
    "low_carb": {
        "label": "Low carbohydrate intake",
        "why": "Fruit, tubers and pulses are the main potassium sources, and they're "
               "the first things cut when carbs go down. Low insulin also makes the "
               "kidneys excrete more sodium.",
        "watch": ["potassium", "sodium", "magnesium", "fibre"],
    },
    "low_fat": {
        "label": "Very low fat intake",
        "why": "Vitamins A, D, E and K need dietary fat to be absorbed at all. On a "
               "very-low-fat diet you can eat them and still not get them.",
        "watch": ["vitamin_a", "vitamin_d", "vitamin_e", "vitamin_k", "omega3"],
    },
    "contest_prep": {
        "label": "Contest preparation",
        "why": "Prep stacks every risk factor at once: a long deep deficit, very "
               "low body fat, high training volume, heavy sweating, and often "
               "restricted food variety and salt.",
        "watch": ["sodium", "potassium", "iron", "calcium", "vitamin_d", "magnesium", "zinc", "iodine"],
    },
    "indoor": {
        "label": "Mostly indoors",
        "why": "Vitamin D is made in skin exposed to sunlight. An indoor working day "
               "plus gym training after dark means very little of it, whatever the "
               "latitude.",
        "watch": ["vitamin_d"],
    },
}


def build_risk_profile(*, diet: str, sex: str, deficit_pct: float,
                       climate: str, training_hours: float,
                       goal: str, carb_g_per_kg: float,
                       fat_g_per_kg: float, contest_prep: bool = False) -> list[str]:
    """
    Decide which risk tags apply to this client.

    Deliberately rule-based and readable: a coach should be able to look at this
    function and see exactly why a flag appeared. Thresholds are conservative —
    it's better to surface a nutrient the client is fine on than to miss one they
    aren't.
    """
    tags: list[str] = []

    if diet == "vegan":
        tags += ["vegan", "no_dairy"]
    elif diet == "vegetarian":
        tags.append("vegetarian")
    elif diet == "eggetarian":
        tags.append("vegetarian")   # still no haem iron or fish-source omega-3

    if sex == "female":
        tags.append("female")

    # A deficit past ~22% of maintenance is where food volume starts genuinely
    # squeezing micronutrient intake.
    if goal == "cut" and deficit_pct >= 22:
        tags.append("deep_cut")

    if climate in ("hot", "very_hot") or training_hours >= 1.5:
        tags.append("heavy_sweater")

    if carb_g_per_kg < 2.0:
        tags.append("low_carb")

    if fat_g_per_kg < 0.7:
        tags.append("low_fat")

    if contest_prep:
        tags.append("contest_prep")

    # Assume an indoor working day — true for most clients, and the cost of a
    # false positive is one extra vitamin D card.
    tags.append("indoor")

    return sorted(set(tags))


def panel_for(risk_tags: list[str], sex: str) -> list[dict]:
    """
    Build the ordered micronutrient panel for one client.

    Every nutrient is returned — a coach should be able to see the whole panel —
    but each carries a `priority` and the list of `flagged_by` reasons, so the UI
    can lead with what matters for this person.
    """
    tagset = set(risk_tags)
    out = []

    for m in MICRONUTRIENTS:
        # Which of the client's risk factors call out this nutrient?
        flagged_by = [
            RISK_DEFINITIONS[t]["label"]
            for t in risk_tags
            if t in RISK_DEFINITIONS and m["key"] in RISK_DEFINITIONS[t]["watch"]
        ]
        # A nutrient tagged "all" is one everybody should see regardless.
        universal = "all" in m.get("risk_tags", [])

        if flagged_by:
            priority = "high" if len(flagged_by) >= 2 else "watch"
        elif universal:
            priority = "watch"
        else:
            priority = "standard"

        icmr = m["icmr"]
        western = m["western"]
        out.append({
            "key": m["key"],
            "name": m["name"],
            "unit": m["unit"],
            "group": m["group"],
            "priority": priority,
            "flagged_by": flagged_by,
            "target_icmr": icmr[sex] if icmr else None,
            "target_western": western[sex] if western else None,
            "note_on_targets": m["note_on_targets"],
            "what_it_does": m["what_it_does"],
            "why_short": m["why_short"],
            "deficiency_signs": m["deficiency_signs"],
            "upper_limit": m["upper_limit"],
            "athlete_note": m["athlete_note"],
            "source_keys": m["source_keys"],
        })

    # High-priority first, then watch, then the rest — stable within each band so
    # the panel order doesn't jump around between requests.
    rank = {"high": 0, "watch": 1, "standard": 2}
    out.sort(key=lambda m: rank[m["priority"]])
    return out
