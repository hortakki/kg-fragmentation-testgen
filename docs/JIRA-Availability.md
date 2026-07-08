[
  {
    "ticket_id": "JIRA-AVAIL-401",
    "summary": "Availability Calculation Logic",
    "description": "Implement the core availability calculation so the system derives rentable periods from existing rental activity, prevents invalid overlaps, and refreshes results as lifecycle changes happen. The implementation should remain consistent with the current availability specification and avoid relying on outdated uniform timing assumptions.",
    "status": "Closed",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-02-23T09:00:00Z",
        "text": "Completed the overlap checks and lifecycle-triggered refresh flow. One implementation note: an earlier discussion suggested using a single fallback delay after certain rental events, so I initially followed that interpretation before rechecking the current availability rules."
      }
    ]
  },
  {
    "ticket_id": "JIRA-AVAIL-402",
    "summary": "Availability Query API",
    "description": "Develop the endpoint for checking whether an item can be rented within a requested period, ensuring the response reflects the latest rental and item-state information at query time.",
    "status": "In Progress",
    "comments": [
      {
        "author": "QA Marta",
        "timestamp": "2026-02-23T11:00:00Z",
        "text": "Found an ambiguity in query results after the recent item-management changes. Records that are no longer operationally valid are being surfaced through the same availability wording used for temporarily blocked items, which may mislead users about whether the item is recoverable or simply not rentable at the moment."
      }
    ]
  },
  {
    "ticket_id": "JIRA-AVAIL-403",
    "summary": "Manual Availability Restrictions",
    "description": "Allow authorized users to define manual non-rentable periods and ensure those restrictions take precedence over otherwise rentable time windows.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-AVAIL-404",
    "summary": "Maintenance Period Management",
    "description": "Implement maintenance windows for items, ensure those periods block rental activity, and make the item appear non-rentable while the maintenance window is in effect.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Tomas",
        "timestamp": "2026-02-24T10:00:00Z",
        "text": "Current implementation path uses the existing non-rentable status handling for maintenance-related periods as well. We should confirm whether the user interface needs to distinguish maintenance from other forms of temporary unavailability."
      }
    ]
  },
  {
    "ticket_id": "JIRA-AVAIL-405",
    "summary": "Real-time Status Sync",
    "description": "Ensure availability changes are applied immediately when relevant rental lifecycle events or availability controls are updated.",
    "status": "To Do"
  }
]