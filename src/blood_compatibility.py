# BR-04: PRBC ABO and Rh compatibility

PRBC_COMPATIBILITY = {
    "O-": ["O-"],
    "O+": ["O-", "O+"],
    "A-": ["O-", "A-"],
    "A+": ["O-", "O+", "A-", "A+"],
    "B-": ["O-", "B-"],
    "B+": ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
}


def check_prbc_compatibility(donor_group, donor_rh, patient_group, patient_rh):
    """
    Checks PRBC compatibility between donor and patient.

    Returns True if compatible, otherwise False.
    """

    donor_blood = donor_group.upper() + (
        "+" if donor_rh.upper() in ["POS", "+"] else "-"
    )

    patient_blood = patient_group.upper() + (
        "+" if patient_rh.upper() in ["POS", "+"] else "-"
    )

    compatible_groups = PRBC_COMPATIBILITY.get(patient_blood, [])

    return donor_blood in compatible_groups

def check_emergency_rh_exception(
    donor_rh,
    patient_rh,
    patient_gender,
    patient_age,
    urgency,
    rh_negative_stock
):
    """
    Checks whether an Rh-negative patient can receive
    Rh-positive blood during an emergency.
    """

    if donor_rh.upper() not in ["POS", "+"]:
        return False

    if patient_rh.upper() not in ["NEG", "-"]:
        return False

    if urgency.upper() != "EMERGENCY":
        return False

    if rh_negative_stock != 0:
        return False

    if patient_gender.upper() == "M":
        return True

    if patient_gender.upper() == "F" and patient_age > 50:
        return True

    return False

# BR-04: FFP compatibility

FFP_COMPATIBILITY = {
    "O": ["O", "A", "B", "AB"],
    "A": ["A", "AB"],
    "B": ["B", "AB"],
    "AB": ["AB"]
}


def check_ffp_compatibility(donor_group, patient_group):

    donor_group = donor_group.upper()
    patient_group = patient_group.upper()

    compatible_groups = FFP_COMPATIBILITY.get(
        patient_group, []
    )

    return donor_group in compatible_groups