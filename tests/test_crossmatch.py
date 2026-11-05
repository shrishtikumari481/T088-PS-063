from src.crossmatch import check_retrospective_crossmatch
from src.crossmatch import emergency_uncrossmatched_issue

from src.crossmatch import (
    create_reservation,
    check_reservation_status
)


def test_reservation_created_successfully():
    reservation = create_reservation(
        "U001",
        "REQ001",
        "2026-11-05 10:00:00"
    )

    assert reservation["reservation_state"] == "CROSSMATCHED"
    assert reservation["release_ts"] == "2026-11-08 10:00:00"


def test_reservation_before_72_hours():
    reservation = create_reservation(
        "U001",
        "REQ001",
        "2026-11-05 10:00:00"
    )

    result = check_reservation_status(
        reservation,
        "2026-11-08 09:59:00"
    )

    assert result == "CROSSMATCHED"


def test_reservation_at_exactly_72_hours():
    reservation = create_reservation(
        "U001",
        "REQ001",
        "2026-11-05 10:00:00"
    )

    result = check_reservation_status(
        reservation,
        "2026-11-08 10:00:00"
    )

    assert result == "AVAILABLE"


def test_issued_reservation_is_not_released():
    reservation = create_reservation(
        "U001",
        "REQ001",
        "2026-11-05 10:00:00"
    )

    reservation["reservation_state"] = "ISSUED"

    result = check_reservation_status(
        reservation,
        "2026-11-09 10:00:00"
    )

    assert result == "ISSUED"

def test_emergency_issue_with_unknown_blood_group():
    result = emergency_uncrossmatched_issue(
        None, None
    )

    assert result["unit_id"] == "O-"
    assert result["status"] == "ISSUED"
    assert result["crossmatch_state"] == "PENDING_RETROSPECTIVE"


def test_emergency_issue_with_known_blood_group():
    result = emergency_uncrossmatched_issue(
        "A", "POS", "U001"
    )

    assert result["unit_id"] == "U001"
    assert result["status"] == "ISSUED"


def test_emergency_issue_without_compatible_unit():
    result = emergency_uncrossmatched_issue(
        "A", "POS"
    )

    assert result is None


def test_emergency_issue_with_unknown_group_uses_o_negative():
    result = emergency_uncrossmatched_issue(
        "", "", None
    )

    assert result["unit_id"] == "O-"

def test_retrospective_crossmatch_completed():
    result = check_retrospective_crossmatch(
        "2026-11-05 10:00:00",
        "2026-11-05 18:00:00",
        "COMPATIBLE"
    )

    assert result == "COMPLETED"


def test_retrospective_crossmatch_pending_within_24_hours():
    result = check_retrospective_crossmatch(
        "2026-11-05 10:00:00",
        "2026-11-06 09:59:00",
        None
    )

    assert result == "PENDING"


def test_retrospective_crossmatch_exactly_24_hours():
    result = check_retrospective_crossmatch(
        "2026-11-05 10:00:00",
        "2026-11-06 10:00:00",
        None
    )

    assert result == "PENDING"


def test_retrospective_crossmatch_over_24_hours():
    result = check_retrospective_crossmatch(
        "2026-11-05 10:00:00",
        "2026-11-06 10:01:00",
        None
    )

    assert result == "FLAGGED"