# Documentum ID: TOOLCHAIN-CONF-DELIVERY-01
# Description: Delivery Management
# Status: Effective

## 8. Delivery Management

## 8.1 Delivery Options
## 8.1.1 The system shall allow users to choose a delivery method for a rent, including pickup and delivery.
## 8.1.2 The system shall require the user to provide a delivery address when delivery is selected.
## 8.1.3 The system shall validate the delivery address before confirming the rent.

## 8.2 Delivery Scheduling
## 8.2.1 The system shall allow users to select a delivery time window.
## 8.2.2 The system shall validate that the selected delivery time window is available.
## 8.2.3 The system shall prevent scheduling delivery outside supported delivery hours.

## 8.3 Delivery Lifecycle
## 8.3.1 The system shall create a delivery record associated with the rent record when delivery is selected.
## 8.3.2 The system shall support delivery status values including Scheduled, In Transit, Delivered, and Failed.
## 8.3.3 The system shall allow authorized users to update delivery status.
## 8.3.4 The system shall notify the user when delivery status changes.

## 8.4 Delivery Fees
## 8.4.1 The system shall calculate delivery fees based on configured delivery rules.
## 8.4.2 The system shall include delivery fees in the invoice when applicable.

## 8.5 Delivery Access Control and Audit
## 8.5.1 The system shall restrict delivery status updates to authorized users.
## 8.5.2 The system shall log delivery lifecycle events.