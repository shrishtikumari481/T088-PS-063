import csv
from pathlib import Path
from datetime import datetime, timedelta

from component_expiry import calculate_expiry
from screening import evaluate_screening
from blood_compatibility import (
    check_prbc_compatibility,
    check_ffp_compatibility,
    check_emergency_rh_exception
)
from allocation import allocate_blood_unit
from crossmatch import (
    create_reservation,
    check_reservation_status,
    emergency_uncrossmatched_issue,
    check_retrospective_crossmatch
)
from request_sla import (
    calculate_sla_deadline,
    calculate_partial_allocation,
    prioritize_shortage_queue
)
from hospital_quota import (
    check_daily_quota,
    calculate_replacement_ratio,
    calculate_adjusted_quota
)
from stock_monitor import check_stock_alert
from billing import calculate_invoice, evaluate_return
from reservation_manager import (
    reserve_unit,
    preempt_routine_reservation
)
from platelet_pooling import create_platelet_pool


# Project folders
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)


# Required output CSV structures
OUTPUT_FIELDS = {

    "unit_status.csv": [
        "unit_id",
        "ts",
        "status",
        "reason"
    ],

    "donation_eligibility.csv": [
        "donation_id",
        "donor_id",
        "decision",
        "failed_rule"
    ],

    "allocations.csv": [
        "request_id",
        "unit_id",
        "unit_group",
        "unit_rh",
        "compatibility_path",
        "reservation_state",
        "allocated_ts",
        "sla_met",
        "note"
    ],

    "stock_positions.csv": [
        "date",
        "blood_group",
        "rh",
        "component",
        "available",
        "quarantine",
        "crossmatched",
        "alert"
    ],

    "invoices.csv": [
        "hospital_id",
        "request_id",
        "unit_id",
        "component",
        "base_charge",
        "government_discount",
        "emergency_surcharge",
        "amount"
    ]
}


