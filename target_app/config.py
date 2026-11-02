"""Target Application — Global Financial System Configuration Boundaries & Constants."""
from typing import Dict, Any

API_VERSION: str = "2026-v2.1"
DEFAULT_CURRENCY: str = "USD"

# Promotion denominator boundary ceiling (promos >= 4 triggers algorithmic singularity in unpatched code)
MAX_DISCOUNT_SLOTS: int = 4
MAX_ALLOWABLE_DISCOUNT_PERCENT: float = 0.50  # Hard ceiling: 50% max statutory rebate

# Regional VAT / sales tax coefficients mapped by settlement territory code
JURISDICTION_TAX_RATES: Dict[str, float] = {
    "US-CA": 0.0925,
    "US-NY": 0.08875,
    "US-TX": 0.0825,
    "EU-DE": 0.1900,
    "GLOBAL-DEFAULT": 0.1000,
}

# Transaction processing threshold limits for fraud and memory protection
SYSTEM_LIMITS: Dict[str, Any] = {
    "MAX_ORDER_VALUE": 1_000_000.0,
    "MIN_ORDER_VALUE": 0.50,
    "MAX_ITEMS_PER_ORDER": 500,
}
