[
  {
    "ticket_id": "JIRA-ITEM-301",
    "summary": "Database schema for Item Identification and Tracking",
    "description": "Implement the data model for rentable items, including a stable identifier strategy and support for availability tracking. The backend design should remain compatible with warehouse operations, while staying aligned with the business-facing item model defined in the current specification.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Backend Engineer Tomas",
        "timestamp": "2026-02-21T09:00:00Z",
        "text": "Technical note: our indexing and downstream storage path would be simpler with a scanner-friendly numeric identifier than with the mixed-format code used in the business documentation. I need confirmation on whether the warehouse-facing identifier and the formal item identifier are supposed to be the same thing."
      },
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-21T10:30:00Z",
        "text": "Please clarify the source of truth. The current specification describes the item identifier differently from the implementation direction discussed here, so frontend validation and persistence may diverge unless we separate the business identifier from the operational one."
      }
    ],
    "attachments": ["EMAIL_LOGISTICS_Barcode_Requirement.txt"]
  },
  {
    "ticket_id": "JIRA-ITEM-302",
    "summary": "Item Creation UI with Mandatory Fields",
    "description": "Create the admin interface for item creation. The screen must capture all required attributes defined in the current item management specification, including the core identifier and the availability-related inputs needed at creation time.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-02-21T14:00:00Z",
        "text": "The screen is ready, but I aligned the visible identifier label with the terminology commonly used by warehouse staff rather than the formal wording from the specification. Please confirm whether this should remain only a UI alias or whether the underlying field meaning is also different."
      }
    ]
  },
  {
    "ticket_id": "JIRA-ITEM-303",
    "summary": "Implement Item Modification and Validation",
    "description": "Allow authorized users to modify item details. The system must validate all required fields before saving changes and should preserve identifier consistency for downstream operational processes.",
    "status": "To Do",
    "comments": [
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-22T08:15:00Z",
        "text": "Do modifications include the operational identifier as well, or only the business-facing item details? If warehouse scanning depends on a stable machine-readable identifier, we may need to restrict edits after creation."
      }
    ]
  },
  {
    "ticket_id": "JIRA-ITEM-304",
    "summary": "Item Availability Status Toggle",
    "description": "Implement the immediate status change for items (Available/Unavailable). Ensure items marked Unavailable cannot be rented.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-02-22T10:00:00Z",
        "text": "Logic check: If an item is currently 'Active' in a rent record, can an admin still set it to 'Unavailable'? The specification says status changes take effect immediately."
      }
    ]
  },
  {
    "ticket_id": "JIRA-ITEM-305",
    "summary": "Item Deletion Logic (Soft Delete)",
    "description": "Implement deletion of items using a soft-delete approach instead of physical removal. Prevent deletion when the item is still referenced by active rental activity, and confirm how the business deletion outcome should map to the current technical status model.",
    "status": "To Do",
    "comments": [
      {
        "author": "Backend Engineer Tomas",
        "timestamp": "2026-02-22T12:00:00Z",
        "text": "Terminology check: the deletion outcome described in the specification does not map cleanly to the status values currently supported in the database. I need confirmation whether deleted items should reuse a non-rentable status or whether this requires a separate lifecycle value."
      }
    ]
  }
]