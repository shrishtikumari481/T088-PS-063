from datetime import datetime, timedelta


# Base charges for each blood component
COMPONENT_CHARGES = {
    "PRBC": 1550,
    "FFP": 400,
    "PLATELET": 400
}


def calculate_invoice(component, hospital_type, urgency):
    """
    Calculates the blood component charge.

    BR-10:
    - Government hospitals get 50% discount.
    - Emergency requests get Rs. 500 surcharge.
    """

    component = component.upper()
    hospital_type = hospital_type.upper()
    urgency = urgency.upper()

    if component not in COMPONENT_CHARGES:
        raise ValueError("Invalid component type")

    base_charge = COMPONENT_CHARGES[component]

    if hospital_type == "GOVERNMENT":
        government_discount = base_charge * 0.50
    else:
        government_discount = 0

    emergency_surcharge = 500 if urgency == "EMERGENCY" else 0

    amount = base_charge - government_discount + emergency_surcharge

    return {
        "base_charge": base_charge,
        "government_discount": government_discount,
        "emergency_surcharge": emergency_surcharge,
        "amount": amount
    }


def evaluate_return(issue_ts, return_ts, cold_chain):
    """
    Checks whether unused blood can be returned to stock.

    Return within 30 minutes with proper cold chain:
    RETURNED and not billed.

    Otherwise:
    DISCARDED and billed.
    """

    issue_time = datetime.strptime(
        issue_ts, "%Y-%m-%d %H:%M:%S"
    )

    return_time = datetime.strptime(
        return_ts, "%Y-%m-%d %H:%M:%S"
    )

    elapsed_time = return_time - issue_time

    if elapsed_time < timedelta(0):
        raise ValueError("Return time cannot be before issue time")

    if cold_chain and elapsed_time <= timedelta(minutes=30):
        return {
            "status": "RETURNED",
            "billable": False
        }

    return {
        "status": "DISCARDED",
        "billable": True
    }