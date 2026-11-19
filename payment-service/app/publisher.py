import os, asyncio, json
from google.cloud import pubsub_v1

_publisher = None
_topic_path = None

async def init_publisher():
    global _publisher, _topic_path
    _publisher = pubsub_v1.PublisherClient()
    project_id = os.environ["PUBSUB_PROJECT_ID"]
    topic_id = "invariant-events"
    _topic_path = _publisher.topic_path(project_id, topic_id)
    # Ensure topic exists (idempotent)
    try:
        _publisher.create_topic(request={"name": _topic_path})
    except Exception:
        pass

async def publish_event(event_type: str, transaction_ref: str, entity_id: str, data: dict):
    import uuid
    from datetime import datetime, timezone
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "source_system": "payment-service",
        "transaction_ref": transaction_ref,
        "entity_id": entity_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    payload = json.dumps(event).encode("utf-8")
    loop = asyncio.get_event_loop()
    future = await loop.run_in_executor(
        None,
        lambda: _publisher.publish(
            _topic_path, payload,
            event_type=event_type,
            source_system="payment-service",
            transaction_ref=transaction_ref,
        )
    )
    await loop.run_in_executor(None, future.result)
    return event["event_id"]
