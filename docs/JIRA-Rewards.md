[
  {
    "ticket_id": "JIRA-REW-901",
    "summary": "Loyalty Points Accrual Logic",
    "description": "Implement loyalty point accrual for completed and successfully settled rental activity, and ensure awarded points are applied to the user account according to the configurable reward policy.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-15T10:00:00Z",
        "text": "Implementation note: the specification refers to configurable business rules for point awards, but the exact reward formula is not yet finalized. I need confirmation on whether beta should use a temporary default rule or wait for the configurable policy source."
      }
    ]
  },
  {
    "ticket_id": "JIRA-REW-902",
    "summary": "Points Redemption and Discount Handling",
    "description": "Allow loyalty point redemption during billing, validate that the user has sufficient balance, and ensure redemption is recorded consistently together with the related financial outcome.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-REW-903",
    "summary": "Loyalty Tier Automation",
    "description": "Implement configurable loyalty tier assignment and automatic tier updates when user reward history crosses the relevant thresholds.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-REW-904",
    "summary": "Late Return Penalty Calculation",
    "description": "Implement late-return penalty calculation based on the applicable penalty policy and ensure the resulting penalty can be associated with the affected rental and billing flow.",
    "status": "In Progress",
    "comments": [
      {
        "author": "QA Marta",
        "timestamp": "2026-03-16T14:00:00Z",
        "text": "Policy gap: the penalty trigger is clear in principle, but the tolerance around overdue return timing is not fully specified. Please confirm whether the penalty should start immediately at the breach point or whether there is an allowed operational buffer before charges apply."
      }
    ]
  },
  {
    "ticket_id": "JIRA-REW-905",
    "summary": "Penalty Dispute Workflow",
    "description": "Implement penalty dispute submission and resolution so users can challenge penalty outcomes and authorized staff can record the final decision together with any resulting adjustment.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-REW-906",
    "summary": "Adjustment Audit Logging",
    "description": "Log loyalty and penalty adjustments in a way that preserves traceability, supports controlled review, and remains compatible with the platform's broader privacy and auditability expectations.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-17T09:00:00Z",
        "text": "Auditability note: the requirement expects user-linked traceability for adjustments, but we should confirm whether direct user-identifying values belong in the raw adjustment log or whether authorized reviewers should resolve identities through a controlled lookup path."
      }
    ]
  }
]