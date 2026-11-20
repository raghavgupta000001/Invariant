import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_webhook_ingest_and_transaction_lifecycle():
    with TestClient(app) as client:
        txn_ref = "TXN-E2E-TEST-01"

        # 1. Ingest order created webhook
        r_order = client.post(
            "/webhooks/shopify",
            json={
                "event_type": "order.created",
                "transaction_ref": txn_ref,
                "data": {
                    "id": "ord_101",
                    "customer_email": "e2e@example.com",
                    "total_amount_paise": 6000000,
                    "status": "CREATED",
                }
            }
        )
        assert r_order.status_code == 200
        assert r_order.json()["status"] == "PROCESSED"
        assert r_order.json()["transaction_state"] == "IN_PROGRESS"

        # 2. Ingest payment captured webhook (with amount mismatch to trigger invariant)
        # Order was ₹60,000 (6,000,000 paise), payment is ₹6,000 (600,000 paise)
        r_pay = client.post(
            "/webhooks/razorpay",
            json={
                "event": "payment.captured",
                "transaction_ref": txn_ref,
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_909",
                            "amount": 600000,  # ₹6,000!
                            "currency": "INR",
                            "status": "captured",
                        }
                    }
                }
            }
        )
        assert r_pay.status_code == 200
        pay_res = r_pay.json()
        assert pay_res["transaction_state"] == "INCONSISTENT"
        assert len(pay_res["incidents_raised"]) >= 1

        # 3. Verify transaction API reports the anomaly
        r_txn = client.get(f"/transactions/{txn_ref}")
        assert r_txn.status_code == 200
        txn_data = r_txn.json()
        assert txn_data["state"] == "INCONSISTENT"
        assert "amount" in txn_data["inconsistent_reason"].lower()

        # 4. Verify incidents API lists the raised incident
        r_inc = client.get(f"/incidents?transaction_ref={txn_ref}")
        assert r_inc.status_code == 200
        inc_data = r_inc.json()
        assert inc_data["count"] >= 1
        incident_id = inc_data["incidents"][0]["id"]

        # 5. Resolve incident
        r_res = client.post(f"/incidents/{incident_id}/resolve")
        assert r_res.status_code == 200
        assert r_res.json()["state"] == "RESOLVED"

