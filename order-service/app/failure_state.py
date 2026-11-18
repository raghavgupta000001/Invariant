# In-memory failure injection state (set by simulator orchestrator)
from typing import Optional

_active_failures: dict[str, dict] = {}

def set_failure(mode: str, options: dict = {}):
    _active_failures[mode] = options

def clear_failure(mode: str):
    _active_failures.pop(mode, None)

def clear_all():
    _active_failures.clear()

def is_active(mode: str) -> bool:
    return mode in _active_failures

def get_options(mode: str) -> dict:
    return _active_failures.get(mode, {})
