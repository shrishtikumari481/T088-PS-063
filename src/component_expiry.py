from datetime import datetime, timedelta, time


def calculate_expiry(component, collection_ts, additive_solution=False, frozen_ts=None):
    """
    Calculate the last valid date and time for a blood component.

    Returns:
        Expiry datetime if valid.
        None if the component must be discarded.
    """

    # PRBC shelf life: 35 days or 42 days with additive solution
    if component == "PRBC":
        shelf_life = 42 if additive_solution else 35

    # Platelet shelf life: 5 days
    elif component == "PLATELET":
        shelf_life = 5

    # FFP shelf life: 365 days if frozen within 8 hours
    elif component == "FFP":
        if frozen_ts is None:
            return None

        freezing_time = frozen_ts - collection_ts

        if freezing_time > timedelta(hours=8):
            return None

        shelf_life = 365

    else:
        raise ValueError("Invalid component type")

    # Last valid day is collection date + shelf life
    expiry_date = collection_ts.date() + timedelta(days=shelf_life)

    # Components expire at 23:59 on the last valid day
    expiry_datetime = datetime.combine(expiry_date, time(23, 59))

    return expiry_datetime