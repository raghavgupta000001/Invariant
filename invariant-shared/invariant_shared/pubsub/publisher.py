import asyncio, os
from google.cloud import pubsub_v1
from invariant_shared.models.events import CanonicalEvent

class EventPublisher:
    def __init__(self, project_id: str | None = None, topic_id: str = "invariant-events"):
        self.project_id = project_id or os.environ["PUBSUB_PROJECT_ID"]
        self.topic_id = topic_id
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_id)

    async def publish(self, event: CanonicalEvent) -> str:
        data = event.model_dump_json().encode("utf-8")
        loop = asyncio.get_event_loop()
        future = await loop.run_in_executor(
            None,
            lambda: self.publisher.publish(
                self.topic_path,
                data,
                event_type=event.event_type.value,
                source_system=event.source_system,
                transaction_ref=event.transaction_ref,
            )
        )
        return await loop.run_in_executor(None, future.result)

    async def ensure_topic_exists(self):
        """Create topic if it doesn't exist (idempotent, for local emulator)."""
        try:
            self.publisher.create_topic(request={"name": self.topic_path})
        except Exception:
            pass  # Already exists
