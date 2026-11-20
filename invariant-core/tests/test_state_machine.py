from datetime import datetime, timezone
from app.models.icef import CanonicalEvent, ICEFMeta, ICEFEntity, ICEFCorrelation
from app.engine.state_machine import TransactionStateMachine
from app.models.domain import TransactionState, StepState


def _make_event(event_type: str, txn_ref: str, data: dict = {}) -> CanonicalEvent:
    return CanonicalEvent(
        meta=ICEFMeta(
            idempotency_key=f"idemp-{event_type}-{txn_ref}",
            source_system="test",
            source_event_id=f"src-{event_type}",
            raw_event_type=event_type,
            canonical_event_type=event_type,
            occurred_at=datetime.now(timezone.utc),
        ),
        entity=ICEFEntity(type="generic", id="test-entity"),
        data=data,
        transaction_correlation=ICEFCorrelation(transaction_ref=txn_ref),
    )


def test_state_machine_happy_progression():
    sm = TransactionStateMachine()
    txn_ref = "TXN-PROGRESS-1"

    # Step 1: Order created
    txn, err = sm.apply_event(_make_event("order.created", txn_ref), txn_ref)
    assert txn["state"] == TransactionState.IN_PROGRESS.value
    assert txn["steps"]["order_created"]["state"] == StepState.COMPLETED.value
    assert err is None

    # Step 2: Payment captured
    txn, err = sm.apply_event(_make_event("payment.captured", txn_ref), txn_ref)
    assert txn["steps"]["payment_captured"]["state"] == StepState.COMPLETED.value
    assert err is None

    # Step 3: ERP order created
    txn, err = sm.apply_event(_make_event("erp.order_created", txn_ref), txn_ref)
    assert txn["steps"]["erp_order_created"]["state"] == StepState.COMPLETED.value

    # Step 4: Inventory reserved
    txn, err = sm.apply_event(_make_event("erp.inventory_reserved", txn_ref), txn_ref)
    assert txn["steps"]["inventory_reserved"]["state"] == StepState.COMPLETED.value

    # Step 5: Invoice generated
    txn, err = sm.apply_event(_make_event("erp.invoice_generated", txn_ref), txn_ref)
    assert txn["steps"]["invoice_generated"]["state"] == StepState.COMPLETED.value

    # Step 6: Shipment created
    txn, err = sm.apply_event(_make_event("shipment.created", txn_ref), txn_ref)
    assert txn["steps"]["shipment_created"]["state"] == StepState.COMPLETED.value
    assert txn["state"] == TransactionState.COMPLETED.value


def test_state_machine_out_of_order_detection():
    sm = TransactionStateMachine()
    txn_ref = "TXN-OUT-ORDER"

    # Shipment arrives BEFORE payment
    txn, err = sm.apply_event(_make_event("shipment.created", txn_ref), txn_ref)
    assert err is not None
    assert "Out of order" in err

