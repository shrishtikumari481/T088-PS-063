from datetime import datetime

from src.component_expiry import calculate_expiry


def test_prbc_expiry_35_days():
    collection = datetime(2026, 1, 1, 10, 0)

    result = calculate_expiry("PRBC", collection)

    assert result == datetime(2026, 2, 5, 23, 59)


def test_prbc_with_additive_expiry_42_days():
    collection = datetime(2026, 1, 1, 10, 0)

    result = calculate_expiry(
        "PRBC", collection, additive_solution=True
    )

    assert result == datetime(2026, 2, 12, 23, 59)


def test_platelet_expiry_5_days():
    collection = datetime(2026, 1, 1, 10, 0)

    result = calculate_expiry("PLATELET", collection)

    assert result == datetime(2026, 1, 6, 23, 59)


def test_ffp_frozen_within_8_hours():
    collection = datetime(2026, 1, 1, 10, 0)
    frozen = datetime(2026, 1, 1, 18, 0)

    result = calculate_expiry("FFP", collection, frozen_ts=frozen)

    assert result == datetime(2027, 1, 1, 23, 59)


def test_ffp_frozen_after_8_hours():
    collection = datetime(2026, 1, 1, 10, 0)
    frozen = datetime(2026, 1, 1, 18, 1)

    result = calculate_expiry("FFP", collection, frozen_ts=frozen)

    assert result is None


def test_ffp_without_freezing_time():
    collection = datetime(2026, 1, 1, 10, 0)

    result = calculate_expiry("FFP", collection)

    assert result is None