import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Any
from app.models.icef import CanonicalEvent


class NormalizationResult:
    def __init__(
        self,
        success: bool,
        event: Optional[CanonicalEvent] = None,
        error: Optional[str] = None,
        is_recognized: bool = True,
    ):
        self.success = success
        self.event = event
        self.error = error
        self.is_recognized = is_recognized

    @classmethod
    def ok(cls, event: CanonicalEvent) -> "NormalizationResult":
        return cls(success=True, event=event)

    @classmethod
    def fail(cls, error: str) -> "NormalizationResult":
        return cls(success=False, error=error)

    @classmethod
    def unrecognized(cls, raw_type: str) -> "NormalizationResult":
        return cls(success=False, error=f"Unrecognized event type: {raw_type}", is_recognized=False)


def compute_idempotency_key(source_system: str, event_type: str, source_event_id: str) -> str:
    raw = f"{source_system}::{event_type}::{source_event_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BaseNormalizer(ABC):
    @property
    @abstractmethod
    def source_system(self) -> str:
        pass

    @abstractmethod
    def normalize(self, raw: dict, raw_bytes: bytes = b"", headers: dict = {}) -> NormalizationResult:
        pass

    def verify_signature(self, payload_bytes: bytes, signature: str, secret: str) -> bool:
        return True

