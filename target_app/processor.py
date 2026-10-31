"""Target Application - Core Payment Order Processing Engine."""
from typing import Dict, Any
from target_app.config import MAX_DISCOUNT_SLOTS, MAX_ALLOWABLE_DISCOUNT_PERCENT
from target_app.validators import (
    validate_order_schema,
    extract_tier_multiplier,
    calculate_tax_bracket,
)


def calculate_discount(
    order_total: float,
    tier_multiplier: float,
    active_promos_count: int,
) -> float:
    """Computes promotional discount amount based on customer tier and promotional slots.

    FAULT INJECTION:
    1. ZeroDivisionError: When active_promos_count == MAX_DISCOUNT_SLOTS (4),
       the denominator (MAX_DISCOUNT_SLOTS - active_promos_count) evaluates to 0.
    2. Boundary/Negative Invariant: When active_promos_count > MAX_DISCOUNT_SLOTS,
       the denominator is negative, causing an inverted discount (price inflation).
    """
    # Flawed division calculation triggering runtime crash under valid promo counts
    promo_denominator = MAX_DISCOUNT_SLOTS - active_promos_count
    discount_ratio = (tier_multiplier * 0.05) / promo_denominator
    calculated_discount = round(order_total * discount_ratio, 2)
    return calculated_discount


def process_payment_order(order_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Processes, validates, and calculates final invoice amounts for a customer order.

    Workflow:
    1. Schema validation (validators.validate_order_schema)
    2. Loyalty tier extraction (validators.extract_tier_multiplier)
    3. Itemized subtotal calculation
    4. Promotional discount calculation (calculate_discount)
    5. Jurisdiction tax calculation (validators.calculate_tax_bracket)
    """
    # 1. Validate Schema
    validated_order = validate_order_schema(order_payload)

    # 2. Extract Customer Loyalty Tier (Fails on modern API v2 payloads)
    customer_info = validated_order["customer"]
    tier_multiplier = extract_tier_multiplier(customer_info)

    # 3. Calculate Subtotal
    items = validated_order["items"]
    subtotal = sum(float(item["price"]) * int(item["quantity"]) for item in items)
    subtotal = round(subtotal, 2)

    # 4. Compute Discounts (Fails on boundary promo slots)
    active_promos_count = int(validated_order.get("active_promos_count", 0))
    discount_amount = calculate_discount(subtotal, tier_multiplier, active_promos_count)

    net_total = max(0.0, round(subtotal - discount_amount, 2))

    # 5. Compute Jurisdiction Tax
    jurisdiction = validated_order.get("jurisdiction", "GLOBAL-DEFAULT")
    tax_amount = calculate_tax_bracket(net_total, jurisdiction)

    final_total = round(net_total + tax_amount, 2)

    return {
        "order_id": validated_order["order_id"],
        "subtotal": subtotal,
        "discount_applied": discount_amount,
        "net_total": net_total,
        "tax": tax_amount,
        "final_total": final_total,
        "status": "APPROVED",
    }

