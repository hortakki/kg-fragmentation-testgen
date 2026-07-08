[
  {
    "ticket_id": "JIRA-PAY-601",
    "summary": "Pricing Configuration Service",
    "description": "Implement the pricing configuration layer so authorized users can define rental pricing structures and apply them consistently to rentable items without retroactively changing already established rental records.",
    "status": "Closed"
  },
  {
    "ticket_id": "JIRA-PAY-602",
    "summary": "Price Calculation and Precision",
    "description": "Implement rental cost calculation based on duration and pricing rules, and make sure the resulting amount is derived consistently across calculation, storage, and user-facing display. International billing and currency presentation should be treated as a related operational concern, but must not silently override the core pricing logic.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-01T10:00:00Z",
        "text": "The current specification defines correctness expectations for the total, but it does not fully spell out how edge-case fractions should be handled at each calculation stage. I started with a simplified approach for partial-unit handling, but this needs confirmation before we freeze the behavior."
      },
      {
        "author": "QA Marta",
        "timestamp": "2026-03-01T14:00:00Z",
        "text": "Please verify the consistency of subtotal, tax, and final amount handling. A display-friendly simplification in one layer can still produce visible mismatches later if the stored and presented totals are derived differently."
      },
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-04T15:00:00Z",
        "text": "UI note: finance asked for cleaner presentation in one of the pilot currency scenarios, so I explored a more compact display format there while keeping more precise values in the underlying records. We need confirmation that the user-facing total must always match the persisted billing amount exactly."
      }
    ]
  },
  {
    "ticket_id": "JIRA-PAY-603",
    "summary": "Invoice Generation Engine",
    "description": "Generate invoices for billable rental outcomes, assign stable invoice identifiers, and store the invoice content together with the relevant rental and pricing details.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-PAY-604",
    "summary": "Payment Processing Integration",
    "description": "Implement payment handling, including payment-state tracking and linkage between payment, invoice, and rental records. Clarify how unsuccessful payment outcomes should affect downstream rental and availability behavior.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Tomas",
        "timestamp": "2026-03-02T09:00:00Z",
        "text": "There is a cross-module ambiguity here: when a payment attempt does not complete successfully, I do not yet know whether the related rental should remain operationally blocked, return to normal availability, or wait for a separate business decision."
      }
    ]
  },
  {
    "ticket_id": "JIRA-PAY-605",
    "summary": "Duplicate Payment Prevention",
    "description": "Implement idempotent payment protection so the same invoice cannot be settled multiple times through repeated requests or retries.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-PAY-606",
    "summary": "Refund Management Logic",
    "description": "Support authorized refund handling while preserving traceability to the original payment and ensuring the refunded amount remains within the permitted financial boundary.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-PAY-607",
    "summary": "Billing History and Immutability",
    "description": "Implement billing history access and preserve the immutability expectations of completed financial records so users and administrators can review prior invoices and payments without altering finalized outcomes.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-PAY-608",
    "summary": "Billing Access Control",
    "description": "Implement access control rules for billing records so users can view only their own financial history while authorized roles can review broader payment and invoice data.",
    "status": "Closed"
  }
]