[
  {
    "ticket_id": "JIRA-REP-701",
    "summary": "Rent Report Generation Logic",
    "description": "Implement rent reporting so authorized users can review rental records together with the core identifying and timing information required by the reporting specification. The implementation should remain consistent with the currently supported identifier model, while also accounting for historical data representations that may differ from present-day operational terminology.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-05T09:00:00Z",
        "text": "Implementation note: the reporting UI is currently leaning toward the warehouse-facing identifier wording rather than the formal term used in the specification. Please confirm whether the report output should mirror the business-facing identifier, the operational alias, or both."
      },
      {
        "author": "QA Marta",
        "timestamp": "2026-03-05T11:00:00Z",
        "text": "Compatibility concern: some historical rental records appear to use an earlier identifier representation, so report output may become inconsistent unless we define how legacy and current item references should be normalized."
      }
    ]
  },
  {
    "ticket_id": "JIRA-REP-702",
    "summary": "Financial Report Accuracy",
    "description": "Develop financial reporting so payment and invoice data can be summarized accurately and consistently across report views and exported outputs. Please clarify how display-oriented billing presentation should relate to the financially authoritative stored totals.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Tomas",
        "timestamp": "2026-03-06T10:00:00Z",
        "text": "Accuracy question: when the reporting layer aggregates rental totals, should it rely on the stored accounting values, the customer-visible display amounts, or a separately recomputed value? We need one clear source of truth to avoid mismatches between invoices and exported summaries."
      }
    ]
  },
  {
    "ticket_id": "JIRA-REP-703",
    "summary": "User Activity and Audit Logging",
    "description": "Implement user activity reporting and audit logging for critical system events, while preserving traceability and staying aligned with privacy constraints around what user-related data may appear in logs and operational views.",
    "status": "In Progress",
    "comments": [
      {
        "author": "Developer Dave",
        "timestamp": "2026-03-07T08:30:00Z",
        "text": "Privacy note: the specification expects user-linked auditability, but the current compliance direction discourages exposing directly identifiable personal details in raw logs. I need confirmation on whether administrators should read these records through a controlled lookup layer rather than from the stored log entries alone."
      }
    ]
  },
  {
    "ticket_id": "JIRA-REP-704",
    "summary": "Audit Log Integrity",
    "description": "Ensure audit entries remain protected against unauthorized change or removal, and that the storage approach supports the integrity guarantees defined in the reporting and audit specification.",
    "status": "Closed"
  },
  {
    "ticket_id": "JIRA-REP-705",
    "summary": "Report Export",
    "description": "Implement report export for supported output formats and ensure exported data remains faithful to the reporting view that generated it.",
    "status": "To Do"
  },
  {
    "ticket_id": "JIRA-REP-706",
    "summary": "Reporting Access Control",
    "description": "Restrict report and audit-log access to authorized users and ensure unauthorized actors cannot view or export protected reporting information.",
    "status": "Closed"
  }
]