import hmac
import hashlib
from datetime import datetime, timezone
from app.normalizers.base import BaseNormalizer, NormalizationResult, compute_idempotency_key
from app.models.icef import CanonicalEvent, ICEFMeta, ICEFEntity, ICEFCorrelation


class RazorpayNormalizer(BaseNormalizer):
    @property
    def source_system(self) -> str:
        return "razorpay"

    EVENT_TYPE_MAP = {
        "payment.captured": "payment.captured",
        "payment.failed": "payment.failed",
        "payment.authorized": "payment.authorized",
        "refund.created": "payment.refunded",
        "order.paid": "payment.order_paid",
    }

    def verify_signature(self, payload_bytes: bytes, signature: str, secret: str) -> bool:
        if not signature or not secret:
            return False
        expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def normalize(self, raw: dict, raw_bytes: bytes = b"", headers: dict = {}) -> NormalizationResult:
        # Standard Razorpay webhook payload format or direct simulator format
        raw_event_type = raw.get("event") or raw.get("event_type")
        canonical_type = self.EVENT_TYPE_MAP.get(raw_event_type)
        if not canonical_type:
            return NormalizationResult.unrecognized(str(raw_event_type))

        # Handle either standard Razorpay payload {payload: {payment: {entity: ...}}} or canonical dict
        payment_entity = raw.get("payload", {}).get("payment", {}).get("entity", {})
        if not payment_entity and "data" in raw:
            payment_entity = raw["data"]

        source_event_id = payment_entity.get("id") or payment_entity.get("payment_id") or raw.get("entity_id", "unknown_payment")
        transaction_ref = (
            raw.get("transaction_ref") or
            payment_entity.get("notes", {}).get("order_id") or
            payment_entity.get("description") or
            headers.get("x-transaction-ref")
        )

        created_ts = payment_entity.get("created_at") or raw.get("occurred_at")
        if isinstance(created_ts, (int, float)):
            occurred_at = datetime.fromtimestamp(created_ts, tz=timezone.utc)
        elif isinstance(created_ts, str):
            try:
                occurred_at = datetime.fromisoformat(created_ts.replace("Z", "+00:00"))
            except Exception:
                occurred_at = datetime.now(timezone.utc)
        else:
            occurred_at = datetime.now(timezone.utc)

        idempotency_key = payment_entity.get("idempotency_key") or compute_idempotency_key(
            self.source_system, canonical_type, source_event_id
        )

        amount_paise = payment_entity.get("amount") or payment_entity.get("amount_paise", 0)

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
                type="payment",
                id=source_event_id,
                correlation_hints={"transaction_ref": transaction_ref, "order_id": payment_entity.get("order_id")},
            ),
            data={
                "payment_id": source_event_id,
                "amount_paise": amount_paise,
                "amount_display": amount_paise / 100 if amount_paise else 0.0,
                "currency": payment_entity.get("currency", "INR"),
                "method": payment_entity.get("method", "upi"),
                "status": payment_entity.get("status", "captured"),
            },
            transaction_correlation=ICEFCorrelation(
                transaction_ref=transaction_ref,
                confidence=1.0 if transaction_ref else 0.5,
                method="EXPLICIT_ID" if transaction_ref else "HEURISTIC",
            ),
        )
        return NormalizationResult.ok(event)

