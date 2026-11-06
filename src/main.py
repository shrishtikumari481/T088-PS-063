from inventory_engine import InventoryEngine
import csv
from pathlib import Path

from donor_eligibility import check_donor_eligibility


# Project folders
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)


# Input CSV files
INPUT_FILES = {
    "donors": "donors.csv",
    "donations": "donations.csv",
    "components": "components.csv",
    "screening_results": "screening_results.csv",
    "hospitals": "hospitals.csv",
    "hospital_quotas": "hospital_quotas.csv",
    "requests": "requests.csv"
}


def load_csv(filename):
    """Load a CSV file and return its rows."""
    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Missing input file: {file_path}")

    with open(file_path, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_all_data():
    """Load all project input CSV files."""

    data = {}

    for key, filename in INPUT_FILES.items():
        data[key] = load_csv(filename)

    return data


def load_commands():
    """Read and validate commands while preserving their order."""

    commands_file = DATA_DIR / "commands.txt"

    if not commands_file.exists():
        raise FileNotFoundError("commands.txt not found")

    command_fields = {
        "DONATION": ["donation_id", "ts"],
        "SCREENING": ["donation_id", "ts"],
        "REQUEST": ["request_id", "ts"],
        "ISSUE": ["request_id", "ts"],
        "RETURN": ["request_id", "ts", "units", "cold_chain"],
        "CROSSMATCH_RESULT": ["request_id", "ts", "result"],
        "CANCEL_REQUEST": ["request_id", "ts"],
        "DAILY_RUN": ["date"],
        "PRINT_STOCK": ["date"],
        "PRINT_INVOICE": ["hospital_id", "from_date", "to_date"]
    }

    commands = []

    with open(commands_file, "r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            line = line.strip()

            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            command_type = parts[0].strip()

            if command_type not in command_fields:
                raise ValueError(
                    f"Unknown command at line {line_number}: {command_type}"
                )

            expected_fields = command_fields[command_type]
            values = [value.strip() for value in parts[1:]]

            if len(values) != len(expected_fields):
                raise ValueError(
                    f"Incorrect number of fields at line {line_number}"
                )

            

            commands.append({
                "type": command_type,
                "args": dict(zip(expected_fields, values)),
                "line_number": line_number
            })

    return commands

def generate_eligibility_report(data):
    """Generate the donor eligibility output."""

    donors = data["donors"]
    donations = data["donations"]

    donor_lookup = {
        donor["donor_id"]: donor
        for donor in donors
    }

    results = []

    for donation in donations:

        donor_id = donation["donor_id"]
        donor = donor_lookup.get(donor_id)

        if donor is None:
            decision = "DEFERRED"
            failed_rule = "INVALID_DONOR"

        else:
            decision, failed_rule = check_donor_eligibility(
                donor, donation
            )

        results.append({
            "donation_id": donation["donation_id"],
            "donor_id": donor_id,
            "decision": decision,
            "failed_rule": failed_rule
        })

    output_file = OUTPUT_DIR / "donation_eligibility.csv"

    fieldnames = [
        "donation_id",
        "donor_id",
        "decision",
        "failed_rule"
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("Donor eligibility report generated.")
    print("Donations checked:", len(results))


def main():

    print("Starting Blood Bank Inventory System...")

    # Load all input data
    data = load_all_data()

    # Load commands
    commands = load_commands()

    engine = InventoryEngine(data)

    engine.process_commands(commands)

    engine.export_outputs()

    print("\nInput data loaded successfully!")

    for name, rows in data.items():
        print(f"{name}: {len(rows)} records")

    print("Commands loaded:", len(commands))

   # Generate donor eligibility report
    generate_eligibility_report(data)

   # Initialize and execute the inventory engine
    engine = InventoryEngine(data)

   # Process all commands from commands.txt
    engine.process_commands(commands)

   # Generate the output CSV files
    engine.export_outputs()

print("\nApplication processing completed.")


if __name__ == "__main__":
    main()