import csv
from pathlib import Path

from donor_eligibility import check_donor_eligibility


# Find the main project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Input CSV files
DATA_DIR = BASE_DIR / "data"

DONORS_FILE = DATA_DIR / "donors.csv"
DONATIONS_FILE = DATA_DIR / "donations.csv"

# Output CSV file
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "donation_eligibility.csv"


def load_csv(filename):
    """Read a CSV file and return its rows."""
    with open(filename, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def generate_eligibility_report():

    # Load donor and donation information
    donors = load_csv(DONORS_FILE)
    donations = load_csv(DONATIONS_FILE)

    # Create a dictionary to find donors using donor_id
    donor_lookup = {
        donor["donor_id"]: donor
        for donor in donors
    }

    results = []

    # Check every donation
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

    # Save results in a new CSV file
    fieldnames = [
        "donation_id",
        "donor_id",
        "decision",
        "failed_rule"
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(results)

    print("Donor eligibility report generated successfully!")
    print("Total donations checked:", len(results))
    print("Output saved at:", OUTPUT_FILE)


if __name__ == "__main__":
    generate_eligibility_report()