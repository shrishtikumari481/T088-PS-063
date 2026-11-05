def check_daily_quota(
    daily_cap,
    already_issued,
    requested_units,
    urgency
):
    """
    Checks whether a hospital can receive the requested units
    within its daily quota.

    Emergency requests are exempt from the quota.
    """

    if daily_cap < 0 or already_issued < 0 or requested_units <= 0:
        raise ValueError("Invalid quota or unit count")

    # Emergency requests bypass the daily quota
    if urgency.upper() == "EMERGENCY":
        return {
            "approved_units": requested_units,
            "status": "APPROVED"
        }

    remaining_quota = max(0, daily_cap - already_issued)

    approved_units = min(requested_units, remaining_quota)

    if approved_units == requested_units:
        status = "APPROVED"
    elif approved_units > 0:
        status = "PARTIAL"
    else:
        status = "QUOTA_EXCEEDED"

    return {
        "approved_units": approved_units,
        "status": status
    }


def calculate_replacement_ratio(issued_units, mobilised_donations):
    """
    Calculates the monthly replacement ratio.
    """

    if issued_units < 0 or mobilised_donations < 0:
        raise ValueError("Values cannot be negative")

    if mobilised_donations == 0:
        return float("inf") if issued_units > 0 else 0.0

    return issued_units / mobilised_donations

def calculate_adjusted_quota(normal_quota, replacement_ratio):
    """
    Reduces routine quota by 50% if replacement ratio exceeds 1.5.
    """

    if normal_quota < 0 or replacement_ratio < 0:
        raise ValueError("Invalid quota or replacement ratio")

    if replacement_ratio > 1.5:
        return normal_quota // 2

    return normal_quota