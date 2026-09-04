"""
costing.py — what a day of the plan actually costs to buy.

A coach can hit the macros perfectly and still hand a client a plan they quietly
abandon in week three because it costs more than they budget for food. So this
turns a built day into a shopping list with a price on it, and — because prices
are local and go stale — lets the coach replace every number in it.

TWO THINGS MAKE THIS LESS TRIVIAL THAN IT LOOKS

**You don't buy food in the units the plan is written in.** The plan says grams,
because that is what nutrition is calculated in. Nobody buys eggs in grams, or
milk and oil in anything but litres. So every food carries the unit it is
actually sold in — kg, litre, or piece — and the grams that one of those units
contains, and the conversion happens here rather than in the coach's head.

**The plan is in COOKED weight. You buy RAW.** This is the one that would
silently produce wrong numbers, and it goes in both directions. 150 g of cooked
chicken started as about 210 g raw, because meat loses water — cost it as 150 g
and you are 40% under. 150 g of cooked rice was only about 57 g of raw rice,
because grains absorb it — cost that as 150 g and you are nearly 3× over. Dal is
worse still. Every entry below therefore carries a `raw_factor`: multiply the
plan's grams by it to get the weight you put in the basket, with the reason
written next to it.

PRICES ARE A STARTING POINT, NOT A FACT
The defaults are ordinary Indian retail, and they will be wrong for somebody —
wrong city, wrong month, wrong shop. They exist so the feature works out of the
box, not because they are authoritative. The coach can override any of them, the
overrides are stored, and the output always says which prices were used and when
they were last touched. A cost estimate that hides its assumptions is worse than
no estimate, because it gets quoted to a client.
"""

from __future__ import annotations

from .knowledge import foods

# When the default prices below were last sanity-checked. Shown in the UI so a
# coach can see how stale they are rather than trusting them indefinitely.
PRICES_AS_OF = "2026-09"

KG, LITRE, PIECE = "kg", "litre", "piece"

