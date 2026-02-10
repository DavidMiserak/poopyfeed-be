"""Validation constants for feedings app."""

from decimal import Decimal

# Bottle feeding validation
MIN_BOTTLE_OZ = Decimal("0.1")
MAX_BOTTLE_OZ = Decimal("50")
BOTTLE_MAX_DIGITS = 4
BOTTLE_DECIMAL_PLACES = 1

# Breast feeding validation
MIN_BREAST_MINUTES = 1
MAX_BREAST_MINUTES = 180

# UI constants
BOTTLE_STEP = Decimal("0.1")
