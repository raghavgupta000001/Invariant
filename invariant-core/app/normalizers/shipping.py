from datetime import datetime, timezone
from app.normalizers.base import BaseNormalizer, NormalizationResult, compute_idempotency_key
from app.models.icef import CanonicalEvent, ICEFMeta, ICEFEntity, ICEFCorrelation


class ShippingNormalizer(BaseNormalizer):
    @property
    def source_system(self) -> str:
        return "shipping"

    EVENT_TYPE_MAP = {
        "shipment.created": "shipment.created",
        "shipment.failed": "shipment.failed",
    }

    def normalize(self, raw: dict, raw_bytes: bytes = b"", headers: dict = {}) -> NormalizationResult:
        raw_event_type = raw.get("event_type") or raw.get("event")
        canonical_type = self.EVENT_TYPE_MAP.get(raw_event_type)
        if not canonical_type:
            return NormalizationResult.unrecognized(str(raw_event_type))

        ship_data = raw.get("data", raw)
        source_event_id = str(ship_data.get("shipment_id") or raw.get("entity_id", "unknown_shipment"))
        transaction_ref = raw.get("transaction_ref") or ship_data.get("transaction_ref")

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
                type="shipment",
                id=source_event_id,
                correlation_hints={"transaction_ref": transaction_ref, "tracking_number": ship_data.get("tracking_number")},
            ),
            data=ship_data,
            transaction_correlation=ICEFCorrelation(
                transaction_ref=transaction_ref,
                confidence=1.0 if transaction_ref else 0.5,
                method="EXPLICIT_ID" if transaction_ref else "HEURISTIC",
            ),
        )
        return NormalizationResult.ok(event)

