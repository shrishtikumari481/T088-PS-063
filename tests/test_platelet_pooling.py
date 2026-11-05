import pytest

from src.platelet_pooling import create_platelet_pool


def test_valid_platelet_pool():
    units = [
        {
            "unit_id": "U001",
            "blood_group": "A+",
            "expiry_date": "2026-11-06 10:00:00"
        },
        {
            "unit_id": "U002",
            "blood_group": "A+",
            "expiry_date": "2026-11-06 18:00:00"
        }
    ]

    result = create_platelet_pool(units)

    assert result["blood_group"] == "A+"
    assert result["unit_ids"] == ["U001", "U002"]
    assert result["expiry_date"] == "2026-11-06 10:00:00"


def test_exactly_24_hours_is_allowed():
    units = [
        {
            "unit_id": "U001",
            "blood_group": "O+",
            "expiry_date": "2026-11-06 10:00:00"
        },
        {
            "unit_id": "U002",
            "blood_group": "O+",
            "expiry_date": "2026-11-07 10:00:00"
        }
    ]

    result = create_platelet_pool(units)

    assert result["expiry_date"] == "2026-11-06 10:00:00"


def test_different_blood_groups_not_allowed():
    units = [
        {
            "unit_id": "U001",
            "blood_group": "A+",
            "expiry_date": "2026-11-06 10:00:00"
        },
        {
            "unit_id": "U002",
            "blood_group": "B+",
            "expiry_date": "2026-11-06 18:00:00"
        }
    ]

    with pytest.raises(ValueError):
        create_platelet_pool(units)


def test_expiry_difference_more_than_24_hours():
    units = [
        {
            "unit_id": "U001",
            "blood_group": "A+",
            "expiry_date": "2026-11-06 10:00:00"
        },
        {
            "unit_id": "U002",
            "blood_group": "A+",
            "expiry_date": "2026-11-07 10:01:00"
        }
    ]

    with pytest.raises(ValueError):
        create_platelet_pool(units)


def test_at_least_two_units_required():
    units = [
        {
            "unit_id": "U001",
            "blood_group": "A+",
            "expiry_date": "2026-11-06 10:00:00"
        }
    ]

    with pytest.raises(ValueError):
        create_platelet_pool(units)