"""Target Application — Ingestion Schema Validators and Fiscal Bracket Computations.

Enforces structural schema invariants, quantity allocation limits, and jurisdiction-specific
taxation coefficients for inbound order execution pipelines.
"""
from __future__ import annotations

from typing import Any, Dict
from target_app.config import JURISDICTION_TAX_RATES, SYSTEM_LIMITS


class OrderIngestionValidationError(ValueError):
    """Raised when an inbound transaction violates boundary specifications or payload contracts."""
    pass


def validate_order_schema(raw_order_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validates structural schema and business boundary limits of an incoming transaction payload.
    
    Ensures mandatory envelope fields are present and enforces hard bounds on item allocations
    to prevent algorithmic memory exhaustion attacks.
    """
    mandatory_envelope_keys = {"order_id", "customer", "items", "jurisdiction"}
    omitted_contract_keys = mandatory_envelope_keys - set(raw_order_payload.keys())
    if omitted_contract_keys:
        raise OrderIngestionValidationError(
            f"Schema contract violation: missing mandatory payload attributes: {sorted(list(omitted_contract_keys))}"
        )

    cart_line_items = raw_order_payload["items"]
    if not isinstance(cart_line_items, list) or len(cart_line_items) == 0:
        raise OrderIngestionValidationError(
            "Invalid items list: must be non-empty list of item records."
        )

    cumulative_unit_quantity = sum(cart_record.get("quantity", 0) for cart_record in cart_line_items)
    if cumulative_unit_quantity > SYSTEM_LIMITS["MAX_ITEMS_PER_ORDER"]:
        raise OrderIngestionValidationError(
            f"Order bounds breach: cumulative units ({cumulative_unit_quantity}) exceeds MAX_ITEMS_PER_ORDER ceiling ({SYSTEM_LIMITS['MAX_ITEMS_PER_ORDER']})."
        )

    return raw_order_payload


def extract_tier_multiplier(customer_info: Dict[str, Any]) -> float:
    """Calculates customer loyalty tier multiplier for promotional discounts.

    NOTE: Upstream API v2 deprecated the direct flat string key 'tier' in favor of
    nested 'tier_profile' object, causing unhandled KeyError in unmigrated call sites.
    """
    # FAULT INJECTION (Multi-file bug):
    # Directly accesses deprecated 'tier' key instead of inspecting 'tier_profile'
    legacy_tier_key = customer_info["tier"]

    loyalty_tier_coefficients = {
        "STANDARD": 1.0,
        "SILVER": 1.15,
        "GOLD": 1.30,
        "PLATINUM": 1.50,
    }
    return loyalty_tier_coefficients.get(str(legacy_tier_key).upper(), 1.0)


def calculate_tax_bracket(pre_tax_subtotal: float, settlement_jurisdiction: str) -> float:
    """Computes statutory sales tax / VAT liability for the designated regional jurisdiction."""
    statutory_tax_coefficient = JURISDICTION_TAX_RATES.get(
        settlement_jurisdiction, JURISDICTION_TAX_RATES["GLOBAL-DEFAULT"]
    )
    return round(pre_tax_subtotal * statutory_tax_coefficient, 2)
