import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.engine.reconciliation import ReconciliationEngine
from app.models.domain import IncidentType


def _mock_res(status_code: int, data: dict):
    res = MagicMock(spec=httpx.Response)
    res.status_code = status_code
    res.json.return_value = data
    return res


@pytest.mark.asyncio
async def test_reconciliation_detects_silent_failure():
    """
    Simulates:
    - Gateway has payment record
    - ERP has NO sales order (HTTP 404 / empty)
    Reconciliation sweep must flag SILENT_FAILURE.
    """
    engine = ReconciliationEngine()
    txn_ref = "TXN-SILENT-FAIL"

    responses = {
        f"http://localhost:8001/orders/{txn_ref}": _mock_res(200, {"total_amount_paise": 6000000}),
        f"http://localhost:8002/payments?transaction_ref={txn_ref}": _mock_res(200, [{"id": "p1", "amount_paise": 6000000}]),
        f"http://localhost:8003/erp/orders/{txn_ref}": _mock_res(404, {}),  # MISSING in ERP!
        f"http://localhost:8004/shipments/{txn_ref}": _mock_res(404, {}),
    }

    async def mock_get(self_client, url, **kwargs):
        return responses.get(url, _mock_res(404, {}))

    with patch.object(httpx.AsyncClient, "get", mock_get):
        violations = await engine.sweep_transaction(txn_ref, {})

    assert len(violations) >= 1
    v = next(vi for vi in violations if vi.invariant_name == "payment_without_erp_order")
    assert v.incident_type == IncidentType.SILENT_FAILURE
    assert v.evidence["gateway_payment_found"] is True
    assert v.evidence["erp_sales_order_found"] is False

