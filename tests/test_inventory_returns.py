from src.inventory_engine import InventoryEngine


def create_test_engine():

    data = {
        "donors": [],
        "donations": [],
        "hospitals": [],
        "requests": [
            {"request_id": "REQ-TEST"}
        ],
        "components": [],
        "screening_results": []
    }

    engine = InventoryEngine(data)

    engine.unit_status = {
        "UNIT-001": {
            "status": "ISSUED",
            "issued_request_id": "REQ-TEST",
            "issued_ts": "2026-11-05 10:00:00"
        },
        "UNIT-002": {
            "status": "ISSUED",
            "issued_request_id": "REQ-TEST",
            "issued_ts": "2026-11-05 10:00:00"
        }
    }

    engine.invoices = [
        {
            "request_id": "REQ-TEST",
            "unit_id": "UNIT-001",
            "amount": 1550
        },
        {
            "request_id": "REQ-TEST",
            "unit_id": "UNIT-002",
            "amount": 1550
        }
    ]

    engine.output_records["invoices.csv"] = engine.invoices.copy()

    return engine


def test_eligible_return_removes_only_matching_invoice():

    engine = create_test_engine()

    result = engine.process_return(
        "REQ-TEST",
        "2026-11-05 10:20:00",
        1,
        True
    )

    assert result is True

    assert len(engine.invoices) == 1
    assert engine.invoices[0]["unit_id"] == "UNIT-002"

    assert engine.unit_status["UNIT-001"]["status"] == "RETURNED"
    assert engine.unit_status["UNIT-002"]["status"] == "ISSUED"


def test_late_return_keeps_invoice():

    engine = create_test_engine()

    result = engine.process_return(
        "REQ-TEST",
        "2026-11-05 10:40:00",
        1,
        True
    )

    assert result is True

    assert len(engine.invoices) == 2

    assert engine.unit_status["UNIT-001"]["status"] == "DISCARDED"