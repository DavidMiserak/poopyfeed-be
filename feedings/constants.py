"""Validation constants for feedings app.

Used by feedings models (check constraints), serializers, and forms for
bottle amount and breast duration validation. See feedings/constants.py
references in models and api.py.
"""

from decimal import Decimal

# Bottle feeding validation (DB check constraints and API validation)
MIN_BOTTLE_OZ = Decimal("0.1")
MAX_BOTTLE_OZ = Decimal("50")
BOTTLE_MAX_DIGITS = 4
BOTTLE_DECIMAL_PLACES = 1

# Breast feeding validation (duration in minutes)
MIN_BREAST_MINUTES = 1
MAX_BREAST_MINUTES = 180

# UI constants (preset step for bottle amount inputs)
BOTTLE_STEP = Decimal("0.1")
