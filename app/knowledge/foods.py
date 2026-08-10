"""
foods.py — the food portion database.

A number without a plate is useless. "Eat 165 g of protein" means nothing to a
client until they see "that's 6 eggs + 200 g paneer + 150 g chicken + a bowl of
dal". This file is what turns targets into food.

Every entry is one *realistic portion* — a katori of dal, one roti, one egg —
not "per 100 g", because nobody eats in 100 g units. `household` is the phrase a
client would actually recognise.

Values are rounded from the Indian Food Composition Tables (IFCT 2017,
ICMR-NIN) and USDA FoodData Central. They are approximations: brands, cooking
oil and portion size all move them. Rounding is deliberate — false precision
("23.7 g protein") implies an accuracy that food labels themselves do not have.

Field reference
    key        stable id, used by the macro/fibre/micro helpers
    name       display name
    household  the portion in words a client uses
    grams      approximate cooked/edible weight of that portion, in grams
    kcal, protein_g, carb_g, fat_g, fibre_g   per that portion
    tags       diet flags: veg | nonveg | egg | dairy | vegan
    micros     micronutrient keys (see micronutrients.py) this food is a
               genuinely good source of — used to build "eat this for iron"
               lists, so only meaningful contributors are listed
"""

# ---------------------------------------------------------------------------
#  PROTEIN-LED FOODS
# ---------------------------------------------------------------------------

PROTEIN_FOODS = [
    {
        "key": "chicken_breast",
        "name": "Chicken breast, cooked",
        "household": "1 palm-sized piece (150 g)",
        "grams": 150, "kcal": 248, "protein_g": 46, "carb_g": 0, "fat_g": 5.4, "fibre_g": 0,
        "tags": ["nonveg"], "micros": ["b12", "zinc", "iron", "potassium"],
    },
    {
        "key": "eggs_whole",
        "name": "Whole eggs",
        "household": "3 large eggs",
        "grams": 150, "kcal": 234, "protein_g": 19, "carb_g": 1.2, "fat_g": 16, "fibre_g": 0,
        "tags": ["egg"], "micros": ["b12", "vitamin_d", "vitamin_a", "zinc", "vitamin_k"],
    },
    {
        "key": "egg_whites",
        "name": "Egg whites",
        "household": "6 whites",
        "grams": 200, "kcal": 104, "protein_g": 22, "carb_g": 1.4, "fat_g": 0.3, "fibre_g": 0,
        "tags": ["egg"], "micros": ["potassium"],
    },
    {
        "key": "paneer",
        "name": "Paneer",
        "household": "1 thick slab (100 g)",
        "grams": 100, "kcal": 296, "protein_g": 18, "carb_g": 3.6, "fat_g": 23, "fibre_g": 0,
        "tags": ["veg", "dairy"], "micros": ["calcium", "b12", "vitamin_a"],
    },
    {
        "key": "paneer_low_fat",
        "name": "Low-fat paneer",
        "household": "1 slab (100 g)",
        "grams": 100, "kcal": 180, "protein_g": 22, "carb_g": 4.0, "fat_g": 9, "fibre_g": 0,
        "tags": ["veg", "dairy"], "micros": ["calcium", "b12"],
    },
    {
        "key": "curd",
        "name": "Curd / dahi (full fat)",
        "household": "1 bowl (200 g)",
        "grams": 200, "kcal": 120, "protein_g": 7, "carb_g": 9, "fat_g": 6.4, "fibre_g": 0,
        "tags": ["veg", "dairy"], "micros": ["calcium", "b12", "potassium"],
    },
    {
        "key": "greek_yogurt",
        "name": "Greek yoghurt / hung curd",
        "household": "1 cup (200 g)",
        "grams": 200, "kcal": 146, "protein_g": 20, "carb_g": 7.2, "fat_g": 4.0, "fibre_g": 0,
        "tags": ["veg", "dairy"], "micros": ["calcium", "b12"],
    },
    {
        "key": "milk_toned",
        "name": "Toned milk",
        "household": "1 glass (250 ml)",
        "grams": 250, "kcal": 145, "protein_g": 8, "carb_g": 12, "fat_g": 7.5, "fibre_g": 0,
        "tags": ["veg", "dairy"], "micros": ["calcium", "b12", "vitamin_a", "potassium"],
    },
    {
        "key": "toor_dal",
        "name": "Toor dal, cooked",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 174, "protein_g": 9, "carb_g": 28, "fat_g": 1.2, "fibre_g": 5.0,
        "tags": ["veg", "vegan"], "micros": ["iron", "magnesium", "potassium", "folate"],
    },
    {
        "key": "rajma",
        "name": "Rajma (kidney beans), cooked",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 190, "protein_g": 11, "carb_g": 33, "fat_g": 0.8, "fibre_g": 9.0,
        "tags": ["veg", "vegan"], "micros": ["iron", "magnesium", "potassium", "folate"],
    },
    {
        "key": "chana",
        "name": "Chana / chickpeas, boiled",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 246, "protein_g": 13, "carb_g": 40, "fat_g": 3.8, "fibre_g": 11.0,
        "tags": ["veg", "vegan"], "micros": ["iron", "magnesium", "zinc", "folate"],
    },
    {
        "key": "soya_chunks",
        "name": "Soya chunks, cooked",
        "household": "1 katori cooked (from 30 g dry)",
        "grams": 90, "kcal": 105, "protein_g": 16, "carb_g": 9, "fat_g": 0.5, "fibre_g": 4.0,
        "tags": ["veg", "vegan"], "micros": ["iron", "magnesium", "zinc", "calcium"],
    },
    {
        "key": "fish_rohu",
        "name": "Fish (rohu / surmai), cooked",
        "household": "1 fillet (150 g)",
        "grams": 150, "kcal": 195, "protein_g": 31, "carb_g": 0, "fat_g": 7.5, "fibre_g": 0,
        "tags": ["nonveg"], "micros": ["omega3", "vitamin_d", "b12", "iodine"],
    },
    {
        "key": "sardines",
        "name": "Sardines / mackerel (bangda)",
        "household": "1 serving (120 g)",
        "grams": 120, "kcal": 250, "protein_g": 25, "carb_g": 0, "fat_g": 16, "fibre_g": 0,
        "tags": ["nonveg"], "micros": ["omega3", "vitamin_d", "b12", "calcium", "iodine"],
    },
    {
        "key": "mutton",
        "name": "Mutton, cooked (lean)",
        "household": "1 serving (120 g)",
        "grams": 120, "kcal": 288, "protein_g": 30, "carb_g": 0, "fat_g": 18, "fibre_g": 0,
        "tags": ["nonveg"], "micros": ["iron", "b12", "zinc"],
    },
    {
        "key": "tofu",
        "name": "Tofu, firm",
        "household": "1 block (150 g)",
        "grams": 150, "kcal": 220, "protein_g": 24, "carb_g": 3.6, "fat_g": 12, "fibre_g": 1.4,
        "tags": ["veg", "vegan"], "micros": ["calcium", "iron", "magnesium", "zinc"],
    },
    {
        "key": "whey",
        "name": "Whey protein",
        "household": "1 scoop (30 g)",
        "grams": 30, "kcal": 120, "protein_g": 24, "carb_g": 2.5, "fat_g": 1.5, "fibre_g": 0,
        "tags": ["veg", "dairy"], "micros": ["calcium"],
    },
]

