from app.normalizers.razorpay import RazorpayNormalizer
from app.normalizers.shopify import ShopifyNormalizer
from app.normalizers.erp import ERPNormalizer
from app.normalizers.shipping import ShippingNormalizer


def test_razorpay_normalizer_success():
    norm = RazorpayNormalizer()
    raw = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_TEST123456",
                    "amount": 6000000,
                    "currency": "INR",
                    "status": "captured",
                    "method": "upi",
                    "description": "TXN-TEST-1042",
                }
            }
        }
    }
    res = norm.normalize(raw)
    assert res.success is True
    assert res.event is not None
    assert res.event.meta.canonical_event_type == "payment.captured"
    assert res.event.data["amount_paise"] == 6000000
    assert res.event.data["amount_display"] == 60000.0
    assert res.event.transaction_correlation.transaction_ref == "TXN-TEST-1042"


def test_shopify_normalizer_success():
    norm = ShopifyNormalizer()
    raw = {
        "event_type": "order.created",
        "transaction_ref": "TXN-TEST-1042",
        "data": {
            "id": "ord_98765",
            "customer_email": "customer@example.com",
            "total_amount_paise": 6000000,
            "status": "CREATED",
        }
    }
    res = norm.normalize(raw)
    assert res.success is True
    assert res.event.meta.canonical_event_type == "order.created"
    assert res.event.data["total_amount_paise"] == 6000000


def test_erp_normalizer_success():
    norm = ERPNormalizer()
    raw = {
        "event_type": "erp.order_created",
        "transaction_ref": "TXN-TEST-1042",
        "data": {
            "sales_order_id": "so_54321",
            "status": "OPEN",
        }
    }
    res = norm.normalize(raw)
    assert res.success is True
    assert res.event.meta.canonical_event_type == "erp.order_created"


def test_shipping_normalizer_success():
    norm = ShippingNormalizer()
    raw = {
        "event_type": "shipment.created",
        "transaction_ref": "TXN-TEST-1042",
        "data": {
            "shipment_id": "shp_112233",
            "tracking_number": "BD998877",
            "carrier": "BLUEDART",
        }
    }
    res = norm.normalize(raw)
    assert res.success is True
    assert res.event.meta.canonical_event_type == "shipment.created"


def test_unrecognized_event_type():
    norm = RazorpayNormalizer()
    raw = {"event": "some.random.unknown.event"}
    res = norm.normalize(raw)
    assert res.success is False
    assert res.is_recognized is False

