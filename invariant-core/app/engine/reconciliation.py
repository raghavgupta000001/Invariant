import httpx
import structlog
from typing import Any, Optional
from app.config import ORDER_SERVICE_URL, PAYMENT_SERVICE_URL, ERP_SERVICE_URL, SHIPPING_SERVICE_URL
from app.models.domain import IncidentType, IncidentSeverity, InvariantViolation

logger = structlog.get_logger()


class ReconciliationEngine:
    def __init__(
        self,
        order_url: str = ORDER_SERVICE_URL,
        payment_url: str = PAYMENT_SERVICE_URL,
        erp_url: str = ERP_SERVICE_URL,
        shipping_url: str = SHIPPING_SERVICE_URL,
    ):
        self.urls = {
            "order": order_url,
            "payment": payment_url,
            "erp": erp_url,
            "shipping": shipping_url,
        }

    async def sweep_transaction(self, txn_ref: str, local_txn_state: dict[str, Any]) -> list[InvariantViolation]:
        """
        Polls source-of-truth service APIs for this transaction and detects silent failures.
        """
        violations: list[InvariantViolation] = []
        remote_state = {}

        async with httpx.AsyncClient(timeout=4.0) as client:
            # Query order service
            try:
                res = await client.get(f"{self.urls['order']}/orders/{txn_ref}")
                remote_state["order"] = res.json() if res.status_code == 200 else None
            except Exception:
                remote_state["order"] = None

            # Query payment service
            try:
                res = await client.get(f"{self.urls['payment']}/payments?transaction_ref={txn_ref}")
                remote_state["payment"] = res.json() if res.status_code == 200 else None
            except Exception:
                remote_state["payment"] = None

            # Query ERP service
            try:
                res = await client.get(f"{self.urls['erp']}/erp/orders/{txn_ref}")
                remote_state["erp"] = res.json() if res.status_code == 200 else None
            except Exception:
                remote_state["erp"] = None

            # Query shipping service
            try:
                res = await client.get(f"{self.urls['shipping']}/shipments/{txn_ref}")
                remote_state["shipping"] = res.json() if res.status_code == 200 else None
            except Exception:
                remote_state["shipping"] = None

        # SILENT FAILURE CHECK 1: Payment captured in payment gateway, but ERP has NO record
        has_payment = bool(remote_state.get("payment"))
        has_erp = bool(remote_state.get("erp"))
        if has_payment and not has_erp:
            violations.append(InvariantViolation(
                invariant_name="payment_without_erp_order",
                severity=IncidentSeverity.CRITICAL,
                transaction_ref=txn_ref,
                incident_type=IncidentType.SILENT_FAILURE,
                description="Reconciliation sweep confirmed payment exists in gateway, but ERP has no sales order record.",
                evidence={
                    "gateway_payment_found": True,
                    "erp_sales_order_found": False,
                    "source": "reconciliation_sweep",
                },
            ))

        # SILENT FAILURE CHECK 2: Amount mismatch between Order and Payment
        if remote_state.get("order") and remote_state.get("payment"):
            order_amount = remote_state["order"].get("total_amount_paise")
            payment_list = remote_state["payment"]
            if isinstance(payment_list, list) and len(payment_list) > 0:
                payment_amount = payment_list[0].get("amount_paise")
                if order_amount and payment_amount and abs(order_amount - payment_amount) > 100:
                    violations.append(InvariantViolation(
                        invariant_name="amount_consistency",
                        severity=IncidentSeverity.CRITICAL,
                        transaction_ref=txn_ref,
                        incident_type=IncidentType.DATA_MISMATCH,
                        description=f"Reconciliation sweep detected amount mismatch: order={order_amount} vs payment={payment_amount}.",
                        evidence={
                            "order_amount_paise": order_amount,
                            "payment_amount_paise": payment_amount,
                            "source": "reconciliation_sweep",
                        },
                    ))

        return violations

    async def run_sweep_all(self, active_transactions: list[dict[str, Any]]) -> list[InvariantViolation]:
        all_violations = []
        for txn in active_transactions:
            txn_ref = txn.get("transaction_ref")
            if txn_ref:
                violations = await self.sweep_transaction(txn_ref, txn)
                all_violations.extend(violations)
        return all_violations

