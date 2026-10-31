"""Target Application - Comprehensive Regression Suite.

This suite contains both passing baseline tests and failing tests reflecting
real-world regressions:
1. ZeroDivisionError on boundary promotion slots in processor.py
2. KeyError on modern API v2 tier profile schema in validators.py
"""
import unittest
from target_app.processor import process_payment_order, calculate_discount


class TestPaymentOrderProcessor(unittest.TestCase):

    def test_standard_order_processing_success(self):
        """Verify baseline order processing with valid legacy customer schema."""
        order_payload = {
            "order_id": "ORD-2026-001",
            "customer": {
                "customer_id": "CUST-992",
                "tier": "GOLD",
            },
            "items": [
                {"sku": "SKU-A1", "price": 50.0, "quantity": 2},
                {"sku": "SKU-B2", "price": 25.0, "quantity": 2},
            ],
            "active_promos_count": 0,
            "jurisdiction": "US-CA",
        }

        result = process_payment_order(order_payload)

        self.assertEqual(result["order_id"], "ORD-2026-001")
        self.assertEqual(result["subtotal"], 150.0)
        self.assertEqual(result["status"], "APPROVED")
        self.assertGreater(result["final_total"], 0.0)

    def test_boundary_promo_crash_zero_division(self):
        """REGRESSION TEST: Order with active_promos_count matching MAX_DISCOUNT_SLOTS (4).

        Expected: Should apply valid bounded promotional discount.
        Current Bug: Crashing with ZeroDivisionError in target_app/processor.py line 25.
        """
        order_payload = {
            "order_id": "ORD-2026-002",
            "customer": {
                "customer_id": "CUST-104",
                "tier": "SILVER",
            },
            "items": [
                {"sku": "SKU-ENTERPRISE", "price": 200.0, "quantity": 1},
            ],
            "active_promos_count": 4,  # Triggers division by (4 - 4) = 0!
            "jurisdiction": "US-NY",
        }

        # In unpatched code, this will raise ZeroDivisionError
        result = process_payment_order(order_payload)
        self.assertEqual(result["order_id"], "ORD-2026-002")
        self.assertLessEqual(result["discount_applied"], result["subtotal"])

    def test_schema_v2_migration_payload(self):
        """REGRESSION TEST: Upstream modernized payload using nested tier_profile.

        Expected: extract_tier_multiplier in validators.py extracts tier safely.
        Current Bug: Crashing with KeyError: 'tier' in target_app/validators.py line 34.
        """
        order_payload = {
            "order_id": "ORD-2026-003",
            "customer": {
                "customer_id": "CUST-551",
                "tier_profile": {
                    "tier_level": "PLATINUM",
                    "loyalty_score": 980,
                },
            },
            "items": [
                {"sku": "SKU-PREMIUM", "price": 500.0, "quantity": 1},
            ],
            "active_promos_count": 1,
            "jurisdiction": "EU-DE",
        }

        # In unpatched code, this will raise KeyError: 'tier'
        result = process_payment_order(order_payload)
        self.assertEqual(result["order_id"], "ORD-2026-003")
        self.assertGreater(result["discount_applied"], 0.0)

    def test_invalid_empty_order_items(self):
        """Verify schema validator enforces non-empty item requirements."""
        order_payload = {
            "order_id": "ORD-2026-004",
            "customer": {"tier": "STANDARD"},
            "items": [],
            "jurisdiction": "GLOBAL-DEFAULT",
        }

        with self.assertRaises(ValueError) as ctx:
            process_payment_order(order_payload)
        self.assertIn("Invalid items list", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

