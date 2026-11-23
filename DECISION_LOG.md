# T088 – PS-063
# Decision Log
## Blood Bank Inventory and Cross-Match Allocation Engine

**Team ID:** T088  
**Problem Statement:** PS-063  
**Domain:** Healthcare / Blood Bank

## 1. Purpose

This document records the major technical and architectural decisions made during the development of the Blood Bank Inventory and Cross-Match Allocation Engine. Each decision includes its reason and impact on the project.

## 2. Technical and Architectural Decisions

### D-01: Selection of Python 3.13

**Decision:** Python 3.13 was selected as the programming language.

**Reason:** Python satisfies the project requirement of Python 3.10 or above and supports modular application development.

**Impact:** The system's processing logic, validation functions, and business rules are implemented using Python.

### D-02: CSV-Based Input Data

**Decision:** CSV files were selected for storing and providing input data.

**Reason:** The project data is supplied in CSV format, making it convenient to read, process, and validate.

**Impact:** Donor, donation, component, hospital, request, and screening information can be processed through structured CSV files.

### D-03: Use of pytest

**Decision:** pytest was selected as the automated testing framework.

**Reason:** It supports automated execution of test cases and helps verify individual business rules.

**Impact:** The project includes automated tests for validating functionality and handling different scenarios.

### D-04: Modular System Architecture

**Decision:** The application was designed using separate modules for different responsibilities.

**Reason:** Separating donor management, donation processing, screening, inventory, allocation, and billing makes the system easier to maintain and test.

**Impact:** Individual functionalities can be developed, tested, and maintained separately.

### D-05: Individual Blood Component Tracking

**Decision:** Each separated blood component is tracked individually.

**Reason:** PRBC, FFP, and platelets have different storage conditions, expiry periods, and allocation requirements.

**Impact:** The system can maintain individual component status, availability, and expiry information.

### D-06: Unique Business Rule Identifiers

**Decision:** Each business rule was assigned a unique identifier from BR-01 to BR-12.

**Reason:** Unique identifiers make it easier to connect requirements with implementation and test cases.

**Impact:** The 12 business rules can be independently identified, implemented, and verified.

### D-07: CSV-Based Output Reports

**Decision:** CSV files were selected as the output format.

**Reason:** CSV output provides a structured format for reviewing system results and follows the required project output format.

**Impact:** The system generates reports containing information about inventory, allocations, eligibility, unit status, and invoices.

## 3. Decision Summary

| Decision ID | Area | Selected Approach |
|---|---|---|
| D-01 | Programming Language | Python 3.13 |
| D-02 | Input Data | CSV |
| D-03 | Testing | pytest |
| D-04 | Architecture | Modular Architecture |
| D-05 | Inventory Tracking | Individual Component Tracking |
| D-06 | Requirements | Unique BR-IDs |
| D-07 | Output Reports | CSV |

## 4. Conclusion

These decisions establish the technical and architectural foundation of the Blood Bank Inventory and Cross-Match Allocation Engine. They support modular development, structured data processing, automated testing, and traceability of the project's 12 business rules.

The decisions documented here describe the selected project approach and should remain consistent with the final implementation.
