from datetime import datetime, timezone
from app.normalizers.base import BaseNormalizer, NormalizationResult, compute_idempotency_key
from app.models.icef import CanonicalEvent, ICEFMeta, ICEFEntity, ICEFCorrelation


class ERPNormalizer(BaseNormalizer):
    @property
    def source_system(self) -> str:
        return "erp"

    EVENT_TYPE_MAP = {
        "erp.order_created": "erp.order_created",
        "erp.order_failed": "erp.order_failed",
        "erp.inventory_reserved": "erp.inventory_reserved",
        "erp.invoice_generated": "erp.invoice_generated",
    }

    def normalize(self, raw: dict, raw_bytes: bytes = b"", headers: dict = {}) -> NormalizationResult:
        raw_event_type = raw.get("event_type") or raw.get("event")
        canonical_type = self.EVENT_TYPE_MAP.get(raw_event_type)
        if not canonical_type:
            return NormalizationResult.unrecognized(str(raw_event_type))

        erp_data = raw.get("data", raw)
        source_event_id = str(erp_data.get("sales_order_id") or erp_data.get("invoice_id") or raw.get("entity_id", "unknown_erp_entity"))
        transaction_ref = raw.get("transaction_ref") or erp_data.get("transaction_ref")

        idempotency_key = compute_idempotency_key(self.source_system, canonical_type, source_event_id)

        occurred_ts = raw.get("occurred_at")
        if isinstance(occurred_ts, str):
            try:
                occurred_at = datetime.fromisoformat(occurred_ts.replace("Z", "+00:00"))
            except Exception:
                occurred_at = datetime.now(timezone.utc)
        else:
            occurred_at = datetime.now(timezone.utc)

        event = CanonicalEvent(
            meta=ICEFMeta(
                idempotency_key=idempotency_key,
                source_system=self.source_system,
                source_event_id=source_event_id,
                raw_event_type=str(raw_event_type),
                canonical_event_type=canonical_type,
                occurred_at=occurred_at,
                signature_verified=True,
            ),
            entity=ICEFEntity(
                type="sales_order" if "order" in canonical_type else ("inventory" if "inventory" in canonical_type else "invoice"),
                id=source_event_id,
                correlation_hints={"transaction_ref": transaction_ref},
            ),
            data=erp_data,
            transaction_correlation=ICEFCorrelation(
                transaction_ref=transaction_ref,
                confidence=1.0 if transaction_ref else 0.5,
                method="EXPLICIT_ID" if transaction_ref else "HEURISTIC",
            ),
        )
        return NormalizationResult.ok(event)

