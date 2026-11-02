"""Target Application — Core Payment Order Processing Engine."""
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


def process_payment_order(inbound_order_envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Processes, validates, and calculates final invoice amounts for a customer order.

    Workflow:
    1. Schema validation (validators.validate_order_schema)
    2. Loyalty tier extraction (validators.extract_tier_multiplier)
    3. Itemized subtotal calculation
    4. Promotional discount calculation (calculate_discount)
    5. Jurisdiction tax calculation (validators.calculate_tax_bracket)
    """
    # 1. Validate Schema
    validated_order_record = validate_order_schema(inbound_order_envelope)

    # 2. Extract Customer Loyalty Tier (Fails on modern API v2 payloads)
    customer_account_profile = validated_order_record["customer"]
    loyalty_tier_multiplier = extract_tier_multiplier(customer_account_profile)

    # 3. Calculate Subtotal across line items
    cart_item_manifest = validated_order_record["items"]
    itemized_gross_subtotal = sum(
        float(cart_line["price"]) * int(cart_line["quantity"]) for cart_line in cart_item_manifest
    )
    itemized_gross_subtotal = round(itemized_gross_subtotal, 2)

    # 4. Compute Promotional Discounts (Fails on boundary promo slots)
    active_promotions_count = int(validated_order_record.get("active_promos_count", 0))
    deducted_discount_amount = calculate_discount(
        itemized_gross_subtotal, loyalty_tier_multiplier, active_promotions_count
    )

    discounted_net_base = max(0.0, round(itemized_gross_subtotal - deducted_discount_amount, 2))

    # 5. Compute Jurisdiction Tax Liability
    settlement_jurisdiction = validated_order_record.get("jurisdiction", "GLOBAL-DEFAULT")
    statutory_tax_amount = calculate_tax_bracket(discounted_net_base, settlement_jurisdiction)

    settlement_aggregate_total = round(discounted_net_base + statutory_tax_amount, 2)

    return {
        "order_id": validated_order_record["order_id"],
        "subtotal": itemized_gross_subtotal,
        "discount_applied": deducted_discount_amount,
        "net_total": discounted_net_base,
        "tax": statutory_tax_amount,
        "final_total": settlement_aggregate_total,
        "status": "APPROVED",
    }
