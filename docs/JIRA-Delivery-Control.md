[
  {
    "ticket_id": "JIRA-DEL-801",
    "summary": "Delivery Option Selection",
    "description": "Implement the choice between pickup and delivery, including the collection of delivery-related address data and the validation needed before a delivery-based rental can proceed.",
    "status": "Closed",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-10T09:00:00Z",
        "text": "The address verification integration is in place. We should still confirm whether the current validation result is only a delivery-readiness check or also intended to serve as a customer-facing address quality decision."
      }
    ]
  },
  {
    "ticket_id": "JIRA-DEL-802",
    "summary": "Delivery Scheduling and Timing",
    "description": "Implement delivery-slot selection and time-window validation so users can request supported delivery periods without creating scheduling conflicts.",
    "status": "Closed",
    "comments": [
      {
        "author": "QA Marta",
        "timestamp": "2026-03-10T11:30:00Z",
        "text": "Please confirm how unsupported edge windows should appear in the user flow. There is a difference between a slot that is structurally outside delivery hours and one that is technically valid but already unavailable."
      }
    ]
  },
  {
    "ticket_id": "JIRA-DEL-803",
    "summary": "Delivery Status Lifecycle",
    "description": "Implement the delivery lifecycle flow and ensure the system can track operational delivery progress while keeping users informed when delivery state changes occur.",
    "status": "Closed",
    "comments": [
      {
        "author": "Backend Engineer Tomas",
        "timestamp": "2026-03-11T09:20:00Z",
        "text": "The operational status progression is implemented, but we should confirm whether all internal delivery transitions are meant to be exposed directly to users or whether some should remain back-office only."
      }
    ]
  },
  {
    "ticket_id": "JIRA-DEL-804",
    "summary": "Delivery Fee Calculation",
    "description": "Implement delivery fee calculation according to the configured logistics rules and ensure applicable delivery charges flow into billing in a consistent way.",
    "status": "Closed",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-11T13:00:00Z",
        "text": "Fee computation is wired into the delivery flow. Please confirm whether the delivery charge should always be treated as a separate visible billing component or may be folded into a broader total in some customer-facing views."
      }
    ]
  },
  {
    "ticket_id": "JIRA-DEL-805",
    "summary": "Delivery Event Logging",
    "description": "Log key delivery lifecycle events and delivery-management actions so authorized users can review the operational history when needed.",
    "status": "Closed",
    "comments": [
      {
        "author": "QA Marta",
        "timestamp": "2026-03-12T08:45:00Z",
        "text": "Audit review note: we should decide whether delivery history is intended mainly for operational troubleshooting, formal auditability, or both, because that affects how much detail should be retained in the event trail."
      }
    ]
  }
]