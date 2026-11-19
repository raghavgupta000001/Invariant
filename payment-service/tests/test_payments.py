"""
Tests for payment-service.

Run with: pytest payment-service/tests/
Requires a live DATABASE_URL env var pointing at a payments_db with schema applied,
or use pytest-asyncio with a mock pool. These tests use pytest + httpx AsyncClient
against the FastAPI app directly (no real DB needed via dependency override).
"""
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Minimal in-memory "pool" stub so we don't need a real Postgres
# ---------------------------------------------------------------------------

class _FakeConn:
    def __init__(self, store):
        self._store = store  # shared dict: {idempotency_key: row}

    async def fetchrow(self, query, *args):
        q = query.strip().lower()
        if "idempotency_key = $1" in q and "payments" in q:
            key = args[0]
            return self._store["payments_by_idem"].get(key)
        if "refunds" in q and "idempotency_key = $1" in q:
            key = args[0]
            return self._store["refunds_by_idem"].get(key)
        if "payments where id = $1" in q:
            pid = args[0]
            return self._store["payments_by_id"].get(str(pid))
        # INSERT payments
        if "insert into payments" in q:
            row = {
                "id": uuid.uuid4(),
                "transaction_ref": args[0],
                "idempotency_key": args[1],
                "amount_paise": args[2],
                "currency": args[3],
                "method": args[4],
                "status": "CAPTURED",
                "failure_reason": None,
                "refund_id": None,
                "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            }
            self._store["payments_by_idem"][args[1]] = row
            self._store["payments_by_id"][str(row["id"])] = row
            return row
        # INSERT refunds
        if "insert into refunds" in q:
            refund = {
                "id": uuid.uuid4(),
                "payment_id": args[0],
                "amount_paise": args[1],
                "reason": args[2],
                "idempotency_key": args[3],
                "status": "INITIATED",
                "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            }
            self._store["refunds_by_idem"][args[3]] = refund
            return refund
        return None

    async def execute(self, query, *args):
        # UPDATE payments SET status = 'REFUNDED' ...
        if "update payments" in query.lower():
            refund_id, payment_id = args[0], args[1]
            row = self._store["payments_by_id"].get(str(payment_id))
            if row:
                row["status"] = "REFUNDED"
                row["refund_id"] = refund_id

    def get(self, key, default=None):
        return self.get(key, default)


class _FakePool:
    def __init__(self):
        self._store = {
            "payments_by_idem": {},
            "payments_by_id": {},
            "refunds_by_idem": {},
        }

    def acquire(self):
        return _FakeAcquire(self._store)


class _FakeAcquire:
    def __init__(self, store):
        self._conn = _FakeConn(store)

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_pool():
    return _FakePool()


@pytest_asyncio.fixture()
async def client(fake_pool):
    from app.main import app
    import app.db as db_mod
    import app.publisher as pub_mod

    db_mod._pool = fake_pool
    pub_mod._publisher = MagicMock()
    pub_mod._topic_path = "projects/test/topics/invariant-events"

    mock_future = MagicMock()
    mock_future.result = MagicMock(return_value=None)
    pub_mod._publisher.publish = MagicMock(return_value=mock_future)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capture_returns_201(client):
    resp = await client.post("/payments/capture", json={
        "transaction_ref": "TXN-001",
        "amount_paise": 50000,
        "currency": "INR",
        "method": "upi",
        "idempotency_key": "idem-capture-001",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "CAPTURED"
    assert body["amount_paise"] == 50000
    assert body["amount_display"] == 500.0
    assert body["transaction_ref"] == "TXN-001"
    assert "id" in body


@pytest.mark.asyncio
async def test_duplicate_capture_returns_same_payment(client):
    payload = {
        "transaction_ref": "TXN-002",
        "amount_paise": 10000,
        "currency": "INR",
        "method": "card",
        "idempotency_key": "idem-capture-002",
    }
    r1 = await client.post("/payments/capture", json=payload)
    assert r1.status_code == 201
    id1 = r1.json()["id"]

    # Second call with same idempotency_key — must NOT create a new record
    r2 = await client.post("/payments/capture", json=payload)
    # Idempotent response: may return 200 or 201, but same payment ID
    assert r2.status_code in (200, 201)
    assert r2.json()["id"] == id1, "Duplicate capture must return same payment ID"


@pytest.mark.asyncio
async def test_refund_works(client, fake_pool):
    # First capture a payment
    capture_resp = await client.post("/payments/capture", json={
        "transaction_ref": "TXN-003",
        "amount_paise": 20000,
        "currency": "INR",
        "method": "netbanking",
        "idempotency_key": "idem-capture-003",
    })
    assert capture_resp.status_code == 201
    payment_id = capture_resp.json()["id"]

    # Refund it
    refund_resp = await client.post(f"/payments/{payment_id}/refund", json={
        "amount_paise": 20000,
        "reason": "Customer request",
        "idempotency_key": "idem-refund-003",
    })
    assert refund_resp.status_code == 201
    body = refund_resp.json()
    assert "refund_id" in body
    assert body["status"] == "INITIATED"


@pytest.mark.asyncio
async def test_over_refund_returns_400(client):
    # Capture
    capture_resp = await client.post("/payments/capture", json={
        "transaction_ref": "TXN-004",
        "amount_paise": 5000,
        "currency": "INR",
        "method": "wallet",
        "idempotency_key": "idem-capture-004",
    })
    assert capture_resp.status_code == 201
    payment_id = capture_resp.json()["id"]

    # Try to refund more than captured
    refund_resp = await client.post(f"/payments/{payment_id}/refund", json={
        "amount_paise": 9999,
        "reason": "Overpayment test",
        "idempotency_key": "idem-refund-004-over",
    })
    assert refund_resp.status_code == 400
    assert "exceeds" in refund_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_payment(client):
    capture_resp = await client.post("/payments/capture", json={
        "transaction_ref": "TXN-005",
        "amount_paise": 75000,
        "currency": "INR",
        "method": "upi",
        "idempotency_key": "idem-capture-005",
    })
    assert capture_resp.status_code == 201
    payment_id = capture_resp.json()["id"]

    get_resp = await client.get(f"/payments/{payment_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == payment_id


@pytest.mark.asyncio
async def test_list_payments(client):
    # Capture a few
    for i in range(3):
        await client.post("/payments/capture", json={
            "transaction_ref": f"TXN-LIST-{i}",
            "amount_paise": 1000 * (i + 1),
            "currency": "INR",
            "method": "upi",
            "idempotency_key": f"idem-list-{i}",
        })

    resp = await client.get("/payments")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
