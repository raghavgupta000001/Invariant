import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeRecord(dict):
    """Mimics asyncpg.Record so row["key"] works."""
    pass


FAKE_ORDER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
FAKE_HOLD_ID  = uuid.UUID("11111111-2222-3333-4444-555555555555")
FAKE_INV_ID   = uuid.UUID("cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa")

_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_order_row(**overrides):
    base = FakeRecord({
        "id": FAKE_ORDER_ID,
        "transaction_ref": "TXN-ERP-001",
        "customer_id": "CUST-42",
        "customer_email": "buyer@example.com",
        "line_items": [{"sku": "SKU-X", "name": "Widget", "qty": 1, "unit_price_paise": 10000}],
        "total_amount_paise": 10000,
        "currency": "INR",
        "status": "OPEN",
        "created_at": _now,
        "updated_at": _now,
    })
    base.update(overrides)
    return base


def make_hold_row():
    return FakeRecord({"id": FAKE_HOLD_ID})


def make_invoice_row():
    return FakeRecord({
        "id": FAKE_INV_ID,
        "invoice_number": "INV-ABCD1234",
        "amount_paise": 10000,
        "currency": "INR",
        "status": "ISSUED",
        "issued_at": _now,
        "created_at": _now,
    })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_publisher():
    """Mock publisher so tests don't require a running Pub/Sub."""
    with patch("app.publisher._publisher", MagicMock()), \
         patch("app.publisher._topic_path", "projects/test/topics/invariant-events"), \
         patch("app.publisher.publish_event", new_callable=AsyncMock) as mock_pub:
        yield mock_pub


@pytest.fixture(autouse=True)
def mock_db_pool():
    """Mock asyncpg pool so tests don't require a running PostgreSQL."""
    mock_conn = AsyncMock()
    # Default: return a valid sales_order row
    mock_conn.fetchrow = AsyncMock(return_value=make_order_row())
    mock_conn.fetch = AsyncMock(return_value=[make_order_row()])
    mock_conn.execute = AsyncMock()

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db._pool", mock_pool), \
         patch("app.db.get_pool", new_callable=AsyncMock, return_value=mock_pool):
        yield mock_pool, mock_conn


@pytest_asyncio.fixture
async def client():
    """ASGI test client that skips the real lifespan (db + pubsub init)."""
    from app.main import app
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests — create_sales_order (happy path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_sales_order_returns_201(client, mock_publisher):
    # First fetchrow call: check duplicate (None = no duplicate)
    # Second fetchrow call: INSERT RETURNING
    from unittest.mock import AsyncMock as AM
    _, mock_conn = (None, None)  # get from fixture indirectly via patch

    # patch conn.fetchrow sequence: first None (no duplicate), then order row
    with patch("app.db.get_pool") as mock_get_pool:
        mock_conn2 = AsyncMock()
        mock_conn2.fetchrow = AsyncMock(side_effect=[None, make_order_row()])
        mock_pool2 = MagicMock()
        mock_pool2.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn2)
        mock_pool2.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_get_pool.return_value = mock_pool2

        payload = {
            "transaction_ref": "TXN-ERP-001",
            "customer_id": "CUST-42",
            "customer_email": "buyer@example.com",
            "line_items": [{"sku": "SKU-X", "name": "Widget", "qty": 1, "unit_price_paise": 10000}],
            "total_amount_paise": 10000,
        }
        response = await client.post("/erp/orders", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["transaction_ref"] == "TXN-ERP-001"
    assert data["status"] == "OPEN"
    mock_publisher.assert_awaited_once()
    assert mock_publisher.call_args.kwargs["event_type"] == "erp.order_created"


# ---------------------------------------------------------------------------
# Tests — get_sales_order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_sales_order_returns_200(client, mock_db_pool):
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=make_order_row())

    response = await client.get("/erp/orders/TXN-ERP-001")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_ref"] == "TXN-ERP-001"
    assert data["customer_id"] == "CUST-42"
    assert data["status"] == "OPEN"


