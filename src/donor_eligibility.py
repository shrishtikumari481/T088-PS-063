from datetime import datetime


def check_donor_eligibility(donor, donation):
    """
    Checks whether a donor is eligible to donate blood.
    Returns ACCEPTED or DEFERRED with the first failed rule.
    """

    # BR-01: Check donor's age
    date_of_birth = datetime.strptime(
        donor["date_of_birth"], "%Y-%m-%d"
    ).date()

    donation_date = datetime.strptime(
        donation["collection_ts"], "%Y-%m-%d %H:%M:%S"
    ).date()

    age = donation_date.year - date_of_birth.year
    if (donation_date.month, donation_date.day) < (
        date_of_birth.month, date_of_birth.day
    ):
        age -= 1

    if age < 18 or age > 65:
        return "DEFERRED", "BR-01: AGE"

    if donor["first_time_donor"].lower() == "true" and age > 60:
        return "DEFERRED", "BR-01: FIRST_TIME_AGE"

    # BR-01: Check weight
    if float(donation["weight_kg"]) < 45:
        return "DEFERRED", "BR-01: WEIGHT"

    # BR-01: Check haemoglobin
    if float(donation["haemoglobin_g_dl"]) < 12.5:
        return "DEFERRED", "BR-01: HAEMOGLOBIN"

    # BR-01: Check previous deferral
    deferred_until = donor["deferred_until"].strip()

    if deferred_until and donation_date <= datetime.strptime(
        deferred_until, "%Y-%m-%d"
    ).date():
        return "DEFERRED", "BR-01: PREVIOUS_DEFERRAL"

    # BR-01: Check donation interval
    last_donation = donor["last_donation_date"].strip()

    if last_donation:
        last_date = datetime.strptime(
            last_donation, "%Y-%m-%d"
        ).date()

        days_since_last = (donation_date - last_date).days

        if donor["gender"] == "M" and days_since_last < 90:
            return "DEFERRED", "BR-01: DONATION_INTERVAL"

        if donor["gender"] == "F" and days_since_last < 120:
            return "DEFERRED", "BR-01: DONATION_INTERVAL"

    return "ACCEPTED", ""