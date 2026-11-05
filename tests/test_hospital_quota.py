from src.hospital_quota import (
    check_daily_quota,
    calculate_replacement_ratio,
    calculate_adjusted_quota
)
from src.hospital_quota import check_daily_quota


def test_request_within_daily_quota():
    result = check_daily_quota(10, 4, 3, "ROUTINE")

    assert result["approved_units"] == 3
    assert result["status"] == "APPROVED"


def test_request_exceeds_quota_partially():
    result = check_daily_quota(10, 8, 5, "URGENT")

    assert result["approved_units"] == 2
    assert result["status"] == "PARTIAL"


def test_daily_quota_fully_used():
    result = check_daily_quota(10, 10, 2, "ROUTINE")

    assert result["approved_units"] == 0
    assert result["status"] == "QUOTA_EXCEEDED"


def test_emergency_bypasses_quota():
    result = check_daily_quota(10, 10, 3, "EMERGENCY")

    assert result["approved_units"] == 3
    assert result["status"] == "APPROVED"


def test_invalid_quota_values():
    try:
        check_daily_quota(10, -1, 3, "ROUTINE")
    except ValueError:
        assert True
    else:
        assert False


def test_replacement_ratio():
    result = calculate_replacement_ratio(18, 10)
    assert result == 1.8


def test_replacement_ratio_with_zero_donations():
    result = calculate_replacement_ratio(5, 0)
    assert result == float("inf")


def test_quota_reduced_when_ratio_exceeds_1_5():
    result = calculate_adjusted_quota(10, 1.8)
    assert result == 5


def test_quota_not_reduced_at_exactly_1_5():
    result = calculate_adjusted_quota(10, 1.5)
    assert result == 10


def test_quota_not_reduced_below_1_5():
    result = calculate_adjusted_quota(10, 1.2)
    assert result == 10