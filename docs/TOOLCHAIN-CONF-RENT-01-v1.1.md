# Documentum ID: TOOLCHAIN-CONF-RENT-01
# Description: Rent lifecycle management
# Status: Archived (v1.1)

## 2. Rent Lifecycle Management

## 2.1 Rent Creation
## 2.1.1 The system shall allow authenticated users to create a rent request for an available rentable item.
## 2.1.2 The system shall require the user to select the rentable item when creating a rent request.
## 2.1.3 The system shall require the user to provide a rental start date and rental end date.
## 2.1.4 The system shall validate that all required fields are provided before creating the rent request.
## 2.1.5 The system shall assign a unique identifier to each rent record.
## 2.1.6 The system shall store the rent record with status set to Requested upon creation.

## 2.2 Rent Validation Rules
## 2.2.1 The system shall validate that the selected rentable item exists.
## 2.2.2 The system shall validate that the rentable item is available for the requested rental period.
## 2.2.3 The system shall prevent creation of overlapping rent records for the same rentable item.
## 2.2.4 The system shall validate that the rental start date is earlier than the rental end date.
## 2.2.5 The system shall prevent creation of rent records with rental periods in the past, unless explicitly permitted.

## 2.3 Rent Approval
## 2.3.1 The system shall allow authorized users to approve rent requests.
## 2.3.2 The system shall allow authorized users to reject rent requests.
## 2.3.3 The system shall update the rent status to Approved when a rent request is approved.
## 2.3.4 The system shall update the rent status to Rejected when a rent request is rejected.
## 2.3.5 The system shall prevent unauthorized users from approving or rejecting rent requests.

## 2.4 Rent Activation
## 2.4.1 The system shall update the rent status to Active when the rental start date is reached.
## 2.4.2 The system shall allow authorized users to manually activate a rent.
## 2.4.3 The system shall prevent activation of rent records that are not in Approved status.

## 2.5 Rent Completion and Cleaning
## 2.5.1 Upon reaching the rental end date, the system shall update the status to 'Cleaning'.
## 2.5.2 The 'Cleaning' status must persist for a fixed duration of 120 minutes for all equipment types.
## 2.5.3 After the 120-minute period, the status automatically transitions to 'Available'.

## 2.6 Rent Cancellation
## 2.6.1 The system shall allow users to cancel rent records that are in Requested status.
## 2.6.2 **Operator Grace Period:** Authorized operators may cancel an 'Active' rent record within the first 30 minutes of the rental period without incurring any penalty fees.
## 2.6.3 The system shall update the rent status to Cancelled when a rent is cancelled.
## 2.6.4 The system shall prevent cancellation of rent records that are already Completed or Cancelled.

## 2.7 Rent Modification Rules
## 2.7.1 The system shall allow modification of rent records only when the rent status is Requested.
## 2.7.2 The system shall prevent modification of rent records that are in Approved, Active, Completed, Rejected, or Cancelled status, unless explicitly permitted.
## 2.7.3 The system shall validate all changes before saving modifications.

## 2.8 Rent History and Audit
## 2.8.1 The system shall maintain the full lifecycle history of each rent record.
## 2.8.2 The system shall log all rent lifecycle events, including creation, approval, rejection, activation, completion, cancellation, and modification.
## 2.8.3 The system shall store the timestamp and user identifier for each lifecycle event.
## 2.8.4 The system shall ensure that rent history records cannot be modified or deleted.

## 2.9 Rent Access Control
## 2.9.1 The system shall allow users to view their own rent records.
## 2.9.2 The system shall allow authorized users to view all rent records.
## 2.9.3 The system shall prevent unauthorized access to rent records.
## 2.9.4 The system shall ensure that only authorized users can modify rent records.