# unit          how it is sold
# unit_grams    grams in one of those units
# raw_factor    plan grams × this = weight you buy
# price         default, in rupees, per unit
PURCHASE: dict[str, dict] = {
    # --- Meat, fish, eggs -------------------------------------------------
    # Meat loses roughly a third of its weight as water in cooking, so the raw
    # weight you buy is meaningfully more than the cooked weight you eat.
    "chicken_breast": {"unit": KG, "unit_grams": 1000, "raw_factor": 1.40, "price": 280,
                       "why": "cooked chicken has lost ~30% water; you buy it raw"},
    "fish_rohu":      {"unit": KG, "unit_grams": 1000, "raw_factor": 1.40, "price": 260,
                       "why": "cooking loss on a cleaned fillet"},
    "mutton":         {"unit": KG, "unit_grams": 1000, "raw_factor": 1.50, "price": 800,
                       "why": "cooking loss plus trimming"},
    "sardines":       {"unit": KG, "unit_grams": 1000, "raw_factor": 1.30, "price": 220,
                       "why": "cooking loss"},
    # Eggs are the clearest case for not using grams: nobody buys 150 g of egg.
    "eggs_whole":     {"unit": PIECE, "unit_grams": 50, "raw_factor": 1.0, "price": 7,
                       "why": "one large egg is about 50 g"},
    # You cannot buy a white on its own — six whites means buying six eggs, and
    # paying for six yolks you are not eating. Costing it any other way would
    # make egg whites look cheaper than they are.
    "egg_whites":     {"unit": PIECE, "unit_grams": 33, "raw_factor": 1.0, "price": 7,
                       "why": "you buy the whole egg even when you use only the white"},

    # --- Dairy ------------------------------------------------------------
    "milk_toned":     {"unit": LITRE, "unit_grams": 1000, "raw_factor": 1.0, "price": 60,
                       "why": "sold by the litre; 1 ml ≈ 1 g"},
    "curd":           {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 90},
    "greek_yogurt":   {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 400},
    "paneer":         {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 400},
    "paneer_low_fat": {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 420},
    "ghee":           {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 650},
    "whey":           {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 2000,
                       "why": "a 1 kg tub; the single most price-sensitive item here"},

    # --- Pulses and soya: bought dry, eaten cooked -------------------------
    # A katori of cooked dal started as roughly a third of its weight in dry dal.
    # Costing the cooked weight would roughly triple the grocery bill for pulses.
    "toor_dal":       {"unit": KG, "unit_grams": 1000, "raw_factor": 0.35, "price": 160,
                       "why": "dry dal roughly triples in weight when cooked"},
    "rajma":          {"unit": KG, "unit_grams": 1000, "raw_factor": 0.42, "price": 140,
                       "why": "dry beans absorb water when soaked and boiled"},
    "chana":          {"unit": KG, "unit_grams": 1000, "raw_factor": 0.42, "price": 100,
                       "why": "dry chana absorbs water when soaked and boiled"},
    "soya_chunks":    {"unit": KG, "unit_grams": 1000, "raw_factor": 0.33, "price": 200,
                       "why": "the portion is already stated as 90 g cooked from 30 g dry"},
    "sprouts":        {"unit": KG, "unit_grams": 1000, "raw_factor": 0.45, "price": 120,
                       "why": "sprouted moong weighs more than the dry grain it came from"},
    "tofu":           {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 250},

    # --- Grains ------------------------------------------------------------
    "rice_cooked":    {"unit": KG, "unit_grams": 1000, "raw_factor": 0.38, "price": 60,
                       "why": "rice roughly two-and-a-half times its weight when cooked"},
    "brown_rice":     {"unit": KG, "unit_grams": 1000, "raw_factor": 0.40, "price": 120,
                       "why": "same absorption as white rice"},
    "oats":           {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 150,
                       "why": "the portion is already dry weight"},
    # Flatbreads and batters are priced by the flour or grain they are made from,
    # not the finished weight, because that is what is bought.
    "roti":           {"unit": KG, "unit_grams": 1000, "raw_factor": 0.70, "price": 50,
                       "why": "priced as atta; the rest of a roti's weight is water"},
    "chapati_bajra":  {"unit": KG, "unit_grams": 1000, "raw_factor": 0.70, "price": 80,
                       "why": "priced as bajra flour"},
    "idli":           {"unit": KG, "unit_grams": 1000, "raw_factor": 0.40, "price": 70,
                       "why": "priced as the rice and urad dal the batter is ground from"},
    "dosa":           {"unit": KG, "unit_grams": 1000, "raw_factor": 0.38, "price": 70,
                       "why": "priced as the batter's dry rice and dal"},
    "poha":           {"unit": KG, "unit_grams": 1000, "raw_factor": 0.35, "price": 60,
                       "why": "flattened rice swells when soaked and cooked"},
    "potato":         {"unit": KG, "unit_grams": 1000, "raw_factor": 1.15, "price": 30,
                       "why": "peeling waste"},
    "sweet_potato":   {"unit": KG, "unit_grams": 1000, "raw_factor": 1.15, "price": 60,
                       "why": "peeling waste"},

    # --- Fats, nuts, seeds --------------------------------------------------
    "oil":            {"unit": LITRE, "unit_grams": 920, "raw_factor": 1.0, "price": 150,
                       "why": "oil is lighter than water — a litre is about 920 g"},
    "almonds":        {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 900},
    "walnuts":        {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 1200},
    "peanuts":        {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 160},
    "peanut_butter":  {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 500},
    "flaxseed":       {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 200},
    "coconut":        {"unit": KG, "unit_grams": 1000, "raw_factor": 1.0, "price": 120},

    # --- Vegetables and fruit ------------------------------------------------
    # Leafy greens collapse when cooked: a katori of cooked palak is a large
    # bunch of raw spinach, which is why it looks disproportionately expensive
    # here and is still one of the cheapest things on the list.
    "palak":          {"unit": KG, "unit_grams": 1000, "raw_factor": 2.00, "price": 40,
                       "why": "spinach loses about half its weight when cooked"},
    "mixed_veg":      {"unit": KG, "unit_grams": 1000, "raw_factor": 1.20, "price": 60,
                       "why": "trimming and peeling waste"},
    "bhindi":         {"unit": KG, "unit_grams": 1000, "raw_factor": 1.20, "price": 60,
                       "why": "topping and tailing waste"},
    "salad_veg":      {"unit": KG, "unit_grams": 1000, "raw_factor": 1.15, "price": 50,
                       "why": "trimming waste"},
    "banana":         {"unit": PIECE, "unit_grams": 120, "raw_factor": 1.0, "price": 7,
                       "why": "sold by the piece; 120 g is the edible part of a medium one"},
    "orange":         {"unit": PIECE, "unit_grams": 150, "raw_factor": 1.0, "price": 15},
    "apple":          {"unit": PIECE, "unit_grams": 180, "raw_factor": 1.0, "price": 30},
    "guava":          {"unit": PIECE, "unit_grams": 150, "raw_factor": 1.0, "price": 15},
    "papaya":         {"unit": KG, "unit_grams": 1000, "raw_factor": 1.55, "price": 50,
                       "why": "you buy it whole; skin and seeds are about a third"},
}

UNIT_LABEL = {KG: "per kg", LITRE: "per litre", PIECE: "each"}


def default_prices() -> dict[str, float]:
    return {key: row["price"] for key, row in PURCHASE.items()}


