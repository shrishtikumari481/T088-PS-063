# Blood Bank Inventory and Cross-Match Allocation Engine

## Project Information
- Team ID: T088
- Problem Statement: PS-063
- Domain: Healthcare / Blood Bank
- Language: Python 3.13

## Project Overview
The Blood Bank Inventory and Cross-Match Allocation Engine
is designed to manage blood donations, component processing,
screening, inventory, and hospital requests.

## Main Features
1. Donor registration and eligibility validation.
2. Blood donation and component separation.
3. TTI screening and quarantine management.
4. Blood group compatibility and cross-matching.
5. Hospital blood requests and allocation.
6. Inventory tracking and expiry management.
7. Hospital invoices and shortage alerts.

## Technology Stack
- Python
- CSV files
- Pytest
- Git and GitHub

## Project Structure
- data/ - Input sample datasets
- docs/ - Design documentation
- src/ - Application source code
- tests/ - Test cases
- outputs/ - Generated output files

## Team
- Shrishti Kumari
- USN: 1AT24CG078

## Run the project

Use Python 3.10 or newer (tested with Python 3.13).

From the project root:

```bash
python -m pip install pytest
python -m src.main
```

The application reads the CSV files in `data/`, processes `data/commands.txt`
in strict file order, and writes the five required reports to `outputs/`.

## Run automated tests

```bash
python -m pytest -q
```

The regression suite covers donor eligibility, component expiry, screening,
compatibility, allocation, cross-match reservations, request SLA, hospital
quotas, stock alerts, billing, returns, cancellation, and platelet pooling.

## Input and output contract

The application accepts the company-provided CSV schema and command types:
`DONATION`, `SCREENING`, `REQUEST`, `ISSUE`, `RETURN`, `CROSSMATCH_RESULT`,
`CANCEL_REQUEST`, `DAILY_RUN`, `PRINT_STOCK`, and `PRINT_INVOICE`.

Generated files:
- `outputs/unit_status.csv`
- `outputs/donation_eligibility.csv`
- `outputs/allocations.csv`
- `outputs/stock_positions.csv`
- `outputs/invoices.csv`

All output headers follow the required column order in the supplied data-pack
README. The application does not require a graphical interface; it is a
CSV-driven Python backend.

## Project Demo Video

[Watch the Project Demo Video](https://drive.google.com/file/d/1MkgmI6ii4Xnsaibbus9SgeSgd_2Ih0Vp/view?usp=sharing)
