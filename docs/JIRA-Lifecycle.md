[
  {
    "ticket_id": "JIRA-LIFE-201",
    "summary": "Implement Rent Creation Flow",
    "description": "Develop the initial rent request screen based on TOOLCHAIN-CONF-RENT-01 Section 2.1. The system must capture item selection, start date, and end date. Ensure a unique Rent ID is generated for every record.",
    "status": "Closed",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-02-10T08:00:00Z",
        "text": "Base flow implemented. Status is set to 'Requested' by default as per 2.1.6."
      }
    ]
  },
  {
  "ticket_id": "JIRA-LIFE-202",
  "summary": "Implement Automated Post-Rental Availability Logic",
  "description": "Develop the backend logic that returns equipment to its normal rentable state after the post-rental handling window has elapsed. The implementation must follow the current lifecycle definition and support category-dependent handling durations rather than relying on a single fixed timer.",
  "status": "In Progress",
  "attachments": ["EMAIL_OPS_MixerSpecialRule.txt"],
  "comments": [
    {
      "author": "Developer Dave",
      "timestamp": "2026-02-20T10:00:00Z",
      "text": "Based on the older lifecycle notes, I assumed there was one uniform cooldown period after return and started wiring the timer around that interpretation."
    },
    {
      "author": "QA Engineer Marta",
      "timestamp": "2026-02-20T11:30:00Z",
      "text": "Please re-check which lifecycle version you used. The newer documentation no longer describes the post-rental step the same way as the archived one, and it appears to rely on category-based handling. I cannot find the referenced lookup or matrix in the available materials."
    }
  ]
},
  {
    "ticket_id": "JIRA-LIFE-203",
    "summary": "Rent Approval Logic and Permissions",
    "description": "Implement approval/rejection functionality for authorized users. Status should transition to 'Approved' or 'Rejected' accordingly.",
    "status": "Closed",
    "comments": [
      {
        "author": "Backend Engineer Tomas",
        "timestamp": "2026-02-12T14:20:00Z",
        "text": "RBAC (Role-Based Access Control) integrated. Only users with 'OPERATOR' or 'ADMIN' roles can trigger approval."
      }
    ]
  },
  {
    "ticket_id": "JIRA-LIFE-204",
    "summary": "Manual Rent Completion for Operators",
    "description": "Allow authorized users to manually trigger rent completion. This is required for early returns.",
    "status": "In Progress",
    "comments": [
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-21T10:15:00Z",
        "text": "Clarification needed: If an operator completes a rent early, does the 'Maintenance' (v1.2) period start immediately, or only at the original end date?"
      }
    ]
  },
  {
  "ticket_id": "JIRA-LIFE-205",
  "summary": "Bug: Penalty applied during early operator cancellation",
  "description": "An operator reported that a rent was stopped shortly after it became active, but the system still applied a penalty fee. Based on earlier lifecycle guidance, there may have been a short tolerance window in which this kind of early cancellation should not have triggered the charge.",
  "status": "New",
  "comments": [
    {
      "author": "Developer Dave",
      "timestamp": "2026-02-21T09:00:00Z",
      "text": "I checked the current cancellation rules and they still allow stopping an active rent, but I cannot find the earlier exemption language that would have waived the penalty in the initial operator tolerance window. It may have been removed, or it may simply be missing from the latest write-up."
    },
    {
      "author": "PM Peter",
      "timestamp": "2026-02-21T11:00:00Z",
      "text": "This needs confirmation. If the newer lifecycle material dropped that exception without an explicit decision, we need to determine whether that was intentional or a documentation gap."
    }
  ]
}
]