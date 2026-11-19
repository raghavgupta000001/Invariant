import pytest
import pytest_asyncio
import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
import uuid


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


@pytest.fixture
def mock_shipment_row():
    """A realistic asyncpg Record-like dict for a single shipment."""

    class FakeRecord(dict):
        """Mimics asyncpg.Record so row["key"] works."""
        pass

    row = FakeRecord({
        "id": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        "transaction_ref": "TXN-SHIP-001",
        "sales_order_id": "SO-001",
        "carrier": "BLUEDART",
        "tracking_number": "BDABCDE12345",
        "status": "CREATED",
        "recipient_name": "Test Recipient",
        "recipient_email": "recipient@example.com",
        "delivery_address": json.dumps({
            "line1": "123 Main St",
            "line2": "",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001",
            "country": "IN",
        }),
        "estimated_delivery": date(2024, 1, 4),
        "failure_reason": None,
        "created_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    })
    return row


@pytest.fixture(autouse=True)
def mock_db_pool(mock_shipment_row):
    """Mock asyncpg pool so tests don't require a running PostgreSQL."""
    mock_conn = AsyncMock()
    # By default fetchrow returns None for the "existing" check, then the row
    mock_conn.fetchrow = AsyncMock(side_effect=[None, mock_shipment_row])
    mock_conn.fetch = AsyncMock(return_value=[mock_shipment_row])
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
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_shipment_returns_201(client, mock_publisher):
    payload = {
        "transaction_ref": "TXN-SHIP-001",
        "sales_order_id": "SO-001",
        "recipient_name": "Test Recipient",
        "recipient_email": "recipient@example.com",
        "delivery_address": {
            "line1": "123 Main St",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001",
        },
        "carrier": "BLUEDART",
    }
    response = await client.post("/shipments", json=payload)

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert "tracking_number" in data
    assert data["tracking_number"].startswith("BD")
    assert data["carrier"] == "BLUEDART"
    assert data["status"] == "CREATED"
    assert data["transaction_ref"] == "TXN-SHIP-001"

    mock_publisher.assert_awaited_once()
    call_kwargs = mock_publisher.call_args.kwargs
    assert call_kwargs["event_type"] == "shipment.created"


@pytest.mark.asyncio
async def test_create_shipment_duplicate_returns_409(client, mock_db_pool):
    """Second creation for the same transaction_ref returns 409."""
    _, mock_conn = mock_db_pool
    # Simulate existing record found
    mock_conn.fetchrow = AsyncMock(return_value={"id": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")})

    payload = {
        "transaction_ref": "TXN-SHIP-001",
        "sales_order_id": "SO-001",
        "recipient_name": "Test Recipient",
        "recipient_email": "recipient@example.com",
        "delivery_address": {
            "line1": "123 Main St",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001",
        },
    }
    response = await client.post("/shipments", json=payload)
    assert response.status_code == 409
    assert "already created" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_shipment_failure_mode_returns_503(client, mock_publisher):
    """When failure mode is active, POST /shipments returns 503."""
    from app import failure_state
    failure_state.set_failure("shipment_creation_fails")
    try:
        payload = {
            "transaction_ref": "TXN-SHIP-FAIL",
            "sales_order_id": "SO-FAIL",
            "recipient_name": "Test Recipient",
            "recipient_email": "fail@example.com",
            "delivery_address": {
                "line1": "1 Failure Lane",
                "city": "Delhi",
                "state": "Delhi",
                "pincode": "110001",
            },
        }
        response = await client.post("/shipments", json=payload)
        assert response.status_code == 503
        assert "SIMULATED" in response.json()["detail"]

        # Publisher should have been called with shipment.failed
        mock_publisher.assert_awaited_once()
        call_kwargs = mock_publisher.call_args.kwargs
        assert call_kwargs["event_type"] == "shipment.failed"
    finally:
        failure_state.clear_failure("shipment_creation_fails")


@pytest.mark.asyncio
async def test_get_shipment_found(client, mock_db_pool, mock_shipment_row):
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=mock_shipment_row)

    response = await client.get("/shipments/TXN-SHIP-001")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_ref"] == "TXN-SHIP-001"
    assert data["tracking_number"] == "BDABCDE12345"


@pytest.mark.asyncio
async def test_get_shipment_not_found(client, mock_db_pool):
    _, mock_conn = mock_db_pool
    mock_conn.fetchrow = AsyncMock(return_value=None)

    response = await client.get("/shipments/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Shipment not found"


@pytest.mark.asyncio
async def test_list_shipments(client):
    response = await client.get("/shipments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["transaction_ref"] == "TXN-SHIP-001"


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
