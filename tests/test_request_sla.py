from src.request_sla import (
    calculate_sla_deadline,
    calculate_partial_allocation,
    prioritize_shortage_queue,
    retry_shortage_requests
)
from src.request_sla import calculate_sla_deadline


def test_emergency_sla_15_minutes():
    result = calculate_sla_deadline(
        "2026-11-05 10:00:00", "EMERGENCY"
    )

    assert result == "2026-11-05 10:15:00"


def test_urgent_sla_2_hours():
    result = calculate_sla_deadline(
        "2026-11-05 10:00:00", "URGENT"
    )

    assert result == "2026-11-05 12:00:00"


def test_routine_sla_24_hours():
    result = calculate_sla_deadline(
        "2026-11-05 10:00:00", "ROUTINE"
    )

    assert result == "2026-11-06 10:00:00"


def test_invalid_urgency():
    try:
        calculate_sla_deadline(
            "2026-11-05 10:00:00", "LOW"
        )
    except ValueError:
        assert True
    else:
        assert False


from src.request_sla import calculate_partial_allocation


def test_partial_allocation():
    result = calculate_partial_allocation(5, 3)

    assert result["allocated_units"] == 3
    assert result["shortfall"] == 2
    assert result["status"] == "PARTIAL"


def test_complete_allocation():
    result = calculate_partial_allocation(5, 5)

    assert result["allocated_units"] == 5
    assert result["shortfall"] == 0
    assert result["status"] == "FULFILLED"


def test_no_stock_available():
    result = calculate_partial_allocation(5, 0)

    assert result["allocated_units"] == 0
    assert result["shortfall"] == 5
    assert result["status"] == "PENDING"


def test_invalid_unit_count():
    try:
        calculate_partial_allocation(0, 5)
    except ValueError:
        assert True
    else:
        assert False


def test_emergency_request_gets_highest_priority():
    requests = [
        {"request_id": "R1", "urgency": "ROUTINE",
         "request_ts": "2026-11-05 09:00:00"},
        {"request_id": "R2", "urgency": "EMERGENCY",
         "request_ts": "2026-11-05 10:00:00"},
        {"request_id": "R3", "urgency": "URGENT",
         "request_ts": "2026-11-05 08:00:00"}
    ]

    result = prioritize_shortage_queue(requests)

    assert [r["request_id"] for r in result] == [
        "R2", "R3", "R1"
    ]


def test_older_request_gets_priority_when_urgency_is_same():
    requests = [
        {"request_id": "R1", "urgency": "URGENT",
         "request_ts": "2026-11-05 11:00:00"},
        {"request_id": "R2", "urgency": "URGENT",
         "request_ts": "2026-11-05 09:00:00"}
    ]

    result = prioritize_shortage_queue(requests)

    assert result[0]["request_id"] == "R2"


def test_retry_shortage_requests():
    requests = [
        {
            "request_id": "R1",
            "urgency": "ROUTINE",
            "request_ts": "2026-11-05 09:00:00",
            "shortfall": 3
        },
        {
            "request_id": "R2",
            "urgency": "EMERGENCY",
            "request_ts": "2026-11-05 10:00:00",
            "shortfall": 2
        }
    ]

    result = retry_shortage_requests(requests, 4)

    assert result[0]["request_id"] == "R2"
    assert result[0]["allocated_units"] == 2
    assert result[1]["request_id"] == "R1"
    assert result[1]["allocated_units"] == 2
    assert result[1]["shortfall"] == 1


def test_retry_with_no_new_stock():
    requests = [
        {
            "request_id": "R1",
            "urgency": "URGENT",
            "request_ts": "2026-11-05 09:00:00",
            "shortfall": 3
        }
    ]

    result = retry_shortage_requests(requests, 0)

    assert result[0]["allocated_units"] == 0
    assert result[0]["shortfall"] == 3
    assert result[0]["status"] == "PENDING"