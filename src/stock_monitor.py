def check_stock_alert(available_units, blood_group):
    """
    Checks blood stock and returns the appropriate alert.

    BR-09:
    - O- stock below 8: SHORTAGE
    - Other blood groups below 5: SHORTAGE
    - Any blood group below 2: CRITICAL
    """

    if not isinstance(available_units, int) or isinstance(available_units, bool):
        raise ValueError("Available units must be an integer")

    if available_units < 0:
        raise ValueError("Available units cannot be negative")

    blood_group = blood_group.upper()

    if available_units < 2:
        return "CRITICAL"

    if blood_group == "O-" and available_units < 8:
        return "SHORTAGE"

    if available_units < 5:
        return "SHORTAGE"

    return ""