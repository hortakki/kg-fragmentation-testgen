[
  {
    "ticket_id": "JIRA-NOTIF-501",
    "summary": "Lifecycle Event Notification Triggers",
    "description": "Implement notification triggers for the key rental lifecycle changes defined in the current notification specification, ensuring that user-facing and process-facing transitions both emit the expected events.",
    "status": "Closed"
  },
  {
    "ticket_id": "JIRA-NOTIF-502",
    "summary": "Email Delivery Reliability",
    "description": "Implement the email delivery service with failure handling and retry support so message delivery remains dependable under transient delivery issues.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-02-25T09:00:00Z",
        "text": "The retry flow is now limited to a small number of repeated attempts before the failure is escalated into the operational logging path. Please confirm whether that threshold should stay configurable or remain fixed for beta."
      }
    ]
  },
  {
    "ticket_id": "JIRA-NOTIF-503",
    "summary": "Reminder Notification Scheduling",
    "description": "Implement reminder messages around rental start and end milestones, with configurable timing so deployment teams can adjust reminder lead times without code changes.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-NOTIF-504",
    "summary": "Administrative Notification Flow",
    "description": "Notify authorized operational users about new requests, approval-related workload, and system-side issues that affect rental processing.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-NOTIF-505",
    "summary": "Notification Content Templates",
    "description": "Implement the notification templates so they include the key rental details required by the current specification, while keeping field naming consistent across the product and warehouse-facing terminology.",
    "status": "In Progress",
    "comments": [
      {
        "author": "QA Marta",
        "timestamp": "2026-02-25T14:00:00Z",
        "text": "Please confirm which identifier wording should appear in outbound messages. The specification and the warehouse-facing screens do not use exactly the same term, and I want to avoid sending emails that confuse end users."
      }
    ]
  },
  {
    "ticket_id": "JIRA-NOTIF-506",
    "summary": "User Notification Preferences",
    "description": "Allow users to manage notification preferences by category, while clarifying whether any event classes are considered business-critical and therefore not fully optional.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-02-26T10:00:00Z",
        "text": "There is a policy ambiguity here: product preference settings suggest broad user control, but management feedback indicates that some approval-related messages may need to remain non-optional. I need confirmation before deciding whether these events should bypass normal preference filtering."
      }
    ]
  },
  {
    "ticket_id": "JIRA-NOTIF-507",
    "summary": "Notification Event Logging",
    "description": "Log notification generation and delivery outcomes so authorized users can review what was sent, whether delivery succeeded, and where failures occurred.",
    "status": "To Do"
  }
]