import structlog
from typing import Any, Optional
from app.normalizers.base import BaseNormalizer
from app.normalizers.razorpay import RazorpayNormalizer
from app.normalizers.shopify import ShopifyNormalizer
from app.normalizers.erp import ERPNormalizer
from app.normalizers.shipping import ShippingNormalizer
from app.engine.correlation import EntityCorrelator
from app.engine.state_machine import TransactionStateMachine
from app.engine.invariants import InvariantChecker
from app.services.incident_service import IncidentService

logger = structlog.get_logger()


class IngestionService:
    def __init__(
        self,
        state_machine: Optional[TransactionStateMachine] = None,
        correlator: Optional[EntityCorrelator] = None,
        checker: Optional[InvariantChecker] = None,
        incident_service: Optional[IncidentService] = None,
    ):
        self.state_machine = state_machine or TransactionStateMachine()
        self.correlator = correlator or EntityCorrelator()
        self.checker = checker or InvariantChecker()
        self.incident_service = incident_service or IncidentService()

        self.normalizers: dict[str, BaseNormalizer] = {
            "razorpay": RazorpayNormalizer(),
            "shopify": ShopifyNormalizer(),
            "erp": ERPNormalizer(),
            "shipping": ShippingNormalizer(),
            "order-service": ShopifyNormalizer(),
            "payment-service": RazorpayNormalizer(),
            "erp-service": ERPNormalizer(),
            "shipping-service": ShippingNormalizer(),
        }

    async def ingest(
        self,
        source: str,
        raw_payload: dict[str, Any],
        raw_bytes: bytes = b"",
        headers: dict[str, str] = {},
    ) -> dict[str, Any]:
        normalizer = self.normalizers.get(source.lower())
        if not normalizer:
            return {"status": "REJECTED", "error": f"Unknown event source: {source}"}

        norm_result = normalizer.normalize(raw_payload, raw_bytes, headers)
        if not norm_result.success or not norm_result.event:
            return {"status": "NORMALIZATION_FAILED", "error": norm_result.error}

        event = norm_result.event

        # Correlate event with transaction
        txn_ref = await self.correlator.correlate(event)
        if not txn_ref:
            return {
                "status": "UNRESOLVABLE_CORRELATION",
                "event_id": event.meta.event_id,
                "error": "Could not correlate event to a business transaction",
            }

        # Apply to state machine
        txn, ordering_issue = self.state_machine.apply_event(event, txn_ref)

        # Evaluate business invariants
        violations = self.checker.evaluate_transaction(txn)
        incidents_raised = []

        for v in violations:
            self.state_machine.mark_inconsistent(txn_ref, v.description)
            inc = self.incident_service.raise_incident(v)
            incidents_raised.append(inc["id"])

        return {
            "status": "PROCESSED",
            "event_id": event.meta.event_id,
            "idempotency_key": event.meta.idempotency_key,
            "canonical_event_type": event.meta.canonical_event_type,
            "transaction_ref": txn_ref,
            "transaction_state": txn["state"],
            "incidents_raised": incidents_raised,
            "ordering_issue": ordering_issue,
        }

