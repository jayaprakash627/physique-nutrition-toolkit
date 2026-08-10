"""
explanations.py — the "Why this number?" content.

This is the actual product. Anyone can compute 1.8 g/kg × bodyweight; the reason
clients abandon plans is that nobody ever told them what protein *does*, what
breaks when fat goes too low, or why carbs get whatever calories are left over.

Every builder here returns the same shape, so the frontend renders one component
for all of them:

    {
      "id":            stable id for the UI panel
      "title":         nutrient name
      "headline":      one line a client remembers ("Fat is not optional.")
      "why_this_much": the reasoning for *this* client's number, with their
                       own figures woven in
      "what_it_does":  [{label, text}]  — the physiology, one job per card
      "too_little":    [str]            — what goes wrong on the low side
      "too_much":      [str]            — what goes wrong on the high side
      "source_keys":   [str]            — keys into knowledge/sources.py
    }

The text is deliberately written the way a good coach talks: plain words first,
the technical term in brackets after. "Your body builds muscle by stitching
amino acids into new muscle protein (muscle protein synthesis)" — not the
reverse.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
#  PROTEIN
# ---------------------------------------------------------------------------

def protein(ctx: dict) -> dict:
    """
    ctx keys: grams, g_per_kg_bw, g_per_kg_lbm, lbm_kg, goal, deficit_pct,
              kcal, pct_kcal, in_issn_range (bool)
    """
    goal = ctx["goal"]
    g = ctx["grams"]

    # The reasoning changes meaningfully by goal, so each gets its own paragraph
    # rather than one generic sentence with the goal name swapped in.
    if goal == "cut":
        why = (
            f"Your target is {g} g/day — that's {ctx['g_per_kg_lbm']} g for every "
            f"kg of your {ctx['lbm_kg']} kg of lean mass, or "
            f"{ctx['g_per_kg_bw']} g/kg of bodyweight.\n\n"
            "We set it from your lean mass, not your total weight, because fat "
            "tissue doesn't need feeding — muscle does. Two people at 80 kg with "
            "very different body fat need very different amounts of protein, and "
            "a bodyweight-only number gets one of them wrong.\n\n"
            "It's set at the high end on purpose. You're eating fewer calories "
            "than you burn, so your body is actively looking for tissue to break "
            "down for energy. High protein is the single strongest signal telling "
            "it to take that energy from fat and leave the muscle alone. In a "
            "deficit protein isn't a bonus — it's the thing protecting what you "
            "built."
        )
    elif goal == "bulk":
        why = (
            f"Your target is {g} g/day — {ctx['g_per_kg_lbm']} g per kg of your "
            f"{ctx['lbm_kg']} kg of lean mass ({ctx['g_per_kg_bw']} g/kg "
            "bodyweight).\n\n"
            "Set from lean mass rather than total weight, because it's the "
            "muscle you already carry that determines how much raw material you "
            "need to add more.\n\n"
            "Notice it's a little lower than a cutting target. That's not a "
            "typo. In a calorie surplus you have plenty of energy coming in, so "
            "your body isn't hunting for muscle to burn, and the extra carbs and "
            "fat spare protein for its actual job — building. Past roughly "
            "2 g/kg, more protein doesn't build more muscle; it just displaces "
            "the training fuel that drives the sessions doing the building."
        )
    else:
        why = (
            f"Your target is {g} g/day — {ctx['g_per_kg_lbm']} g per kg of your "
            f"{ctx['lbm_kg']} kg of lean mass ({ctx['g_per_kg_bw']} g/kg "
            "bodyweight).\n\n"
            "Set from lean mass, not total weight, because fat tissue doesn't "
            "need protein — muscle does.\n\n"
            "At maintenance this amount covers daily repair with room to spare, "
            "keeps you full, and means that if you later shift into a cut or a "
            "bulk you're not starting from a deficit of raw material."
        )

    issn_note = (
        "This sits inside the ISSN's recommended 1.6–2.2 g/kg bodyweight range "
        "for people training to build or keep muscle."
        if ctx.get("in_issn_range")
        else
        f"At {ctx['g_per_kg_bw']} g/kg bodyweight this sits outside the ISSN's "
        "headline 1.6–2.2 g/kg band. That's expected when body fat is high or "
        "very low — the number is driven by your lean mass, which is the more "
        "meaningful reference. The bodyweight figure is shown for comparison, "
        "not as the target."
    )
    why += "\n\n" + issn_note

    return {
        "id": "protein",
        "title": "Protein",
        "headline": "The raw material. In a deficit, it's what protects the muscle you built.",
        "why_this_much": why,
        "what_it_does": [
            {
                "label": "Builds and repairs muscle",
                "text": "Training damages muscle fibres; protein supplies the amino "
                        "acids your body stitches into new muscle protein (muscle "
                        "protein synthesis). Leucine, from animal protein, dairy and "
                        "soy, is the amino acid that flips the switch on. No amino "
                        "acids available means the repair happens slowly or not at "
                        "all — the session was wasted.",
            },
            {
                "label": "Protects muscle while dieting",
                "text": "In a calorie deficit your body will break down tissue for "
                        "energy. High protein plus resistance training is the "
                        "strongest evidence-backed way to steer that loss toward fat "
                        "and away from muscle. This is the reason protein goes UP, "
                        "not down, when calories go down.",
            },
            {
                "label": "Keeps you full",
                "text": "Protein is the most satiating macronutrient — it triggers "
                        "the fullness hormones (GLP-1, PYY, CCK) more strongly than "
                        "carbs or fat. Practically: the same calories eaten as "
                        "protein leave you less hungry, which is the difference "
                        "between a diet you can hold and one you quit in week three.",
            },
            {
                "label": "Costs calories to digest",
                "text": "About 20–30% of protein's calories are burnt just digesting "
                        "and processing it (the thermic effect of food), versus "
                        "5–10% for carbs and 0–3% for fat. A high-protein diet "
                        "quietly gives you a slightly larger real deficit for the "
                        "same food logged.",
            },
            {
                "label": "Runs everything else too",
                "text": "Enzymes, antibodies, haemoglobin, hair, skin, nails and "
                        "connective tissue are all protein. Muscle is the visible "
                        "part of a much longer list.",
            },
        ],
        "too_little": [
            "Muscle loss while dieting — you get smaller rather than leaner, and "
            "the scale rewards you for it.",
            "Slower recovery: sessions start to feel harder at the same weights, "
            "and soreness lingers.",
            "Constant hunger, because the most filling macronutrient is the one "
            "you're short on.",
            "Below roughly 0.8 g/kg long term: weakened immune function, poor "
            "wound healing, thinning hair and nails.",
        ],
        "too_much": [
            "Mostly a crowding-out problem, not a toxicity one — every extra "
            "protein calorie is a carb or fat calorie you didn't get, so training "
            "fuel and hormone support suffer.",
            "Above ~3 g/kg with an appetite already suppressed, hitting fibre and "
            "micronutrient targets gets genuinely hard.",
            "High protein raises water needs, because clearing nitrogen through "
            "the kidneys costs fluid. In healthy kidneys high protein is well "
            "tolerated; with existing kidney disease it needs medical supervision.",
        ],
        "source_keys": ["ISSN_PROTEIN", "HELMS_NATURAL", "ACSM_ENERGY", "ICMR_NIN_2020"],
    }


# ---------------------------------------------------------------------------
#  FAT
# ---------------------------------------------------------------------------

def fat(ctx: dict) -> dict:
    """
    ctx keys: grams, g_per_kg_bw, pct_kcal, floor_g, floor_pct, below_floor (bool),
              kcal
    """
    g = ctx["grams"]
    why = (
        f"Your target is {g} g/day — {ctx['pct_kcal']}% of your calories, or "
        f"{ctx['g_per_kg_bw']} g per kg of bodyweight.\n\n"
        "Fat gets set second, right after protein, and before carbs. That order "
        "matters: fat is the macronutrient with a hard biological floor, so it "
        "gets claimed early rather than being whatever happens to be left.\n\n"
        f"Your floor is about {ctx['floor_g']} g/day (the higher of 0.5 g/kg "
        f"bodyweight and {ctx['floor_pct']}% of calories). Below that, the "
        "problems in the next panel start showing up — and they show up as "
        "hormones and recovery, which you feel weeks before you'd ever see it in "
        "the mirror."
    )
    if ctx.get("below_floor"):
        why += (
            "\n\n⚠ Your current inputs push fat under that floor. The plan has "
            "raised fat back to the floor and taken the difference out of carbs. "
            "If that leaves carbs too low to train on, the honest fix is a "
            "smaller deficit — not less fat."
        )

    return {
        "id": "fat",
        "title": "Fat",
        "headline": "Not optional. Your hormones are built from it.",
        "why_this_much": why,
        "what_it_does": [
            {
                "label": "Builds your hormones",
                "text": "Cholesterol — which your body makes from dietary fat — is "
                        "the backbone of every steroid hormone, testosterone and "
                        "oestrogen included. Studies cutting dietary fat sharply "
                        "show measurable drops in testosterone. For a lifter that "
                        "is the opposite of the goal: less drive, worse recovery, "
                        "flatter sessions.",
            },
            {
                "label": "Unlocks vitamins A, D, E and K",
                "text": "These four are fat-soluble: without fat in the same meal "
                        "they pass through you largely unabsorbed. You can eat a "
                        "perfect salad and absorb very little of it. This is why a "
                        "spoon of ghee or oil on your vegetables is function, not "
                        "indulgence.",
            },
            {
                "label": "Builds every cell membrane",
                "text": "Every cell in your body is wrapped in a membrane made of "
                        "fat. Membrane quality affects how well cells signal — "
                        "including how well muscle cells respond to insulin and "
                        "carry glucose in.",
            },
            {
                "label": "Supplies fats you cannot make",
                "text": "Omega-3 (ALA, EPA, DHA) and omega-6 (linoleic acid) are "
                        "'essential' in the literal sense: your body cannot "
                        "synthesise them, so they have to be eaten. Omega-3 in "
                        "particular drives the anti-inflammatory side of recovery, "
                        "and most Indian diets run heavy on omega-6 and light on "
                        "omega-3.",
            },
            {
                "label": "Protects your joints and organs",
                "text": "Structural fat cushions organs, insulates nerves (the "
                        "myelin sheath is largely fat) and supports joint health — "
                        "which matters when you're loading heavy.",
            },
        ],
        "too_little": [
            "Falling testosterone and oestrogen. In women, low fat plus a large "
            "deficit is a common driver of lost or irregular periods — a warning "
            "sign, not a side effect to accept.",
            "Deficiency in vitamins A, D, E and K even when the food you eat "
            "contains them, because absorption fails without fat.",
            "Dry skin, brittle hair, feeling cold constantly, mood and libido "
            "dropping.",
            "Worse recovery: inflammation stays up longer between sessions.",
        ],
        "too_much": [
            "No direct harm from fat itself, but it's the most calorie-dense "
            "macronutrient (9 kcal/g), so it's the easiest way to blow past your "
            "calorie target without noticing.",
            "Above ~35–40% of calories, carbs usually get squeezed enough that "
            "high-intensity training quality drops.",
            "WHO advises total fat at or below 30% of energy for the general "
            "population, with a shift away from saturated fat toward unsaturated "
            "sources — nuts, seeds, fish and vegetable oils over excess ghee and "
            "fried food.",
        ],
        "source_keys": ["IOM_MACRO", "WHO_FATS", "HELMS_NATURAL", "EFSA_OMEGA3", "ISSN_DIET"],
    }


# ---------------------------------------------------------------------------
#  CARBOHYDRATE
# ---------------------------------------------------------------------------

def carbs(ctx: dict) -> dict:
    """
    ctx keys: grams, g_per_kg_bw, pct_kcal, kcal, goal, low_warning (bool),
              training_days
    """
    g = ctx["grams"]
    why = (
        f"Your target is {g} g/day — {ctx['pct_kcal']}% of your calories, or "
        f"{ctx['g_per_kg_bw']} g per kg of bodyweight.\n\n"
        "Carbs come last, and they get whatever calories are left after protein "
        "and fat. That isn't because they matter least — it's because they're the "
        "macronutrient with the widest safe range. Protein has a job nothing else "
        "can do, and fat has a hard floor. Carbs can flex from low to very high "
        "without breaking anything, so they're the right lever to absorb the "
        "adjustment.\n\n"
        "Think of it as the fuel tank: you fix the engine parts first, then fill "
        "the tank with whatever room is left."
    )
    if ctx.get("low_warning"):
        why += (
            "\n\n⚠ At this level carbs are low for someone lifting hard. Expect "
            "flatter-looking muscles, fewer reps at the same weight, and worse "
            "session quality — especially on your heaviest days. If training is "
            "suffering, shrink the deficit or shift some fat calories to carbs on "
            "training days."
        )

    return {
        "id": "carbs",
        "title": "Carbohydrate",
        "headline": "Training fuel. This is what makes the hard sets possible.",
        "why_this_much": why,
        "what_it_does": [
            {
                "label": "Fuels hard training",
                "text": "Sets in the 6–20 rep range run mostly on glycogen — carbs "
                        "stored in muscle. Fat can't be burnt fast enough to power "
                        "that intensity. Low glycogen shows up as losing your last "
                        "two reps and blaming motivation.",
            },
            {
                "label": "Fills the muscle out",
                "text": "Every gram of glycogen pulls roughly 3 g of water into the "
                        "muscle with it. That's why muscles look full and hard after "
                        "carbs and flat after a low-carb week — a large chunk of "
                        "'looking better' after a refeed is this, not fat loss.",
            },
            {
                "label": "Spares protein",
                "text": "With carbs available your body burns them for energy and "
                        "leaves amino acids free for repair. Strip carbs too far and "
                        "your body converts protein to glucose "
                        "(gluconeogenesis) — expensive protein doing a cheap "
                        "carbohydrate's job.",
            },
            {
                "label": "Keeps hormones and mood steady",
                "text": "Chronically low carbs and a chronic deficit lower leptin "
                        "(the 'I have enough energy' signal) and can reduce active "
                        "thyroid hormone (T3), which shows up as feeling cold, flat, "
                        "irritable and unable to recover. A deliberate higher-carb "
                        "day helps, and this is why long diets need planned breaks.",
            },
            {
                "label": "Feeds your brain",
                "text": "Your brain prefers glucose. The 'diet brain fog' most "
                        "people describe on very low carbs is real, and it's a "
                        "training risk when you're under a loaded bar.",
            },
        ],
        "too_little": [
            "Strength and endurance drop first — usually the last few reps of "
            "each set go missing.",
            "Muscles look flat as glycogen and the water it holds leave.",
            "Chronically low: reduced T3 and leptin, cold hands and feet, low "
            "mood, disrupted sleep, lost periods in women.",
            "More muscle loss in a deficit, because protein gets diverted to "
            "making glucose.",
        ],
        "too_much": [
            "Nothing harmful about carbs themselves — excess calories are what "
            "cause fat gain, from any macronutrient.",
            "Very high carbs with very low fat risks pushing fat under its floor. "
            "Fat's floor is protected first.",
            "Mostly refined sources (sugar, white flour, sweets) at the expense "
            "of whole grains, pulses, fruit and vegetables costs you fibre and "
            "micronutrients even when the gram total is right. Source matters, "
            "not just quantity.",
        ],
        "source_keys": ["ACSM_ENERGY", "IOM_MACRO", "ISSN_DIET", "WHO_FIBRE"],
    }


# ---------------------------------------------------------------------------
#  FIBRE
# ---------------------------------------------------------------------------

def fibre(ctx: dict) -> dict:
    """ctx keys: grams, kcal, per_1000_kcal"""
    return {
        "id": "fibre",
        "title": "Fibre",
        "headline": "The cheapest way to feel full on fewer calories.",
        "why_this_much": (
            f"Your target is {ctx['grams']} g/day.\n\n"
            f"That comes from the 14 g per 1000 kcal guideline — you're eating "
            f"{ctx['kcal']} kcal, so {ctx['per_1000_kcal']} g per 1000 kcal gives "
            f"{ctx['grams']} g. It's scaled to your intake rather than fixed, "
            "because fibre needs track how much food is moving through you.\n\n"
            "WHO puts the floor at 25 g/day for adults; the usual quoted range is "
            "25–38 g. Indian diets built on dal, whole grains, vegetables and "
            "fruit hit this easily — the ones that struggle are built on refined "
            "flour, white rice and packaged food."
        ),
        "what_it_does": [
            {
                "label": "Keeps you full while dieting",
                "text": "Fibre adds bulk and slows stomach emptying, so meals feel "
                        "bigger and last longer for the same calories. When you're "
                        "cutting, this is the difference between feeling fed and "
                        "feeling deprived.",
            },
            {
                "label": "Keeps digestion working",
                "text": "Insoluble fibre (wheat bran, vegetables, skins) adds bulk "
                        "and keeps things moving. Constipation is one of the most "
                        "common complaints in a cut, and low fibre plus low food "
                        "volume plus low water is almost always the cause.",
            },
            {
                "label": "Steadies blood sugar",
                "text": "Soluble fibre (oats, dal, beans, guava, apple) slows "
                        "glucose absorption, flattening the spike-and-crash that "
                        "drives cravings two hours after a refined-carb meal.",
            },
            {
                "label": "Lowers cholesterol",
                "text": "Soluble fibre binds bile acids in the gut and carries them "
                        "out, so your body pulls LDL cholesterol from the blood to "
                        "make more. A meaningful, food-only effect on heart-disease "
                        "risk.",
            },
            {
                "label": "Feeds your gut bacteria",
                "text": "Fibre is food for your gut microbiome. Those bacteria "
                        "ferment it into short-chain fatty acids like butyrate, "
                        "which feed the cells lining your colon and help regulate "
                        "inflammation and immune function.",
            },
        ],
        "too_little": [
            "Constipation, bloating and irregularity — the standard complaint in a "
            "deep cut.",
            "Hungrier at the same calories, because the food has less bulk.",
            "Bigger blood-sugar swings, and the cravings that follow them.",
            "Less diverse gut microbiome over time.",
        ],
        "too_much": [
            "Jumping suddenly to a high intake causes gas, bloating and cramping. "
            "Increase by about 5 g a week and let your gut adapt.",
            "Very high fibre (above ~50–60 g) can bind minerals — iron, zinc, "
            "calcium — and reduce absorption. Relevant if you're already at risk "
            "of low iron.",
            "Fibre without water makes constipation worse, not better. The two go "
            "together.",
        ],
        "source_keys": ["IOM_MACRO", "WHO_FIBRE", "ICMR_NIN_2020", "IFCT_2017"],
    }


# ---------------------------------------------------------------------------
#  WATER
# ---------------------------------------------------------------------------

def water(ctx: dict) -> dict:
    """
    ctx keys: total_ml, total_l, baseline_ml, training_ml, climate_ml,
              protein_ml, per_kg, training_hours, climate, weight_kg
    """
    lines = [
        f"Baseline {ctx['baseline_ml']} ml — {ctx['per_kg']} ml per kg of your "
        f"{ctx['weight_kg']} kg bodyweight",
    ]
    if ctx["training_ml"]:
        lines.append(
            f"+{ctx['training_ml']} ml for {ctx['training_hours']} h of training "
            "(roughly 500–750 ml per hour of sweat replacement)"
        )
    if ctx["climate_ml"]:
        lines.append(
            f"+{ctx['climate_ml']} ml for a {ctx['climate']} climate — sweat rate "
            "rises sharply in Indian heat and humidity"
        )
    if ctx["protein_ml"]:
        lines.append(
            f"+{ctx['protein_ml']} ml for your high protein intake — clearing "
            "nitrogen through the kidneys costs fluid"
        )

    return {
        "id": "water",
        "title": "Water",
        "headline": "A 2% drop in bodyweight from fluid loss measurably hurts performance.",
        "why_this_much": (
            f"Your target is about {ctx['total_l']} L/day ({ctx['total_ml']} ml), "
            "built up from:\n\n• " + "\n• ".join(lines) + "\n\n"
            "This is total fluid, and food counts — dal, curd, fruit, sabzi and "
            "chai all contribute. Use urine colour as your check: pale straw is "
            "the target, dark yellow means you're behind. Sipping steadily beats "
            "drinking a litre at once, which mostly just gets urinated out."
        ),
        "what_it_does": [
            {
                "label": "Protects performance",
                "text": "Losing just 2% of your bodyweight in fluid measurably "
                        "reduces strength, endurance and focus — that's only about "
                        "1.5 kg for an 75 kg lifter, easily lost in one hot session. "
                        "Weigh yourself before and after training: every kg lost is "
                        "roughly a litre of sweat to replace.",
            },
            {
                "label": "Moves nutrients around",
                "text": "Blood is mostly water. Dehydrated, blood volume falls, so "
                        "delivering glucose, amino acids and oxygen to working muscle "
                        "gets harder and your heart rate rises at the same effort.",
            },
            {
                "label": "Cushions joints and discs",
                "text": "Synovial fluid and spinal discs are water-based. Chronic "
                        "under-hydration is a mostly-invisible tax on joint comfort "
                        "under heavy squats and deadlifts.",
            },
            {
                "label": "Keeps you cool",
                "text": "Sweat evaporation is your only real cooling system. Too "
                        "little fluid and core temperature climbs, performance falls, "
                        "and in Indian summer heat exhaustion becomes a genuine risk.",
            },
            {
                "label": "Helps your kidneys handle high protein",
                "text": "Protein metabolism produces urea, which your kidneys excrete "
                        "in urine. High protein plus low water means concentrated "
                        "urine and a higher kidney-stone risk. Water is what makes a "
                        "high-protein diet comfortable.",
            },
        ],
        "too_little": [
            "Strength, endurance and concentration drop before you feel thirsty — "
            "thirst is a late signal.",
            "Headaches, fatigue, cramps and a higher heart rate at the same "
            "training load.",
            "Constipation, especially when fibre is high and water is not.",
            "Concentrated urine and higher kidney-stone risk on high protein.",
        ],
        "too_much": [
            "Drinking far beyond need dilutes blood sodium (hyponatraemia) — rare "
            "but genuinely dangerous. It shows up in endurance events where people "
            "drink litres of plain water while sweating out salt.",
            "If you're training long in the heat, replace electrolytes as well as "
            "water — a pinch of salt, lemon water, coconut water, curd, or ORS.",
            "Practical sign you've overshot: completely clear urine all day plus "
            "constant bathroom trips.",
        ],
        "source_keys": ["ACSM_HYDRATION", "EFSA_WATER", "ACSM_ENERGY", "WHO_SODIUM"],
    }


# ---------------------------------------------------------------------------
#  CALORIES / ENERGY
# ---------------------------------------------------------------------------

def calories(ctx: dict) -> dict:
    """
    ctx keys: target, tdee, bmr_used, bmr_method, delta, delta_pct, goal,
              rate_kg_per_week, rate_pct_bw
    """
    goal = ctx["goal"]
    if goal == "cut":
        head = "A deficit big enough to work, small enough to keep muscle."
        body = (
            f"Your maintenance (TDEE) is about {ctx['tdee']} kcal — that's what "
            "you burn on an average day, all in. Your target is "
            f"{ctx['target']} kcal, a deficit of {abs(ctx['delta'])} kcal "
            f"({ctx['delta_pct']}% below maintenance).\n\n"
            f"That should move you about {ctx['rate_kg_per_week']} kg/week "
            f"({ctx['rate_pct_bw']}% of bodyweight per week). The evidence-backed "
            "safe band for keeping muscle while losing fat is 0.5–1.0% of "
            "bodyweight per week. Faster is not better: past that, the extra loss "
            "comes increasingly from muscle, and hunger and fatigue rise faster "
            "than the results do.\n\n"
            "The maths behind it: roughly 7700 kcal is stored in a kilogram of "
            "body fat, so a 500 kcal daily deficit ≈ 0.45 kg/week. Treat that as "
            "an estimate — your body adapts as you lose, so re-check every few "
            "weeks against actual scale data rather than trusting the prediction."
        )
    elif goal == "bulk":
        head = "A surplus small enough that most of the gain is muscle."
        body = (
            f"Your maintenance (TDEE) is about {ctx['tdee']} kcal. Your target is "
            f"{ctx['target']} kcal — a surplus of {ctx['delta']} kcal "
            f"({ctx['delta_pct']}% above maintenance), or about "
            f"{ctx['rate_kg_per_week']} kg/week of gain.\n\n"
            "It's deliberately small. Muscle can only be built so fast — roughly "
            "0.25–0.5% of bodyweight per week for a trained lifter, and slower the "
            "more advanced you are. A bigger surplus doesn't build muscle faster; "
            "it just adds fat you'll have to diet off later, which costs months.\n\n"
            "Judge it by the scale and the mirror over 3–4 weeks. Gaining much "
            "faster than planned means the surplus is too big."
        )
    else:
        head = "Enough to fuel training and hold your weight steady."
        body = (
            f"Your maintenance (TDEE) is about {ctx['tdee']} kcal, and that's your "
            "target. This is where you recover best, train hardest and your "
            "hormones sit normally.\n\n"
            "Maintenance is underrated. After a long diet, a stretch here lets "
            "leptin, thyroid and training performance recover — which is exactly "
            "what makes the next cut work. It's also where you'd sit to "
            "recomposition slowly: gain muscle and lose fat at the same time, "
            "which works best for beginners and people returning after a break."
        )

    return {
        "id": "calories",
        "title": "Calories",
        "headline": head,
        "why_this_much": body
        + f"\n\nWe used your {ctx['bmr_method']} BMR ({ctx['bmr_used']} kcal) as "
          "the starting point, then multiplied by your activity level to get TDEE. "
          "Open the Energy section to see how the two BMR equations compare and "
          "why the lean-mass one is preferred for lifters.",
        "what_it_does": [
            {
                "label": "Sets the direction",
                "text": "Calories decide whether you gain, lose or hold. Macros "
                        "decide what that change is made of — muscle or fat. Both "
                        "matter, but calories come first: perfect macros in a "
                        "surplus will not lose you fat.",
            },
            {
                "label": "Fuels recovery and hormones",
                "text": "Energy availability — what's left after training burns its "
                        "share — drives testosterone, oestrogen, thyroid and bone "
                        "health. Too little for too long is a recognised clinical "
                        "problem (RED-S), and it affects men as well as women.",
            },
            {
                "label": "Estimates, not measurements",
                "text": "BMR equations carry roughly ±10% error, and activity "
                        "multipliers are broad brackets. This number is a starting "
                        "point. Track weight for 2–3 weeks, then adjust by what "
                        "actually happened — your own data always beats the formula.",
            },
        ],
        "too_little": [
            "Muscle loss, fatigue, poor recovery and stalled training.",
            "Hormonal disruption: lost periods in women, low testosterone in men, "
            "low thyroid output in both.",
            "Bone-density loss, weakened immunity, disturbed sleep, low mood.",
            "Metabolic adaptation — you burn less, so progress stalls at the same "
            "intake, which tempts an even deeper cut. That spiral is how disordered "
            "eating starts.",
        ],
        "too_much": [
            "Fat gain beyond what supports muscle growth — every extra kilo of "
            "fat is a future diet you have to run.",
            "In a bulk, a very large surplus worsens insulin sensitivity and "
            "usually makes the following cut longer and harder.",
        ],
        "source_keys": ["MIFFLIN", "KATCH_MCARDLE", "ACSM_ENERGY", "HELMS_NATURAL", "RED_S"],
    }


# ---------------------------------------------------------------------------
#  Static explainers for the calculator tools (no client numbers needed)
# ---------------------------------------------------------------------------

BODYFAT_METHOD_NOTES = {
    "navy": {
        "name": "U.S. Navy tape",
        "needs": "Tape measure: neck, waist, height (plus hips for women)",
        "trust": "Good for tracking, moderate for absolute accuracy",
        "how": "Predicts body fat from body circumferences. Fat accumulates "
               "around the waist, so waist size relative to neck and height "
               "carries real information.",
        "watch": "It can't tell muscle from fat. A lifter with a thick neck reads "
                 "leaner than they are; someone carrying fat on hips and thighs "
                 "rather than the waist reads leaner too. Typical error ±3–4%.",
        "source_keys": ["NAVY_TAPE"],
    },
    "jp3": {
        "name": "Jackson–Pollock 3-site",
        "needs": "Callipers: chest, abdomen, thigh (men) / triceps, suprailiac, thigh (women)",
        "trust": "Good — the practical best of these four when done well",
        "how": "Skinfold thickness estimates the fat stored just under the skin, "
               "which is converted to body density and then to body-fat percent "
               "using the Siri equation.",
        "watch": "Entirely dependent on technique. Same site, same pinch, same "
                 "person, every time — otherwise you're measuring your own "
                 "inconsistency. Ignores internal (visceral) fat. Error ±3–5%.",
        "source_keys": ["JACKSON_POLLOCK_M", "JACKSON_POLLOCK_W", "SIRI"],
    },
    "jp7": {
        "name": "Jackson–Pollock 7-site",
        "needs": "Callipers: chest, midaxillary, triceps, subscapular, abdomen, suprailiac, thigh",
        "trust": "Best of these four, if you have a skilled measurer",
        "how": "Same principle as the 3-site with more sampling points, so an "
               "unusual fat distribution biases the result less.",
        "watch": "More sites means more chances for technique error. Only better "
                 "than the 3-site if all seven are taken well. Error ±3–4%.",
        "source_keys": ["JACKSON_POLLOCK_M", "JACKSON_POLLOCK_W", "SIRI"],
    },
    "deurenberg": {
        "name": "Deurenberg (BMI-based)",
        "needs": "Height, weight, age, sex — no measuring at all",
        "trust": "Low for athletes — a sanity check, not a target",
        "how": "Estimates body fat from BMI, age and sex using population averages.",
        "watch": "BMI cannot distinguish muscle from fat, so it systematically "
                 "over-reads trained lifters — a muscular 85 kg athlete can read "
                 "'overweight'. Shown here to make that bias visible, not to be "
                 "believed. Error ±5% or worse in athletes.",
        "source_keys": ["DEURENBERG"],
    },
}

SPREAD_EXPLAINER = (
    "The methods disagree — and that spread is the most honest output on this "
    "screen. Every one of these is a formula fitted to a population, then applied "
    "to you. None of them measured your fat; they inferred it.\n\n"
    "What to do with that: pick one method, learn to do it consistently, and "
    "track the trend. A number that moves from 18% to 15% on the same method by "
    "the same measurer is real information. Comparing 18% from callipers against "
    "15% from a tape is not. Even DEXA and hydrostatic weighing — the lab "
    "standards — carry ±2–3% error, so chasing a decimal place is chasing noise."
)

FFMI_CONTEXT = (
    "FFMI is your lean mass scaled to your height — like BMI, but counting only "
    "the muscle. It answers 'how much muscle am I carrying for my frame?', which "
    "bodyweight alone can't.\n\n"
    "Rough reference points: ~18–19 is average untrained, ~20–21 is visibly "
    "athletic, ~22–23 is well-trained, and ~25 is where Kouri et al. (1995) found "
    "very few drug-free lifters above.\n\n"
    "Two honest caveats. First, that 25 figure is a population observation from "
    "one 1995 study, not a biological law — genetic outliers exist, and being "
    "under it proves nothing about anyone. Second, FFMI inherits all the error "
    "from your body-fat estimate: get body fat wrong by 3% and your FFMI is wrong "
    "too. Use it to track your own trend, not to audit anyone else."
)