def _quantity(food_key: str, grams: float, table: dict | None = None) -> dict | None:
    """
    Turn plan grams into something you can put in a basket.

    Returns the amount in purchase units, and the raw weight behind it, so the
    conversion is visible rather than folded silently into a price.
    """
    row = (table or PURCHASE).get(food_key)
    if not row:
        return None
    raw_grams = grams * row["raw_factor"]
    units = raw_grams / row["unit_grams"]
    return {
        "unit": row["unit"],
        "unit_label": UNIT_LABEL[row["unit"]],
        "raw_grams": round(raw_grams),
        # Eggs and bananas come in whole numbers; you cannot buy 2.4 eggs.
        "units": round(units) if row["unit"] == PIECE else round(units, 3),
        "raw_factor": row["raw_factor"],
        "why_raw": row.get("why"),
    }


def _display(food_key: str, q: dict, book: dict | None = None) -> str:
    """How the quantity reads on a shopping list."""
    if q["unit"] == PIECE:
        n = max(1, int(q["units"]))
        entry = (book or foods.BY_KEY).get(food_key) or {"name": ""}
        name = entry["name"].lower()
        return f"{n} {'egg' if 'egg' in name else 'piece'}{'s' if n != 1 else ''}"
    grams = q["raw_grams"]
    if grams >= 1000:
        return f"{grams / 1000:.2f} kg".replace(".00 kg", " kg")
    return f"{grams} {'ml' if q['unit'] == LITRE else 'g'}"


def _bill(day: dict, price_map: dict[str, float], days: int,
          table: dict | None = None) -> float:
    """Just the total for N days — used to price a week and a month honestly."""
    total = 0.0
    for item in day.get("items", []):
        q = _quantity(item["key"], item["grams"] * days, table)
        if q:
            total += q["units"] * price_map.get(item["key"], 0.0)
    return total


def cost_day(day: dict, prices: dict[str, float] | None = None,
             *, days: int = 1, table: dict | None = None,
             book: dict | None = None) -> dict:
    """
    Price a built day, and roll it up into a shopping list.

    `days` multiplies the quantities so a coach can hand over a week's shopping
    rather than one day's, which is how anyone actually buys food.
    """
    # `table` carries the coach's own foods alongside the shipped ones, so a
    # custom food is priced exactly like any other rather than falling off the
    # bill as "unpriced".
    table = table or PURCHASE
    price_map = {**{k: v["price"] for k, v in table.items()}, **(prices or {})}
    items, unpriced = [], []
    total = 0.0

    for item in day.get("items", []):
        key = item["key"]
        q = _quantity(key, item["grams"] * days, table)
        if not q:
            # A food with no purchase data is listed, not silently dropped — a
            # missing line in a shopping list is worse than an obvious gap.
            unpriced.append(item["name"])
            continue
        unit_price = price_map.get(key, 0.0)
        cost = q["units"] * unit_price
        total += cost
        items.append({
            "key": key,
            "name": item["name"],
            "eat_grams": round(item["grams"] * days),
            "buy": _display(key, q, book),
            "buy_units": q["units"],
            "unit": q["unit"],
            "unit_label": q["unit_label"],
            "unit_price": unit_price,
            "cost": round(cost, 2),
            "raw_factor": q["raw_factor"],
            "why_raw": q["why_raw"],
        })

    items.sort(key=lambda i: i["cost"], reverse=True)
    per_day = total / days if days else 0.0

    # A week is priced as a week's shopping, not as one day multiplied by seven,
    # and the difference is real rather than pedantic. Whole-unit foods have to
    # round: 4.5 eggs a day becomes 4, and seven of those is 28 — but the week
    # genuinely needs 31.5, so you buy 32. Multiplying a rounded day understated
    # this plan by about 3%, always in the same direction, and the error grows
    # with however many piece-priced foods are in the plan. Recomputing at each
    # horizon costs nothing and means the monthly figure — the one a client
    # actually answers yes or no to — is the one that's right.
    week = _bill(day, price_map, 7, table) if days == 1 else None
    month = _bill(day, price_map, 30, table) if days == 1 else None

    return {
        "days": days,
        "items": items,
        "unpriced": unpriced,
        "total": round(total, 2),
        "per_day": round(per_day, 2),
        "per_week": round(week if week is not None else per_day * 7, 2),
        "per_month": round(month if month is not None else per_day * 30, 2),
        # The single most useful line for a coach: which food is eating the
        # budget. It is almost always one item, and it is almost always fixable.
        "biggest": items[0] if items else None,
        "biggest_share_pct": round(items[0]["cost"] / total * 100) if items and total else 0,
        "prices_as_of": PRICES_AS_OF,
        "note": (
            "Quantities are what you BUY, not what's eaten — meat is heavier raw, "
            "rice and dal are much lighter. Prices are ordinary Indian retail and "
            "will be wrong for your city and month; change any of them and the "
            "totals follow."
        ),
    }
