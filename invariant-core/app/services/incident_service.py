import uuid
from typing import Any, Optional
from datetime import datetime, timezone
from app.models.domain import InvariantViolation, IncidentSeverity, IncidentType


class IncidentService:
    def __init__(self):
        self._incidents: dict[str, dict[str, Any]] = {}

    def raise_incident(self, violation: InvariantViolation) -> dict[str, Any]:
        # Deduplication check: do not raise duplicate open incidents for same transaction & invariant
        for inc in self._incidents.values():
            if (
                inc["transaction_ref"] == violation.transaction_ref and
                inc["invariant_name"] == violation.invariant_name and
                inc["state"] == "OPEN"
            ):
                return inc

        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        incident = {
            "id": incident_id,
            "transaction_ref": violation.transaction_ref,
            "invariant_name": violation.invariant_name,
            "incident_type": violation.incident_type.value,
            "severity": violation.severity.value,
            "state": "OPEN",
            "description": violation.description,
            "evidence": violation.evidence,
            "detected_at": violation.detected_at.isoformat(),
            "resolved_at": None,
            "investigation": None,
            "recovery_plan_id": None,
        }
        self._incidents[incident_id] = incident
        return incident

    def get_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        return self._incidents.get(incident_id)

    def list_incidents(
        self,
        transaction_ref: Optional[str] = None,
        state: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        results = list(self._incidents.values())
        if transaction_ref:
            results = [i for i in results if i["transaction_ref"] == transaction_ref]
        if state:
            results = [i for i in results if i["state"] == state]
        if severity:
            results = [i for i in results if i["severity"] == severity]
        return results

    def update_incident_state(self, incident_id: str, new_state: str) -> Optional[dict[str, Any]]:
        inc = self._incidents.get(incident_id)
        if inc:
            inc["state"] = new_state
            if new_state == "RESOLVED":
                inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
            return inc
        return None

