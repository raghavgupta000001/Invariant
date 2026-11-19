from datetime import datetime, timezone
from app.normalizers.base import BaseNormalizer, NormalizationResult, compute_idempotency_key
from app.models.icef import CanonicalEvent, ICEFMeta, ICEFEntity, ICEFCorrelation


class ShopifyNormalizer(BaseNormalizer):
    @property
    def source_system(self) -> str:
        return "shopify"

    EVENT_TYPE_MAP = {
        "orders/create": "order.created",
        "orders/cancelled": "order.cancelled",
        "order.created": "order.created",
        "order.cancelled": "order.cancelled",
    }

    def normalize(self, raw: dict, raw_bytes: bytes = b"", headers: dict = {}) -> NormalizationResult:
        raw_event_type = headers.get("x-shopify-topic") or raw.get("event_type") or raw.get("event")
        canonical_type = self.EVENT_TYPE_MAP.get(raw_event_type)
        if not canonical_type:
            return NormalizationResult.unrecognized(str(raw_event_type))

        order_data = raw.get("data", raw)
        source_event_id = str(order_data.get("id") or order_data.get("order_id") or raw.get("entity_id", "unknown_order"))
        transaction_ref = (
            raw.get("transaction_ref") or
            order_data.get("transaction_ref") or
            order_data.get("note") or
            f"TXN-{source_event_id[:8]}"
        )

        idempotency_key = compute_idempotency_key(self.source_system, canonical_type, source_event_id)

        occurred_ts = order_data.get("created_at") or raw.get("occurred_at")
        if isinstance(occurred_ts, str):
            try:
                occurred_at = datetime.fromisoformat(occurred_ts.replace("Z", "+00:00"))
            except Exception:
                occurred_at = datetime.now(timezone.utc)
        else:
            occurred_at = datetime.now(timezone.utc)

        amount_paise = order_data.get("total_amount_paise")
        if amount_paise is None and "total_price" in order_data:
            try:
                amount_paise = int(float(order_data["total_price"]) * 100)
            except Exception:
                amount_paise = 0

        event = CanonicalEvent(
            meta=ICEFMeta(
                idempotency_key=idempotency_key,
                source_system=self.source_system,
                source_event_id=source_event_id,
                raw_event_type=str(raw_event_type),
                canonical_event_type=canonical_type,
                occurred_at=occurred_at,
                signature_verified=bool(headers.get("x-signature-valid", False)),
            ),
            entity=ICEFEntity(
                type="order",
                id=source_event_id,
                correlation_hints={"transaction_ref": transaction_ref, "email": order_data.get("email") or order_data.get("customer_email")},
            ),
            data={
                "order_id": source_event_id,
                "customer_email": order_data.get("customer_email") or order_data.get("email"),
                "total_amount_paise": amount_paise or 0,
                "amount_display": (amount_paise or 0) / 100,
                "currency": order_data.get("currency", "INR"),
                "items": order_data.get("items") or order_data.get("line_items", []),
                "status": order_data.get("status", "CREATED"),
            },
            transaction_correlation=ICEFCorrelation(
                transaction_ref=transaction_ref,
                confidence=1.0,
                method="EXPLICIT_ID",
            ),
        )
        return NormalizationResult.ok(event)

