from src.reservation_manager import (
    reserve_unit,
    preempt_routine_reservation
)


def test_reserve_unit_successfully():
    reservations = []

    result = reserve_unit("U001", "R001", reservations)

    assert result is True
    assert reservations[0]["request_id"] == "R001"


def test_prevent_double_reservation():
    reservations = []

    reserve_unit("U001", "R001", reservations)

    result = reserve_unit("U001", "R002", reservations)

    assert result is False
    assert len(reservations) == 1


def test_emergency_preempts_routine_reservation():
    reservations = []
    waiting_queue = []

    reserve_unit("U001", "R001", reservations, "ROUTINE")

    result = preempt_routine_reservation(
        "U001", "R002", reservations, waiting_queue
    )

    assert result is True
    assert reservations[0]["reservation_state"] == "PREEMPTED"
    assert reservations[1]["request_id"] == "R002"
    assert waiting_queue == ["R001"]


def test_emergency_cannot_preempt_another_emergency():
    reservations = []
    waiting_queue = []

    reserve_unit("U001", "R001", reservations, "EMERGENCY")

    result = preempt_routine_reservation(
        "U001", "R002", reservations, waiting_queue
    )

    assert result is False
    assert waiting_queue == []


def test_preemption_with_unreserved_unit():
    reservations = []
    waiting_queue = []

    result = preempt_routine_reservation(
        "U001", "R002", reservations, waiting_queue
    )

    assert result is False
    assert reservations == []