import httpx
from app.config import ORDER_URL, PAYMENT_URL, ERP_URL, SHIPPING_URL

_clients: dict[str, httpx.AsyncClient] = {}

async def get_client(service: str) -> httpx.AsyncClient:
    urls = {
        "order":    ORDER_URL,
        "payment":  PAYMENT_URL,
        "erp":      ERP_URL,
        "shipping": SHIPPING_URL,
    }
    if service not in _clients:
        _clients[service] = httpx.AsyncClient(base_url=urls[service], timeout=10.0)
    return _clients[service]

async def close_all():
    for c in _clients.values():
        await c.aclose()
    _clients.clear()

