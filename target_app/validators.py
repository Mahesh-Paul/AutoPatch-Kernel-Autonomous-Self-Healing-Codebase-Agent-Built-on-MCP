"""Target Application - Order Schema Validators and Tier Multipliers."""
from typing import Dict, Any
from target_app.config import JURISDICTION_TAX_RATES, SYSTEM_LIMITS


def validate_order_schema(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validates structural schema and business limits of an incoming order.

    Raises:
        ValueError: If mandatory keys are absent or quantities exceed limits.
    """
    required_keys = {"order_id", "customer", "items", "jurisdiction"}
    missing = required_keys - set(order_data.keys())
    if missing:
        raise ValueError(f"Schema violation: missing mandatory keys: {sorted(list(missing))}")

    items = order_data["items"]
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("Invalid items list: must be non-empty list of item records.")

    total_items = sum(item.get("quantity", 0) for item in items)
    if total_items > SYSTEM_LIMITS["MAX_ITEMS_PER_ORDER"]:
        raise ValueError(f"Exceeded MAX_ITEMS_PER_ORDER: {total_items}")

    return order_data


def extract_tier_multiplier(customer_info: Dict[str, Any]) -> float:
    """Calculates customer loyalty tier multiplier for promotional discounts.

    NOTE: Upstream API v2 deprecated the direct flat string key 'tier' in favor of
    nested 'tier_profile' object, causing unhandled KeyError in unmigrated call sites.
    """
    # FAULT INJECTION (Multi-file bug):
    # Directly accesses deprecated 'tier' key instead of inspecting 'tier_profile'
    legacy_tier_key = customer_info["tier"]

    tier_map = {
        "STANDARD": 1.0,
        "SILVER": 1.15,
        "GOLD": 1.30,
        "PLATINUM": 1.50,
    }
    return tier_map.get(str(legacy_tier_key).upper(), 1.0)


def calculate_tax_bracket(amount: float, jurisdiction: str) -> float:
    """Computes applicable sales/VAT tax for the designated jurisdiction."""
    rate = JURISDICTION_TAX_RATES.get(jurisdiction, JURISDICTION_TAX_RATES["GLOBAL-DEFAULT"])
    return round(amount * rate, 2)