# Timestamp format used throughout the project
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class InventoryEngine:

    def __init__(self, data):

        # Store all input data
        self.data = data

        # Create quick lookup dictionaries
        self.donors = {
            donor["donor_id"]: donor
            for donor in data["donors"]
        }

        self.donations = {
            donation["donation_id"]: donation
            for donation in data["donations"]
        }

        self.hospitals = {
            hospital["hospital_id"]: hospital
            for hospital in data["hospitals"]
        }

        self.requests = {
            request["request_id"]: request
            for request in data["requests"]
        }

        self.request_status = {}

        # Store blood components
        self.components = {
            component["unit_id"]: component
            for component in data["components"]
        }

        # Store screening results by donation
        self.screening_results = {}

        for result in data["screening_results"]:

            donation_id = result["donation_id"]

            if donation_id not in self.screening_results:
                self.screening_results[donation_id] = []

            self.screening_results[donation_id].append(result)

        # Initial status of every blood unit
        self.unit_status = {}

        # Store allocation records
        self.allocations = []

        # Store invoice records
        self.invoices = []

        # Store cross-match reservations
        self.reservations = []

        # Store pending requests
        self.shortage_queue = []

        # Store generated reports
        self.output_records = {
            "unit_status.csv": [],
            "allocations.csv": [],
            "stock_positions.csv": [],
            "invoices.csv": []
        }

        print("Inventory Engine initialized successfully!")
        print("Total donors:", len(self.donors))
        print("Total donations:", len(self.donations))
        print("Total blood units:", len(self.components))
        print("Total hospital requests:", len(self.requests))


    def process_donation(self, donation_id, current_ts):

        # Find the donation
        donation = self.donations.get(donation_id)

        if donation is None:
            print("Donation not found:", donation_id)
            return

        # Find its components
        donation_components = [
            component
            for component in self.components.values()
            if component["donation_id"] == donation_id
        ]

        # Check donor eligibility
        from donor_eligibility import check_donor_eligibility

        donor = self.donors.get(donation["donor_id"])

        if donor is None:
            decision = "DEFERRED"
            failed_rule = "INVALID_DONOR"
        else:
            decision, failed_rule = check_donor_eligibility(
                donor, donation
            )

        # Process every component from this donation
        for component in donation_components:

            unit_id = component["unit_id"]

            if decision != "ACCEPTED":

                status = "DISCARDED"
                reason = "DONOR_INELIGIBLE: " + str(failed_rule)

            else:

                collection_ts = datetime.strptime(
                    donation["collection_ts"],
                    TIMESTAMP_FORMAT
                )

                frozen_ts = None

                if component["frozen_ts"]:
                    frozen_ts = datetime.strptime(
                        component["frozen_ts"],
                        TIMESTAMP_FORMAT
                    )

                expiry = calculate_expiry(
                    component["component"],
                    collection_ts,
                    donation["additive_solution"].lower() == "true",
                    frozen_ts
                )

                if expiry is None:
                    status = "DISCARDED"
                    reason = "INVALID_COMPONENT_EXPIRY"

                else:
                    component["expiry_date"] = expiry.strftime(
                        TIMESTAMP_FORMAT
                    )

                    status = "QUARANTINE"
                    reason = "AWAITING_TTI_SCREENING"

            self.unit_status[unit_id] = {
                "status": status,
                "reason": reason,
                "expiry_date": component.get("expiry_date", "")
            }

            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": status,
                "reason": reason
            })

        print("Donation processed:", donation_id)


    def process_screening(self, donation_id, current_ts):

        # Find the donation
        donation = self.donations.get(donation_id)

        if donation is None:
            print("Donation not found:", donation_id)
            return

        # Get all screening results for this donation
        results = self.screening_results.get(donation_id, [])

        # Get the collection timestamp
        collection_ts = datetime.strptime(
            donation["collection_ts"],
            TIMESTAMP_FORMAT
        )

        current_time = datetime.strptime(
            current_ts,
            TIMESTAMP_FORMAT
        )

        # Check whether any marker is reactive
        reactive = any(
            result["result"].upper() == "REACTIVE"
            for result in results
        )

        # Permanently defer donor if any marker is reactive
        if reactive:

            donor_id = donation["donor_id"]
            donor = self.donors.get(donor_id)

            if donor:
                donor["deferred_until"] = "9999-12-31"

        # Process every component from this donation
        for component in self.components.values():

            if component["donation_id"] != donation_id:
                continue

            unit_id = component["unit_id"]

            # Evaluate screening for this component
            status, permanently_deferred, reason = evaluate_screening(
                collection_ts,
                results,
                component["component"],
                current_time
            )

            # Update inventory status
            if unit_id in self.unit_status:

                self.unit_status[unit_id]["status"] = status
                self.unit_status[unit_id]["reason"] = reason

            else:
                self.unit_status[unit_id] = {
                    "status": status,
                    "reason": reason,
                    "expiry_date": component.get("expiry_date", "")
                }

            # Record the status change
            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": status,
                "reason": reason
            })

        print("Screening processed:", donation_id)

    def process_request(self, request_id, current_ts):
        """Validate a request and allocate compatible blood units."""

        if request_id not in self.requests:
            print("Invalid request ID:", request_id)
            return False

        request = self.requests[request_id]
        hospital_id = request["hospital_id"]

        if hospital_id not in self.hospitals:
            print("Invalid hospital ID:", hospital_id)
            return False

        units_needed = int(request["units"])
        if units_needed <= 0:
            return False

        urgency = request["urgency"].upper()
        component_type = request["component"].upper()

        if urgency not in ["EMERGENCY", "URGENT", "ROUTINE"]:
            return False

        patient_group = request["patient_group"].upper()
        patient_rh = request["patient_rh"].upper()

        patient_gender = request["patient_gender"].upper()
        patient_age = int(request["patient_age"])

        # Register the request
        self.request_status[request_id] = {
            "status": "PENDING",
            "request_ts": current_ts,
            "hospital_id": hospital_id,
            "component": component_type,
            "requested_units": units_needed,
            "urgency": urgency,
            "shortfall": units_needed,
            "allocated_units": []
        }

        # Find units that are currently available
        units_by_group = {}

        for unit_id, component in self.components.items():

            if component["component"].upper() != component_type:
                continue

            status_info = self.unit_status.get(unit_id, {})

            if status_info.get("status") != "AVAILABLE":
                continue

            expiry = status_info.get("expiry_date", "")

            if not expiry or expiry < current_ts:
                continue

            donation = self.donations.get(
                component["donation_id"]
            )

            if donation is None:
                continue

            donor = self.donors.get(donation["donor_id"])

            if donor is None:
                continue

            blood_group = donor["blood_group"].upper()
            rh = donor["rh"].upper()

            blood_type = blood_group + (
                "+" if rh in ["POS", "+"] else "-"
            )

            unit_data = dict(component)
            unit_data["unit_id"] = unit_id
            unit_data["expiry_date"] = expiry

            units_by_group.setdefault(
                blood_type, []
            ).append(unit_data)

        allocated_count = 0

        # Allocate units one at a time
        for _ in range(units_needed):

            selected = None
            compatibility_path = ""

            if component_type == "PRBC":

                result = allocate_blood_unit(
                    patient_group,
                    patient_rh,
                    units_by_group,
                    emergency=(urgency == "EMERGENCY"),
                    patient_gender=patient_gender,
                    patient_age=patient_age
                )

                if result:
                    selected = result["unit"]
                    selected_blood_type = result["blood_group"]

                    patient_blood_type = patient_group + (
                        "+" if patient_rh in ["POS", "+"] else "-"
                    )

                    if result["reason"] == "EMERGENCY_RH_POS":
                        compatibility_path = "EMERGENCY_RH_POS"

                    elif selected_blood_type == "O-" and patient_blood_type != "O-":
                        compatibility_path = "O_NEG_RESERVE"

                    elif selected_blood_type == patient_blood_type:
                        compatibility_path = "IDENTICAL"

                    else:
                        compatibility_path = "COMPATIBLE_" + selected_blood_type

            elif component_type == "FFP":

                for blood_type, units in units_by_group.items():

                    donor_group = blood_type[:-1]

                    if check_ffp_compatibility(
                        donor_group, patient_group
                    ) and units:

                        selected = min(
                            units,
                            key=lambda unit: unit["expiry_date"]
                        )

                        compatibility_path = (
                            "COMPATIBLE_" + blood_type
                        )
                        break

            elif component_type == "PLATELET":

                blood_type = patient_group + (
                    "+" if patient_rh in ["POS", "+"] else "-"
                )

                if units_by_group.get(blood_type):
                    selected = min(
                        units_by_group[blood_type],
                        key=lambda unit: unit["expiry_date"]
                    )
                    compatibility_path = "IDENTICAL"

            if selected is None:
                break

            unit_id = selected["unit_id"]

            donation = self.donations[
                self.components[unit_id]["donation_id"]
            ]
            donor = self.donors[donation["donor_id"]]

            unit_group = donor["blood_group"]
            unit_rh = donor["rh"]

            # PRBC units receive a 72-hour reservation
            if component_type == "PRBC":
                reservation = create_reservation(
                    unit_id,
                    request_id,
                    current_ts
                )

                self.reservations.append(reservation)

                reservation_state = "CROSSMATCHED"

                self.unit_status[unit_id]["status"] = (
                    "CROSSMATCHED"
                )

            else:
                reservation_state = "ALLOCATED"

            self.request_status[request_id][
                "allocated_units"
            ].append(unit_id)

            self.allocations.append({
                "request_id": request_id,
                "unit_id": unit_id,
                "unit_group": unit_group,
                "unit_rh": unit_rh,
                "compatibility_path": compatibility_path,
                "reservation_state": reservation_state,
                "allocated_ts": current_ts,
                "sla_met": "",
                "note": ""
            })

            self.output_records["allocations.csv"].append(
                self.allocations[-1]
            )

            # Remove the allocated unit from available stock
            for group_units in units_by_group.values():
                group_units[:] = [
                    unit for unit in group_units
                    if unit["unit_id"] != unit_id
                ]

            allocated_count += 1

        shortfall = units_needed - allocated_count

        self.request_status[request_id]["shortfall"] = shortfall

        if shortfall == 0:
            self.request_status[request_id]["status"] = "ALLOCATED"
        elif allocated_count > 0:
            self.request_status[request_id]["status"] = "PARTIAL"
        else:
            self.request_status[request_id]["status"] = "PENDING"

        print(
            "Request processed:",
            request_id,
            "| Allocated:",
            allocated_count,
            "| Shortfall:",
            shortfall
        )

        return True

    def process_issue(self, request_id, current_ts):

        # Find allocations belonging to this request
         request_allocations = [
            allocation
            for allocation in self.allocations
            if allocation["request_id"] == request_id
            and allocation["reservation_state"] != "ISSUED"
        ]

         if not request_allocations:
            print("No allocated units available to issue:", request_id)
            return False

         issued_count = 0

         for allocation in request_allocations:

            unit_id = allocation["unit_id"]

            # Confirm that the unit exists
            if unit_id not in self.unit_status:
                continue

            current_status = self.unit_status[unit_id]["status"]

            # Only available or cross-matched units can be issued
            if current_status not in ["AVAILABLE", "CROSSMATCHED"]:
                continue

            # Update blood unit status
            self.unit_status[unit_id]["status"] = "ISSUED"
            self.unit_status[unit_id]["reason"] = "ISSUED_TO_HOSPITAL"

            # Update allocation record
            allocation["reservation_state"] = "ISSUED"

            # Update cross-match reservation
            for reservation in self.reservations:

                if (
                    reservation["request_id"] == request_id
                    and reservation["unit_id"] == unit_id
                ):
                    reservation["reservation_state"] = "ISSUED"

            # Record the status change
            self.output_records["unit_status.csv"].append({
                "unit_id": unit_id,
                "ts": current_ts,
                "status": "ISSUED",
                "reason": "ISSUED_TO_HOSPITAL"
            })

            issued_count += 1

         print(
            "Issue processed:",
            request_id,
            "| Units issued:",
            issued_count
        )

         return issued_count > 0
    
    def process_commands(self, commands):

        print("\nStarting command execution...")

        for command in commands:

            command_type = command["type"]
            args = command["args"]

            if command_type == "DONATION":

                self.process_donation(
                    args["donation_id"],
                    args["ts"]
                )

            elif command_type == "SCREENING":

                self.process_screening(
                    args["donation_id"],
                    args["ts"]
                )
            elif command_type == "REQUEST":

                self.process_request(
                    args["request_id"],
                    args["ts"]
    )
            elif command_type == "ISSUE":

                self.process_issue(
                    args["request_id"],
                    args["ts"]
    )

            else:
                print(
                    "Command queued for later implementation:",
                    command_type
                )

        print("\nCommand processing completed.")


    def export_outputs(self):

        for filename, records in self.output_records.items():

            output_file = OUTPUT_DIR / filename

            with open(
                output_file,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.DictWriter(
                    file,
                    fieldnames=OUTPUT_FIELDS[filename]
                )

                writer.writeheader()
                writer.writerows(records)

            print("Generated:", filename)