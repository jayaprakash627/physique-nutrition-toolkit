"""
knowledge — the nutrition content layer.

Deliberately separated from the maths (`app/formulas.py`) and the API
(`app/main.py`) so the content can be reviewed and corrected by someone who
knows nutrition but not Python, without touching application logic.

    sources.py          every citation, one entry per standard
    explanations.py     the "Why this number?" text for each macro
    micronutrients.py   the vitamin & mineral panel + client risk profiling
    foods.py            Indian food portions, for turning grams into plates

Nothing in this package imports from outside it — the content layer has no
dependencies on the app, only the other way round. That keeps it verifiable in
isolation.
"""

from . import explanations, foods, micronutrients, sources  # noqa: F401

__all__ = ["explanations", "foods", "micronutrients", "sources"]
