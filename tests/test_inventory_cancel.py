from src.inventory_engine import InventoryEngine


def create_cancel_test_engine():
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

    engine.request_status = {
        "REQ-TEST": {
            "status": "ALLOCATED",
            "shortfall": 0
        }
    }

    engine.unit_status = {
        "UNIT-001": {
            "status": "CROSSMATCHED",
            "reason": "RESERVED"
        },
        "UNIT-002": {
            "status": "ISSUED",
            "reason": "ALREADY_ISSUED"
        }
    }

    engine.allocations = [
        {
            "request_id": "REQ-TEST",
            "unit_id": "UNIT-001",
            "reservation_state": "CROSSMATCHED"
        },
        {
            "request_id": "REQ-TEST",
            "unit_id": "UNIT-002",
            "reservation_state": "ISSUED"
        }
    ]

    engine.reservations = [
        {
            "request_id": "REQ-TEST",
            "unit_id": "UNIT-001",
            "reservation_state": "CROSSMATCHED"
        }
    ]

    return engine


def test_cancel_releases_reserved_units():
    engine = create_cancel_test_engine()

    result = engine.process_cancel(
        "REQ-TEST",
        "2026-11-06 10:00:00"
    )

    assert result is True
    assert engine.unit_status["UNIT-001"]["status"] == "AVAILABLE"
    assert engine.allocations[0]["reservation_state"] == "CANCELLED"
    assert engine.reservations[0]["reservation_state"] == "CANCELLED"
    assert engine.request_status["REQ-TEST"]["status"] == "CANCELLED"


def test_cancel_does_not_release_issued_units():
    engine = create_cancel_test_engine()

    engine.process_cancel(
        "REQ-TEST",
        "2026-11-06 10:00:00"
    )

    assert engine.unit_status["UNIT-002"]["status"] == "ISSUED"
    assert engine.allocations[1]["reservation_state"] == "ISSUED"


def test_cancelling_same_request_twice():
    engine = create_cancel_test_engine()

    first_result = engine.process_cancel(
        "REQ-TEST",
        "2026-11-06 10:00:00"
    )

    second_result = engine.process_cancel(
        "REQ-TEST",
        "2026-11-06 10:05:00"
    )

    assert first_result is True
    assert second_result is False

def test_daily_run_releases_expired_reservation():
    engine = create_cancel_test_engine()

    # Set reservation expiry to 72 hours after creation
    engine.reservations[0]["release_ts"] = "2026-11-08 10:00:00"

    # Run daily maintenance after the reservation has expired
    engine.process_daily_run("2026-11-08")

    # Reservation must be released
    assert engine.reservations[0]["reservation_state"] == "RELEASED"

    # Unit must become available
    assert engine.unit_status["UNIT-001"]["status"] == "AVAILABLE"

    # Allocation must also be released
    assert engine.allocations[0]["reservation_state"] == "RELEASED"