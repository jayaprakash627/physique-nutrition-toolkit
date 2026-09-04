"""
catalog.py — the curated food list, plus whatever the coach added.

`app/knowledge/foods.py` carries a promise: every number in it is cited to IFCT
2017 or USDA, and a dietitian can check the whole file without reading a line of
application code. Writing a coach's own entries into it would end that promise
quietly — the file would hold verified and unverified numbers side by side with
nothing to tell them apart.

So the two stay separate and are merged here, at request time. The curated list
is never mutated; a custom food is a row in the database that gets folded into a
working copy for one calculation. Everything downstream — the planner, the
costing — takes the merged view as an argument rather than reaching for a global,
which is also what makes it testable.

Custom entries keep an `is_custom` flag all the way to the screen, so a coach can
always see which numbers came from a published table and which they typed in
themselves.
"""

from __future__ import annotations

from .knowledge import foods
from .models import FOOD_CATEGORY_TAGS

CUSTOM_PREFIX = "custom_"


def make_key(name: str, existing: set[str]) -> str:
    """
    A stable id from the name, prefixed so a custom food is obvious in any dump.

    Collisions get a numeric suffix rather than silently overwriting: two foods
    both called "protein bar" are two foods, and losing the first one the moment
    the second is added would be indistinguishable from the save failing.
    """
    slug = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")
    slug = "_".join(part for part in slug.split("_") if part)[:40] or "food"
    base = f"{CUSTOM_PREFIX}{slug}"
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def to_record(payload, key: str) -> dict:
    """
    Turn the submitted form into the shape the rest of the app already speaks.

    The coach types per 100 g because that is what a label shows; everything
    downstream works in portions, so the conversion happens once, here, rather
    than being repeated at every call site with a chance to differ.
    """
    factor = payload.portion_grams / 100.0
    unit_grams = (payload.piece_grams if payload.unit == "piece" else 1000)
    return {
        "key": key,
        "name": payload.name.strip(),
        "household": payload.household.strip(),
        "grams": round(payload.portion_grams),
        "kcal": round(payload.kcal_100g * factor),
        "protein_g": round(payload.protein_100g * factor, 1),
        "carb_g": round(payload.carb_100g * factor, 1),
        "fat_g": round(payload.fat_100g * factor, 1),
        "fibre_g": round(payload.fibre_100g * factor, 1),
        "tags": FOOD_CATEGORY_TAGS[payload.category],
        # No micronutrient claims. The curated entries list only nutrients a food
        # is a genuinely good source of, sourced from a published table; inviting
        # a coach to assert that from memory would put unverifiable claims into
        # the panel that tells a vegan where to get B12.
        "micros": [],
        "is_custom": True,
        "purchase": {
            "unit": payload.unit,
            "unit_grams": unit_grams,
            "raw_factor": payload.raw_factor,
            "price": payload.price,
            "why": ("your own food" if payload.raw_factor == 1
                    else f"you set a buying multiplier of {payload.raw_factor:g}×"),
        },
        "per_100g": {
            "kcal": payload.kcal_100g, "protein_g": payload.protein_100g,
            "carb_g": payload.carb_100g, "fat_g": payload.fat_100g,
            "fibre_g": payload.fibre_100g,
        },
        "category": payload.category,
    }


def by_key(custom: list[dict] | None = None) -> dict[str, dict]:
    """The curated foods, with the coach's own merged on top. Never mutates either."""
    merged = dict(foods.BY_KEY)
    for food in custom or []:
        merged[food["key"]] = food
    return merged


def purchase(custom: list[dict] | None = None) -> dict[str, dict]:
    """The shipped purchase table, with a row for each custom food."""
    from . import costing
    merged = dict(costing.PURCHASE)
    for food in custom or []:
        if food.get("purchase"):
            merged[food["key"]] = food["purchase"]
    return merged


def custom_prices(custom: list[dict] | None = None) -> dict[str, float]:
    """Each custom food's own price, so the costing picks it up like any other."""
    return {f["key"]: f["purchase"]["price"] for f in (custom or []) if f.get("purchase")}
