from src.donor_eligibility import check_donor_eligibility


def create_donor(gender="M", age_status="false",
                 last_donation="", deferred_until=""):
    return {
        "date_of_birth": "2000-01-01",
        "gender": gender,
        "first_time_donor": age_status,
        "last_donation_date": last_donation,
        "deferred_until": deferred_until
    }


def create_donation(weight="50", hb="13.0"):
    return {
        "collection_ts": "2026-10-10 10:00:00",
        "weight_kg": weight,
        "haemoglobin_g_dl": hb
    }


def test_eligible_donor():
    donor = create_donor()
    donation = create_donation()

    result = check_donor_eligibility(donor, donation)

    assert result == ("ACCEPTED", "")


def test_low_weight():
    donor = create_donor()
    donation = create_donation(weight="44")

    result = check_donor_eligibility(donor, donation)

    assert result == ("DEFERRED", "BR-01: WEIGHT")


def test_low_haemoglobin():
    donor = create_donor()
    donation = create_donation(hb="12.0")

    result = check_donor_eligibility(donor, donation)

    assert result == ("DEFERRED", "BR-01: HAEMOGLOBIN")


def test_male_donation_interval():
    donor = create_donor(last_donation="2026-08-01")
    donation = create_donation()

    result = check_donor_eligibility(donor, donation)

    assert result == ("DEFERRED", "BR-01: DONATION_INTERVAL")


def test_female_donation_interval():
    donor = create_donor(
        gender="F",
        last_donation="2026-06-20"
    )
    donation = create_donation()

    result = check_donor_eligibility(donor, donation)

    assert result == ("DEFERRED", "BR-01: DONATION_INTERVAL")