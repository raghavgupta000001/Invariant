"""
Simulated failure state for chaos/testing scenarios.
Toggle failure modes via environment variables or at runtime.
"""
import os

_failure_mode: str | None = None  # e.g. "db_error", "pubsub_error", "slow"

def get_failure_mode() -> str | None:
    return _failure_mode or os.environ.get("FAILURE_MODE")

def set_failure_mode(mode: str | None):
    global _failure_mode
    _failure_mode = mode