# ---------------------------------------------------------------------------
#  CARBOHYDRATE-LED FOODS
# ---------------------------------------------------------------------------

CARB_FOODS = [
    {
        "key": "roti",
        "name": "Roti / chapati (whole wheat)",
        "household": "1 medium roti (40 g)",
        "grams": 40, "kcal": 120, "protein_g": 3.4, "carb_g": 22, "fat_g": 1.8, "fibre_g": 2.6,
        "tags": ["veg", "vegan"], "micros": ["magnesium", "iron", "fibre"],
    },
    {
        "key": "rice_cooked",
        "name": "Rice, cooked",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 195, "protein_g": 4.0, "carb_g": 43, "fat_g": 0.5, "fibre_g": 0.6,
        "tags": ["veg", "vegan"], "micros": [],
    },
    {
        "key": "brown_rice",
        "name": "Brown rice, cooked",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 186, "protein_g": 4.4, "carb_g": 39, "fat_g": 1.4, "fibre_g": 2.7,
        "tags": ["veg", "vegan"], "micros": ["magnesium", "fibre"],
    },
    {
        "key": "oats",
        "name": "Oats, dry",
        "household": "1/2 cup (50 g)",
        "grams": 50, "kcal": 195, "protein_g": 6.5, "carb_g": 33, "fat_g": 3.5, "fibre_g": 5.0,
        "tags": ["veg", "vegan"], "micros": ["magnesium", "iron", "zinc", "fibre"],
    },
    {
        "key": "idli",
        "name": "Idli",
        "household": "3 idli",
        "grams": 150, "kcal": 174, "protein_g": 5.0, "carb_g": 36, "fat_g": 0.6, "fibre_g": 1.8,
        "tags": ["veg", "vegan"], "micros": [],
    },
    {
        "key": "dosa",
        "name": "Plain dosa",
        "household": "1 dosa",
        "grams": 100, "kcal": 165, "protein_g": 4.0, "carb_g": 28, "fat_g": 4.0, "fibre_g": 1.4,
        "tags": ["veg", "vegan"], "micros": [],
    },
    {
        "key": "poha",
        "name": "Poha, cooked",
        "household": "1 plate (200 g)",
        "grams": 200, "kcal": 250, "protein_g": 5.0, "carb_g": 48, "fat_g": 4.5, "fibre_g": 2.0,
        "tags": ["veg", "vegan"], "micros": ["iron"],
    },
    {
        "key": "sweet_potato",
        "name": "Sweet potato, boiled",
        "household": "1 medium (150 g)",
        "grams": 150, "kcal": 130, "protein_g": 2.4, "carb_g": 30, "fat_g": 0.2, "fibre_g": 4.5,
        "tags": ["veg", "vegan"], "micros": ["vitamin_a", "potassium", "vitamin_c", "fibre"],
    },
    {
        "key": "potato",
        "name": "Potato, boiled",
        "household": "1 medium (150 g)",
        "grams": 150, "kcal": 130, "protein_g": 3.0, "carb_g": 30, "fat_g": 0.2, "fibre_g": 3.0,
        "tags": ["veg", "vegan"], "micros": ["potassium", "vitamin_c"],
    },
    {
        "key": "banana",
        "name": "Banana",
        "household": "1 medium",
        "grams": 120, "kcal": 105, "protein_g": 1.3, "carb_g": 27, "fat_g": 0.4, "fibre_g": 3.1,
        "tags": ["veg", "vegan"], "micros": ["potassium", "magnesium", "vitamin_c"],
    },
    {
        "key": "chapati_bajra",
        "name": "Bajra / jowar roti (millet)",
        "household": "1 roti (50 g)",
        "grams": 50, "kcal": 130, "protein_g": 3.6, "carb_g": 25, "fat_g": 1.5, "fibre_g": 3.2,
        "tags": ["veg", "vegan"], "micros": ["iron", "magnesium", "fibre"],
    },
]