@pytest.mark.asyncio
async def test_get_sales_order_not_found(client, mock_db_pool):
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=None)

    response = await client.get("/erp/orders/NONEXISTENT")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests — silent failure mode (the key scenario)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_silent_failure_returns_200_with_fake_id(client, mock_db_pool):
    """
    When erp_silent_failure is active, POST /erp/orders returns HTTP 200
    with a fake order ID but does NOT write to the database.
    """
    from app import failure_state
    failure_state.set_failure("erp_silent_failure")
    try:
        _, mock_conn = mock_db_pool

        payload = {
            "transaction_ref": "TXN-SILENT-001",
            "customer_id": "CUST-99",
            "customer_email": "ghost@example.com",
            "line_items": [{"sku": "SKU-Y", "name": "Ghost Item", "qty": 1, "unit_price_paise": 5000}],
            "total_amount_paise": 5000,
        }
        response = await client.post("/erp/orders", json=payload)

        # Must return 200 (not 201) — silent failure returns early before status_code=201 applies
        assert response.status_code in (200, 201)
        data = response.json()
        assert "id" in data
        assert data["transaction_ref"] == "TXN-SILENT-001"
        assert data["note"] == "__SIMULATED_SILENT_FAILURE__"

        # DB was NOT touched — fetchrow should never have been called for INSERT
        mock_conn.fetchrow.assert_not_called()

        # Publisher was also NOT called
        # (silent failure should not emit events)
    finally:
        failure_state.clear_failure("erp_silent_failure")


@pytest.mark.asyncio
async def test_silent_failure_record_absent_on_get(client, mock_db_pool):
    """
    After a silent failure write, GET /erp/orders/<ref> returns 404
    (record was never persisted).
    """
    from app import failure_state

    # Simulate: silent failure was active during POST, so no DB record exists
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=None)  # DB has no record

    response = await client.get("/erp/orders/TXN-SILENT-001")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — reserve_inventory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reserve_inventory_returns_201(client, mock_publisher):
    with patch("app.db.get_pool") as mock_get_pool:
        mock_conn2 = AsyncMock()
        # sales_order lookup returns valid row, hold INSERT returns hold row
        mock_conn2.fetchrow = AsyncMock(side_effect=[
            make_order_row(),  # sales_order check
            make_hold_row(),   # INSERT inventory_holds for item 1
        ])
        mock_pool2 = MagicMock()
        mock_pool2.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn2)
        mock_pool2.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_get_pool.return_value = mock_pool2

        payload = {
            "transaction_ref": "TXN-ERP-001",
            "sales_order_id": str(FAKE_ORDER_ID),
            "items": [{"sku": "SKU-X", "name": "Widget", "qty": 2, "unit_price_paise": 10000}],
        }
        response = await client.post("/erp/inventory/reserve", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "RESERVED"
    assert len(data["hold_ids"]) == 1
    mock_publisher.assert_awaited_once()
    assert mock_publisher.call_args.kwargs["event_type"] == "erp.inventory_reserved"


@pytest.mark.asyncio
async def test_reserve_inventory_order_not_found(client):
    with patch("app.db.get_pool") as mock_get_pool:
        mock_conn2 = AsyncMock()
        mock_conn2.fetchrow = AsyncMock(return_value=None)  # no sales order
        mock_pool2 = MagicMock()
        mock_pool2.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn2)
        mock_pool2.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_get_pool.return_value = mock_pool2

        payload = {
            "transaction_ref": "TXN-ERP-001",
            "sales_order_id": str(FAKE_ORDER_ID),
            "items": [{"sku": "SKU-X", "name": "Widget", "qty": 1, "unit_price_paise": 10000}],
        }
        response = await client.post("/erp/inventory/reserve", json=payload)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — failure injection control endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_failure_endpoint(client):
    from app import failure_state
    failure_state.clear_failure("erp_silent_failure")

    response = await client.post("/erp/failure?mode=erp_silent_failure&active=true")
    assert response.status_code == 200
    assert failure_state.is_active("erp_silent_failure")

    response = await client.post("/erp/failure?mode=erp_silent_failure&active=false")
    assert response.status_code == 200
    assert not failure_state.is_active("erp_silent_failure")


# ---------------------------------------------------------------------------
# Tests — health endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
