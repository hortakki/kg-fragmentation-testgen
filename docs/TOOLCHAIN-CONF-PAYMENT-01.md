# Documentum ID: TOOLCHAIN-CONF-PAYMENT-01
# Description: Payments and Billing
# Status: Effective

## 6. Payments and Billing

## 6.1 Pricing Configuration
## 6.1.1 The system shall allow authorized users to define pricing for rentable items.
## 6.1.2 The system shall allow pricing to be defined per time unit (e.g., hourly, daily, weekly).
## 6.1.3 The system shall store pricing information associated with each rentable item.
## 6.1.4 The system shall ensure pricing changes do not affect already created rent records.

## 6.2 Price Calculation
## 6.2.1 The system shall calculate rental cost based on item pricing and rental duration.
## 6.2.2 The system shall calculate the total rental cost before confirming the rent.
## 6.2.3 The system shall ensure price calculation accuracy.
## 6.2.4 The system shall store the calculated price with the rent record.

## 6.3 Invoice Generation
## 6.3.1 The system shall generate an invoice for each Approved or Completed rent.
## 6.3.2 The system shall assign a unique identifier to each invoice.
## 6.3.3 The system shall include rent details, pricing, and total amount in the invoice.
## 6.3.4 The system shall store generated invoices.

## 6.4 Payment Processing
## 6.4.1 The system shall allow users to make payments for invoices.
## 6.4.2 The system shall record payment status.
## 6.4.3 The system shall support payment status values including Pending, Paid, and Failed.
## 6.4.4 The system shall associate payment records with the corresponding invoice and rent record.

## 6.5 Payment Status Management
## 6.5.1 The system shall update invoice status upon successful payment.
## 6.5.2 The system shall prevent duplicate payments for the same invoice.
## 6.5.3 The system shall allow authorized users to view payment status.

## 6.6 Refund Management
## 6.6.1 The system shall allow authorized users to initiate refunds.
## 6.6.2 The system shall record refund status.
## 6.6.3 The system shall associate refunds with the corresponding payment record.
## 6.6.4 The system shall ensure refund amount does not exceed original payment amount.

## 6.7 Billing History
## 6.7.1 The system shall maintain billing history for each user.
## 6.7.2 The system shall allow users to view their invoices and payment history.
## 6.7.3 The system shall ensure billing records cannot be modified after payment completion.

## 6.8 Billing Access Control
## 6.8.1 The system shall allow users to access their own billing records.
## 6.8.2 The system shall allow authorized users to access all billing records.
## 6.8.3 The system shall prevent unauthorized access to billing records.