# ---------------------------------------------------------------------------
#  FAT-LED FOODS
# ---------------------------------------------------------------------------

FAT_FOODS = [
    {
        "key": "ghee",
        "name": "Ghee",
        "household": "1 tsp (5 g)",
        "grams": 5, "kcal": 45, "protein_g": 0, "carb_g": 0, "fat_g": 5.0, "fibre_g": 0,
        "tags": ["veg", "dairy"], "micros": ["vitamin_a", "vitamin_k"],
    },
    {
        "key": "oil",
        "name": "Cooking oil (mustard / groundnut)",
        "household": "1 tsp (5 ml)",
        "grams": 5, "kcal": 45, "protein_g": 0, "carb_g": 0, "fat_g": 5.0, "fibre_g": 0,
        "tags": ["veg", "vegan"], "micros": ["vitamin_e"],
    },
    {
        "key": "almonds",
        "name": "Almonds",
        "household": "15 almonds (20 g)",
        "grams": 20, "kcal": 116, "protein_g": 4.2, "carb_g": 4.4, "fat_g": 10, "fibre_g": 2.5,
        "tags": ["veg", "vegan"], "micros": ["vitamin_e", "magnesium", "calcium", "fibre"],
    },
    {
        "key": "peanuts",
        "name": "Peanuts, roasted",
        "household": "1 small handful (30 g)",
        "grams": 30, "kcal": 170, "protein_g": 7.6, "carb_g": 4.8, "fat_g": 14, "fibre_g": 2.5,
        "tags": ["veg", "vegan"], "micros": ["vitamin_e", "magnesium", "zinc"],
    },
    {
        "key": "walnuts",
        "name": "Walnuts",
        "household": "4 halves (20 g)",
        "grams": 20, "kcal": 131, "protein_g": 3.0, "carb_g": 2.8, "fat_g": 13, "fibre_g": 1.4,
        "tags": ["veg", "vegan"], "micros": ["omega3", "magnesium"],
    },
    {
        "key": "flaxseed",
        "name": "Flaxseed, ground",
        "household": "1 tbsp (10 g)",
        "grams": 10, "kcal": 53, "protein_g": 1.8, "carb_g": 2.9, "fat_g": 4.2, "fibre_g": 2.7,
        "tags": ["veg", "vegan"], "micros": ["omega3", "magnesium", "fibre"],
    },
    {
        "key": "coconut",
        "name": "Fresh coconut",
        "household": "2 tbsp grated (20 g)",
        "grams": 20, "kcal": 70, "protein_g": 0.7, "carb_g": 3.0, "fat_g": 6.7, "fibre_g": 1.8,
        "tags": ["veg", "vegan"], "micros": ["fibre"],
    },
    {
        "key": "peanut_butter",
        "name": "Peanut butter",
        "household": "1 tbsp (16 g)",
        "grams": 16, "kcal": 94, "protein_g": 4.0, "carb_g": 3.2, "fat_g": 8.0, "fibre_g": 1.0,
        "tags": ["veg", "vegan"], "micros": ["vitamin_e", "magnesium"],
    },
]

