from dataclasses import dataclass
from typing import Any, Callable, Optional
from datetime import datetime, timezone, timedelta
from app.models.domain import IncidentType, IncidentSeverity, InvariantViolation


@dataclass
class InvariantRule:
    name: str
    description: str
    severity: IncidentSeverity
    incident_type: IncidentType
    evaluator: Callable[[dict[str, Any]], Optional[InvariantViolation]]


def check_payment_without_erp_order(txn: dict[str, Any]) -> Optional[InvariantViolation]:
    steps = txn.get("steps", {})
    payment_done = steps.get("payment_captured", {}).get("state") == "COMPLETED"
    erp_done = steps.get("erp_order_created", {}).get("state") == "COMPLETED"

    if payment_done and not erp_done:
        return InvariantViolation(
            invariant_name="payment_without_erp_order",
            severity=IncidentSeverity.CRITICAL,
            transaction_ref=txn["transaction_ref"],
            incident_type=IncidentType.MISSING_STEP,
            description="Payment has been captured but no corresponding ERP order exists.",
            evidence={
                "payment_captured": True,
                "erp_order_created": False,
                "payment_data": steps.get("payment_captured", {}).get("data"),
            },
        )
    return None


def check_amount_consistency(txn: dict[str, Any]) -> Optional[InvariantViolation]:
    steps = txn.get("steps", {})
    order_data = steps.get("order_created", {}).get("data")
    payment_data = steps.get("payment_captured", {}).get("data")

    if order_data and payment_data:
        order_amount = order_data.get("total_amount_paise")
        payment_amount = payment_data.get("amount_paise")

        if order_amount is not None and payment_amount is not None:
            # Allow at most ₹1 (100 paise) rounding tolerance
            diff = abs(order_amount - payment_amount)
            if diff > 100:
                return InvariantViolation(
                    invariant_name="amount_consistency",
                    severity=IncidentSeverity.CRITICAL,
                    transaction_ref=txn["transaction_ref"],
                    incident_type=IncidentType.DATA_MISMATCH,
                    description=f"Payment amount ({payment_amount} paise) differs from order amount ({order_amount} paise).",
                    evidence={
                        "order_amount_paise": order_amount,
                        "payment_amount_paise": payment_amount,
                        "difference_paise": diff,
                    },
                )
    return None


def check_no_shipment_without_inventory(txn: dict[str, Any]) -> Optional[InvariantViolation]:
    steps = txn.get("steps", {})
    shipment_done = steps.get("shipment_created", {}).get("state") == "COMPLETED"
    inventory_done = steps.get("inventory_reserved", {}).get("state") == "COMPLETED"

    if shipment_done and not inventory_done:
        return InvariantViolation(
            invariant_name="no_shipment_without_inventory",
            severity=IncidentSeverity.HIGH,
            transaction_ref=txn["transaction_ref"],
            incident_type=IncidentType.ORDERING_VIOLATION,
            description="Shipment was created without a confirmed inventory reservation.",
            evidence={"shipment_completed": True, "inventory_reserved": False},
        )
    return None


def check_no_shipment_without_payment(txn: dict[str, Any]) -> Optional[InvariantViolation]:
    steps = txn.get("steps", {})
    shipment_done = steps.get("shipment_created", {}).get("state") == "COMPLETED"
    payment_done = steps.get("payment_captured", {}).get("state") == "COMPLETED"

    if shipment_done and not payment_done:
        return InvariantViolation(
            invariant_name="no_shipment_without_payment",
            severity=IncidentSeverity.CRITICAL,
            transaction_ref=txn["transaction_ref"],
            incident_type=IncidentType.ORDERING_VIOLATION,
            description="Shipment was initiated for an order that has not been successfully paid.",
            evidence={"shipment_completed": True, "payment_captured": False},
        )
    return None


def check_sla_breach(txn: dict[str, Any], max_age_seconds: int = 300) -> Optional[InvariantViolation]:
    if txn.get("state") == "IN_PROGRESS":
        created_at = txn.get("created_at")
        if created_at:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - created_at).total_seconds()
            if age > max_age_seconds:
                return InvariantViolation(
                    invariant_name="sla_breach_detection",
                    severity=IncidentSeverity.HIGH,
                    transaction_ref=txn["transaction_ref"],
                    incident_type=IncidentType.SLA_BREACH,
                    description=f"Transaction stuck in IN_PROGRESS for {int(age)} seconds, exceeding SLA threshold.",
                    evidence={"age_seconds": age, "max_age_seconds": max_age_seconds},
                )
    return None


INVARIANT_RULES: list[InvariantRule] = [
    InvariantRule(
        name="payment_without_erp_order",
        description="Every captured payment must have a corresponding ERP order",
        severity=IncidentSeverity.CRITICAL,
        incident_type=IncidentType.MISSING_STEP,
        evaluator=check_payment_without_erp_order,
    ),
    InvariantRule(
        name="amount_consistency",
        description="Payment amount must equal order amount",
        severity=IncidentSeverity.CRITICAL,
        incident_type=IncidentType.DATA_MISMATCH,
        evaluator=check_amount_consistency,
    ),
    InvariantRule(
        name="no_shipment_without_inventory",
        description="Shipments must not be created without inventory reservation",
        severity=IncidentSeverity.HIGH,
        incident_type=IncidentType.ORDERING_VIOLATION,
        evaluator=check_no_shipment_without_inventory,
    ),
    InvariantRule(
        name="no_shipment_without_payment",
        description="Shipments must not be created without captured payment",
        severity=IncidentSeverity.CRITICAL,
        incident_type=IncidentType.ORDERING_VIOLATION,
        evaluator=check_no_shipment_without_payment,
    ),
    InvariantRule(
        name="sla_breach_detection",
        description="Transactions must complete within defined SLA",
        severity=IncidentSeverity.HIGH,
        incident_type=IncidentType.SLA_BREACH,
        evaluator=check_sla_breach,
    ),
]


class InvariantChecker:
    def __init__(self, rules: list[InvariantRule] = INVARIANT_RULES):
        self.rules = rules

    def evaluate_transaction(self, txn: dict[str, Any]) -> list[InvariantViolation]:
        violations = []
        for rule in self.rules:
            v = rule.evaluator(txn)
            if v:
                violations.append(v)
        return violations

    def evaluate_all(self, transactions: list[dict[str, Any]]) -> list[InvariantViolation]:
        all_violations = []
        for txn in transactions:
            all_violations.extend(self.evaluate_transaction(txn))
        return all_violations

