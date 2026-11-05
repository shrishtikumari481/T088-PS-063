from src.blood_compatibility import check_prbc_compatibility

def select_best_blood_group(
    patient_group,
    patient_rh,
    stock,
    emergency=False
):
    """
    Selects the best PRBC blood group based on BR-05.

    Priority:
    1. Identical blood group.
    2. Compatible group with largest available stock.
    3. Reserve O-negative units.
    """

    patient_blood = patient_group.upper() + (
        "+" if patient_rh.upper() in ["POS", "+"] else "-"
    )

    # Priority 1: Identical blood group
    if stock.get(patient_blood, 0) > 0:
        return patient_blood

    compatible_groups = []

    # Find all compatible blood groups
    for blood_group, units in stock.items():

        if units <= 0:
            continue

        donor_group = blood_group[:-1]
        donor_rh = blood_group[-1]

        if check_prbc_compatibility(
            donor_group,
            donor_rh,
            patient_group,
            patient_rh
        ):
            compatible_groups.append((blood_group, units))

    # Keep O-negative reserved
    non_reserved = [
        item for item in compatible_groups
        if item[0] != "O-"
    ]

    if non_reserved:
        non_reserved.sort(key=lambda item: item[1], reverse=True)
        return non_reserved[0][0]

    # O-negative can be used if emergency or no other
    # compatible stock is available
    o_negative_stock = stock.get("O-", 0)

    if o_negative_stock > 0 and emergency:
        return "O-"

    if o_negative_stock > 0 and not non_reserved:
        return "O-"

    return None


from datetime import datetime


def select_fefo_unit(units):
    """
    Selects the unit that expires first.

    Each unit must contain:
    unit_id and expiry_date.
    """

    if not units:
        return None

    valid_units = sorted(
        units,
        key=lambda unit: datetime.strptime(
            unit["expiry_date"], "%Y-%m-%d %H:%M:%S"
        )
    )

    return valid_units[0]


def allocate_blood_unit(
    patient_group,
    patient_rh,
    units_by_group,
    emergency=False
):
    """
    Selects the best blood group and then selects
    the earliest-expiring unit from that group.
    """

    # Count available units in each blood group
    stock = {
        blood_group: len(units)
        for blood_group, units in units_by_group.items()
    }

    # Select the best blood group
    selected_group = select_best_blood_group(
        patient_group,
        patient_rh,
        stock,
        emergency
    )

    # No compatible stock available
    if selected_group is None:
        return None

    # Select the earliest-expiring unit
    selected_unit = select_fefo_unit(
        units_by_group[selected_group]
    )

    if selected_unit is None:
        return None

    return {
        "unit": selected_unit,
        "blood_group": selected_group,
        "reason": "GROUP_PRIORITY_AND_FEFO"
    }