from app.engine.invariants import InvariantChecker
from app.models.domain import IncidentSeverity, IncidentType


def test_payment_without_erp_order_violation():
    checker = InvariantChecker()
    txn = {
        "transaction_ref": "TXN-FAIL-01",
        "state": "IN_PROGRESS",
        "steps": {
            "order_created": {"state": "COMPLETED", "data": {"total_amount_paise": 6000000}},
            "payment_captured": {"state": "COMPLETED", "data": {"amount_paise": 6000000}},
            "erp_order_created": {"state": "PENDING", "data": None},
        }
    }
    violations = checker.evaluate_transaction(txn)
    assert len(violations) == 1
    v = violations[0]
    assert v.invariant_name == "payment_without_erp_order"
    assert v.severity == IncidentSeverity.CRITICAL
    assert v.incident_type == IncidentType.MISSING_STEP


def test_amount_mismatch_violation():
    checker = InvariantChecker()
    txn = {
        "transaction_ref": "TXN-AMOUNT-BUG",
        "state": "IN_PROGRESS",
        "steps": {
            "order_created": {"state": "COMPLETED", "data": {"total_amount_paise": 6000000}},
            # Paid ₹600 (60,000 paise) instead of ₹60,000 (6,000,000 paise)
            "payment_captured": {"state": "COMPLETED", "data": {"amount_paise": 60000}},
            "erp_order_created": {"state": "COMPLETED", "data": {}},
        }
    }
    violations = checker.evaluate_transaction(txn)
    amount_violations = [v for v in violations if v.invariant_name == "amount_consistency"]
    assert len(amount_violations) == 1
    v = amount_violations[0]
    assert v.severity == IncidentSeverity.CRITICAL
    assert v.incident_type == IncidentType.DATA_MISMATCH
    assert v.evidence["difference_paise"] == 5940000


def test_shipment_without_inventory_violation():
    checker = InvariantChecker()
    txn = {
        "transaction_ref": "TXN-NO-INV",
        "state": "IN_PROGRESS",
        "steps": {
            "order_created": {"state": "COMPLETED", "data": {}},
            "payment_captured": {"state": "COMPLETED", "data": {}},
            "erp_order_created": {"state": "COMPLETED", "data": {}},
            "inventory_reserved": {"state": "PENDING", "data": None},
            "shipment_created": {"state": "COMPLETED", "data": {}},
        }
    }
    violations = checker.evaluate_transaction(txn)
    inv_violations = [v for v in violations if v.invariant_name == "no_shipment_without_inventory"]
    assert len(inv_violations) == 1
    assert inv_violations[0].severity == IncidentSeverity.HIGH

