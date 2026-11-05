from datetime import datetime, timedelta


def create_platelet_pool(units):
    """
    Creates a platelet pool if all units have:
    1. The same blood group.
    2. Expiry dates within 24 hours.

    The pooled expiry is the earliest expiry date.
    """

    # At least two units are required
    if len(units) < 2:
        raise ValueError("At least two platelet units are required")

    # Check that all units have the same blood group
    blood_groups = {unit["blood_group"] for unit in units}

    if len(blood_groups) != 1:
        raise ValueError("All units must have the same blood group")

    # Convert expiry dates into datetime objects
    expiry_dates = [
        datetime.strptime(unit["expiry_date"], "%Y-%m-%d %H:%M:%S")
        for unit in units
    ]

    # Find the earliest and latest expiry
    earliest_expiry = min(expiry_dates)
    latest_expiry = max(expiry_dates)

    # Check whether expiry dates are within 24 hours
    if latest_expiry - earliest_expiry > timedelta(hours=24):
        raise ValueError("Expiry dates must be within 24 hours")

    return {
        "unit_ids": [unit["unit_id"] for unit in units],
        "blood_group": blood_groups.pop(),
        "expiry_date": earliest_expiry.strftime("%Y-%m-%d %H:%M:%S")
    }