# ---------------------------------------------------------------------------
#  FIBRE & MICRONUTRIENT-LED FOODS (vegetables, fruit, greens)
# ---------------------------------------------------------------------------

FIBRE_FOODS = [
    {
        "key": "palak",
        "name": "Palak / spinach, cooked",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 42, "protein_g": 4.4, "carb_g": 5.1, "fat_g": 0.6, "fibre_g": 3.4,
        "tags": ["veg", "vegan"], "micros": ["iron", "vitamin_k", "vitamin_a", "magnesium", "folate", "fibre"],
    },
    {
        "key": "mixed_veg",
        "name": "Mixed vegetable sabzi",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 90, "protein_g": 3.0, "carb_g": 11, "fat_g": 4.0, "fibre_g": 4.0,
        "tags": ["veg", "vegan"], "micros": ["vitamin_c", "vitamin_a", "potassium", "fibre"],
    },
    {
        "key": "bhindi",
        "name": "Bhindi / okra, cooked",
        "household": "1 katori (150 g)",
        "grams": 150, "kcal": 75, "protein_g": 2.7, "carb_g": 10, "fat_g": 3.0, "fibre_g": 4.8,
        "tags": ["veg", "vegan"], "micros": ["magnesium", "vitamin_c", "folate", "fibre"],
    },
    {
        "key": "guava",
        "name": "Guava",
        "household": "1 medium (150 g)",
        "grams": 150, "kcal": 68, "protein_g": 2.6, "carb_g": 14, "fat_g": 1.0, "fibre_g": 8.0,
        "tags": ["veg", "vegan"], "micros": ["vitamin_c", "potassium", "fibre"],
    },
    {
        "key": "apple",
        "name": "Apple, with skin",
        "household": "1 medium (180 g)",
        "grams": 180, "kcal": 94, "protein_g": 0.5, "carb_g": 25, "fat_g": 0.3, "fibre_g": 4.3,
        "tags": ["veg", "vegan"], "micros": ["fibre"],
    },
    {
        "key": "papaya",
        "name": "Papaya",
        "household": "1 bowl (200 g)",
        "grams": 200, "kcal": 86, "protein_g": 1.0, "carb_g": 22, "fat_g": 0.5, "fibre_g": 3.4,
        "tags": ["veg", "vegan"], "micros": ["vitamin_c", "vitamin_a", "potassium", "fibre"],
    },
    {
        "key": "orange",
        "name": "Orange / mosambi",
        "household": "1 medium (150 g)",
        "grams": 150, "kcal": 70, "protein_g": 1.3, "carb_g": 17, "fat_g": 0.2, "fibre_g": 3.1,
        "tags": ["veg", "vegan"], "micros": ["vitamin_c", "potassium", "folate", "fibre"],
    },
    {
        "key": "salad_veg",
        "name": "Raw salad (cucumber, tomato, carrot, onion)",
        "household": "1 large plate (200 g)",
        "grams": 200, "kcal": 50, "protein_g": 2.0, "carb_g": 10, "fat_g": 0.3, "fibre_g": 4.0,
        "tags": ["veg", "vegan"], "micros": ["vitamin_a", "vitamin_c", "potassium", "fibre"],
    },
    {
        "key": "sprouts",
        "name": "Moong sprouts",
        "household": "1 katori (100 g)",
        "grams": 100, "kcal": 100, "protein_g": 8.0, "carb_g": 14, "fat_g": 0.6, "fibre_g": 5.0,
        "tags": ["veg", "vegan"], "micros": ["iron", "folate", "vitamin_c", "fibre"],
    },
]

# One flat list for lookups by key.
ALL_FOODS = PROTEIN_FOODS + CARB_FOODS + FAT_FOODS + FIBRE_FOODS
BY_KEY = {f["key"]: f for f in ALL_FOODS}


# ---------------------------------------------------------------------------
#  Helpers used by the nutrition engine
# ---------------------------------------------------------------------------

