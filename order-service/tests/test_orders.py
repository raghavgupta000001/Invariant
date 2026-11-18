import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


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
def mock_db_pool(mock_order_row):
    """Mock asyncpg pool so tests don't require a running PostgreSQL."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=mock_order_row)
    mock_conn.fetch = AsyncMock(return_value=[mock_order_row])
    mock_conn.execute = AsyncMock()

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db._pool", mock_pool), \
         patch("app.db.get_pool", new_callable=AsyncMock, return_value=mock_pool):
        yield mock_pool, mock_conn


@pytest.fixture
def mock_order_row():
    """A realistic asyncpg Record-like dict for a single order."""
    from datetime import datetime, timezone
    import uuid

    class FakeRecord(dict):
        """Mimics asyncpg.Record so row["key"] works."""
        pass

    row = FakeRecord({
        "id": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        "transaction_ref": "TXN-ABCD1234",
        "customer_email": "test@example.com",
        "customer_name": "Test User",
        "items": [{"sku": "SKU-1", "name": "Widget", "qty": 2, "unit_price_paise": 5000}],
        "total_amount_paise": 10000,
        "currency": "INR",
        "status": "CREATED",
        "notes": {},
        "created_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    })
    return row


@pytest_asyncio.fixture
async def client():
    """ASGI test client that skips the real lifespan (db + pubsub init)."""
    from app.main import app
    # Override lifespan so startup hooks don't run
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_order_returns_201(client, mock_publisher):
    payload = {
        "customer_email": "buyer@example.com",
        "customer_name": "Buyer Name",
        "items": [{"sku": "SKU-1", "name": "Widget", "qty": 2, "unit_price_paise": 5000}],
        "notes": {},
    }
    response = await client.post("/orders", json=payload)

    assert response.status_code == 201
    data = response.json()

    # Required fields present
    assert "id" in data
    assert "transaction_ref" in data
    assert data["transaction_ref"].startswith("TXN-")
    assert "customer_email" in data
    assert "status" in data
    assert data["status"] == "CREATED"
    assert "total_amount_paise" in data
    assert "total_amount_display" in data
    assert data["currency"] == "INR"

    # Publisher was called once
    mock_publisher.assert_awaited_once()
    call_kwargs = mock_publisher.call_args.kwargs
    assert call_kwargs["event_type"] == "order.created"


@pytest.mark.asyncio
async def test_get_order_returns_order(client):
    response = await client.get("/orders/TXN-ABCD1234")

    assert response.status_code == 200
    data = response.json()
    assert data["transaction_ref"] == "TXN-ABCD1234"
    assert data["customer_email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_order_not_found(client, mock_db_pool):
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=None)

    response = await client.get("/orders/nonexistent-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


@pytest.mark.asyncio
async def test_list_orders(client):
    response = await client.get("/orders")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["transaction_ref"] == "TXN-ABCD1234"


@pytest.mark.asyncio
async def test_cancel_order(client, mock_db_pool, mock_publisher, mock_order_row):
    """cancel_order should update status to CANCELLED and publish an event."""
    from datetime import datetime, timezone
    import uuid

    cancelled_row = dict(mock_order_row)
    cancelled_row["status"] = "CANCELLED"

    class FakeRecord(dict):
        pass

    cancelled_record = FakeRecord(cancelled_row)
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=cancelled_record)

    response = await client.post(
        "/orders/TXN-ABCD1234/cancel",
        json={"reason": "Changed mind"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"

    mock_publisher.assert_awaited_once()
    call_kwargs = mock_publisher.call_args.kwargs
    assert call_kwargs["event_type"] == "order.cancelled"


@pytest.mark.asyncio
async def test_cancel_already_cancelled(client, mock_db_pool):
    """If the row is not returned (already cancelled), expect 404."""
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=None)

    response = await client.post(
        "/orders/TXN-ABCD1234/cancel",
        json={"reason": "Duplicate"},
    )
    assert response.status_code == 404


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
