import uuid
import structlog
from typing import Optional, Any
from app.models.icef import CanonicalEvent
from app.db.base import get_pool

logger = structlog.get_logger()


class EntityCorrelator:
    def __init__(self):
        # In-memory mapping fallback when DB is offline or in mock tests
        self._memory_refs: dict[str, dict[str, str]] = {}

    async def correlate(self, event: CanonicalEvent, transaction_id: Optional[str] = None) -> Optional[str]:
        """
        Links incoming event to a transaction using explicit reference code,
        order_id, payment_id, or payload hints.
        """
        transaction_ref = (
            event.transaction_correlation.transaction_ref or
            event.entity.correlation_hints.get("transaction_ref") or
            event.data.get("transaction_ref")
        )
        if not transaction_ref:
            # Fall back to entity ID lookup
            system = event.meta.source_system
            entity_id = event.entity.id
            transaction_ref = self._lookup_memory(system, entity_id)

        if not transaction_ref:
            logger.warning("unresolvable_transaction_correlation", event_id=event.meta.event_id)
            return None

        # Record in memory
        self._record_memory(transaction_ref, event.meta.source_system, event.entity.type, event.entity.id)

        # Record in DB if pool is available
        pool = await get_pool()
        if pool and transaction_id:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO entity_references (transaction_id, system_name, entity_type, external_id, entity_snapshot)
                        VALUES ($1, $2, $3, $4, $5::jsonb)
                        ON CONFLICT (system_name, entity_type, external_id) DO NOTHING
                    """, uuid.UUID(transaction_id), event.meta.source_system, event.entity.type, event.entity.id,
                        __import__("json").dumps(event.data))
            except Exception as e:
                logger.warning("db_correlation_failed", error=str(e))

        return transaction_ref

    def _record_memory(self, txn_ref: str, system: str, entity_type: str, entity_id: str):
        if txn_ref not in self._memory_refs:
            self._memory_refs[txn_ref] = {}
        key = f"{system}:{entity_type}"
        self._memory_refs[txn_ref][key] = entity_id

    def _lookup_memory(self, system: str, entity_id: str) -> Optional[str]:
        for txn_ref, mapping in self._memory_refs.items():
            for key, val in mapping.items():
                if val == entity_id:
                    return txn_ref
        return None

    def get_references(self, txn_ref: str) -> dict[str, str]:
        return self._memory_refs.get(txn_ref, {})