def diet_ok(food: dict, diet: str) -> bool:
    """
    Is this food allowed on the client's diet?

    diet values: "omnivore" | "eggetarian" | "vegetarian" | "vegan"
    Indian "vegetarian" normally includes dairy but not egg — hence the separate
    "eggetarian" option, which is a real and very common category here.
    """
    tags = set(food["tags"])
    if diet == "omnivore":
        return True
    if diet == "eggetarian":
        return "nonveg" not in tags
    if diet == "vegetarian":
        return "nonveg" not in tags and "egg" not in tags
    if diet == "vegan":
        return "vegan" in tags
    return True


def portions_for_protein(target_g: float, diet: str, limit: int = 6) -> list[dict]:
    """
    Build a "here's what {target}g of protein looks like" list.

    Picks the highest-protein-density foods the diet allows and shows how many
    portions of each would cover the whole target on its own. Nobody eats one
    food all day — the point is to give the client a mental scale, e.g. "my
    target is about 5 slabs of paneer worth of protein".
    """
    pool = [f for f in PROTEIN_FOODS if diet_ok(f, diet) and f["protein_g"] >= 6]
    pool.sort(key=lambda f: f["protein_g"] / max(f["kcal"], 1), reverse=True)
    out = []
    for f in pool[:limit]:
        n = target_g / f["protein_g"]
        out.append({
            "name": f["name"],
            "household": f["household"],
            "portions": round(n, 1),
            "per_portion_g": f["protein_g"],
            "kcal_if_all": round(n * f["kcal"]),
        })
    return out


def sample_plate(target_g: float, diet: str) -> list[dict]:
    """
    A realistic mixed day that adds up to roughly the protein target.

    Greedy fill from a diet-appropriate rotation: take portions of each staple in
    turn until the target is met. This is illustrative, not a prescription — the
    UI labels it "one way to get there".
    """
    if diet == "vegan":
        rotation = ["tofu", "soya_chunks", "chana", "toor_dal", "rajma", "peanuts", "oats"]
    elif diet == "vegetarian":
        rotation = ["paneer_low_fat", "greek_yogurt", "toor_dal", "whey", "milk_toned", "chana"]
    elif diet == "eggetarian":
        rotation = ["eggs_whole", "paneer_low_fat", "greek_yogurt", "toor_dal", "whey", "chana"]
    else:
        rotation = ["chicken_breast", "eggs_whole", "curd", "toor_dal", "fish_rohu", "paneer_low_fat"]

    plate, running = [], 0.0
    for key in rotation:
        remaining = target_g - running
        # Stop once we're within half a portion of the target — adding another
        # whole portion here would overshoot by more than it closes.
        if remaining < BY_KEY[key]["protein_g"] * 0.5:
            break
        f = BY_KEY[key]
        # Cap portions per food so the day stays varied — but scale the cap to
        # protein density. Plant foods carry roughly half the protein per portion
        # of meat or paneer, so a 2-portion cap across a vegan rotation can't
        # physically reach a lifter's target and the plate silently undershoots.
        # Three katori of dal or two blocks of tofu in a day is entirely normal.
        cap = 3 if f["protein_g"] < 12 else 2
        n = min(cap, max(1, round(remaining / f["protein_g"])))
        plate.append({
            "name": f["name"],
            "household": f["household"],
            "portions": n,
            "protein_g": round(f["protein_g"] * n, 1),
            "kcal": round(f["kcal"] * n),
        })
        running += f["protein_g"] * n
    return plate


def sources_for_micro(micro_key: str, diet: str, limit: int = 5) -> list[dict]:
    """
    Best food sources for one micronutrient, filtered to the client's diet.

    Returns [] when the diet genuinely has no good whole-food source — that
    absence is information (it is exactly why vegans need a B12 supplement), so
    the micronutrient panel surfaces it rather than inventing a weak source.
    """
    hits = [f for f in ALL_FOODS if micro_key in f.get("micros", []) and diet_ok(f, diet)]
    hits.sort(key=lambda f: f["kcal"])          # lighter options first
    return [{"name": f["name"], "household": f["household"]} for f in hits[:limit]]


def high_fibre_picks(diet: str, limit: int = 6) -> list[dict]:
    """Highest fibre-per-calorie foods — the practical way to hit a fibre target."""
    pool = [f for f in ALL_FOODS if diet_ok(f, diet) and f["fibre_g"] >= 2.5]
    pool.sort(key=lambda f: f["fibre_g"] / max(f["kcal"], 1), reverse=True)
    return [
        {
            "name": f["name"],
            "household": f["household"],
            "fibre_g": f["fibre_g"],
            "kcal": f["kcal"],
        }
        for f in pool[:limit]
    ]
