[
  {
    "ticket_id": "JIRA-Auth-101",
    "summary": "Registration - Create account with mandatory fields",
    "description": "Implement user registration functionality. The system shall require first name, last name, phone number, email address, and password. All fields are mandatory and must be validated before submission. \n\nAdditionally, the form must include:\n1. A single 'Terms and Conditions' checkbox that represents acceptance of both the Terms of Service and Privacy Policy.\n2. A 'Submit' button that remains disabled until all mandatory fields are filled and the legal consent checkbox is checked.",
    "comments": [
      {
        "author": "Tool Master Lesly",
        "timestamp": "2026-02-15T09:00:00Z",
        "text": "Name fields must be limited to 50 characters due to database constraints."
      },
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-15T09:09:00Z",
        "text": "Please clarify if leading/trailing spaces should be trimmed and whether hyphens/accents are allowed in names."
      },
      {
        "author": "Developer Dave",
        "timestamp": "2026-02-15T14:38:00Z",
        "text": "Leading/trailing spaces will be trimmed. Hyphens and accents are allowed."
      },
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-16T07:16:00Z",
        "text": "Will first and last names be entered in separate fields? Will we support a middle name?"
      },
      {
        "author": "PM Peter",
        "timestamp": "2026-02-16T12:58:00Z",
        "text": "First and last name are separate fields. Middle name is optional."
      },
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-16T16:43:00Z",
        "text": "Do we support double surnames or special characters (e.g. apostrophe in O'Connor)?"
      }
    ],
	"attachments": ["EMAIL_LEGAL_GDPR_Compliance.txt"]
  },
  {
    "ticket_id": "JIRA-Auth-102",
    "summary": "Registration - Email uniqueness validation",
    "description": "Validate that the email address provided during registration is unique and not already associated with an existing account. Uniqueness validation shall be case-insensitive.",
    "comments": [
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-15T08:22:00Z",
        "text": "Should email addresses be case-sensitive when checking for uniqueness? (e.g. Test@t.com = test@t.com?)"
      }
    ]
  },
{
  "ticket_id": "JIRA-Auth-103",
  "summary": "Registration - Phone number validation and normalization",
  "description": "Validate phone number format during registration and store it in normalized E.164 format. Reject invalid formats and normalize acceptable inputs.",
  "comments": [
    {
      "author": "QA Engineer Marta",
      "timestamp": "2026-02-15T10:22:00Z",
      "text": "Please confirm whether we accept spaces, parentheses, and dashes in phone number input (e.g., +36 (30) 123-4567) and normalize it. Also, should the email address format be validated during registration?"
    },
    {
      "author": "Developer Dave",
      "timestamp": "2026-02-15T11:05:00Z",
      "text": "Yes, we will accept common separators and normalize phone numbers to E.164 format."
    },
    {
      "author": "Backend Engineer Tomas",
      "timestamp": "2026-02-15T11:42:00Z",
      "text": "Yes, email format must be validated. The email must follow standard format: local-part@domain. The local part may contain letters, numbers, dots, hyphens, and underscores. The domain must contain at least one dot and valid domain name characters. Example of valid format: user.name@example.com"
    }
  ]
},
  {
    "ticket_id": "JIRA-Auth-104",
    "summary": "Registration - Create Pending account after successful submission",
    "description": "Upon successful submission of the registration form, the system shall create a new user account with status set to Pending.",
    "comments": []
  },
  {
    "ticket_id": "JIRA-Auth-105",
    "summary": "Activation - Send confirmation email with activation link",
    "description": "After successful registration, the system shall send an account activation email to the provided email address. The email shall contain a unique activation link.",
    "comments": [
      {
        "author": "Security Engineer Viktor",
        "timestamp": "2026-02-15T13:40:00Z",
        "text": "Activation tokens must be cryptographically secure and time-limited. If stored, store hashed tokens."
      }
    ]
  },
  {
    "ticket_id": "JIRA-Auth-106",
    "summary": "Activation - Validate activation link and activate account",
    "description": "Implement activation flow. The system shall validate the activation link/token. If valid, the system shall update the account status from Pending to Active and allow platform access.",
    "comments": []
  },
  {
    "ticket_id": "JIRA-Auth-107",
    "summary": "Activation - Reject invalid or expired tokens",
    "description": "The system shall reject activation requests that use invalid or expired activation tokens and show an appropriate error state.",
    "comments": []
  },
  {
  "ticket_id": "JIRA-Auth-108",
  "summary": "Registration - Security hardening: Prevent email enumeration",
  "description": "To prevent attackers from discovering registered users, the registration flow must use generic responses. \n\nRequirement:\nIf a user tries to register with an email address that is already in use, the system MUST NOT display an error message stating 'Email already exists'. \nInstead, it should display a generic message: 'If this email is valid, a message has been sent to it.'",
  "comments": [
    {
      "author": "Security Engineer Viktor",
      "timestamp": "2026-02-16T10:00:00Z",
      "text": "This is critical for OWA (OWASP) compliance. We cannot leak user existence through the registration form."
    }
  ]
},
  {
    "ticket_id": "JIRA-Auth-109",
    "summary": "Authentication gate - Block login for non-Active accounts",
    "description": "The system shall not allow authentication or platform access for accounts that are not in Active status (e.g., Pending, Suspended, Deleted).",
    "comments": []
  },
  {
    "ticket_id": "JIRA-Auth-110",
    "summary": "Activation token - Enforce single-use",
    "description": "Activation tokens shall be single-use. After a successful activation, the system shall invalidate the activation token immediately to prevent reuse.",
    "comments": []
  },
  {
    "ticket_id": "JIRA-Auth-111",
    "summary": "Support registration for multiple users sharing the same email address",
    "description": "In some use cases (e.g. family accounts or shared organizational email addresses), multiple users may attempt to register using the same email address. Instead of enforcing strict email uniqueness, we may allow multiple accountsto share the same email if another identifier (such as phone number) is unique. This would require adjusting the registration validation logic.",
    "comments": [
      {
        "author": "QA Engineer Marta",
        "timestamp": "2026-02-16T10:41:00Z",
        "text": "This contradicts the SRS requirement that email must be unique. Please confirm expected behavior."
      }
    ]
  },
  {
  "ticket_id": "JIRA-Auth-112",
  "summary": "Registration - Auto-cleanup for unactivated accounts and Data Retention",
  "description": "To comply with data minimization principles, the system shall automatically delete any user account that remains in 'Pending' status for more than 30 days. All associated personal data must be removed, except for minimal audit logs required by the retention policy.",
  "comments": [
    {
      "author": "PM Peter",
      "timestamp": "2026-02-16T12:05:00Z",
      "text": "This is an enhancement beyond the initial SRS but aligns with GDPR data minimization."
    },
    {
      "author": "QA Engineer Marta",
      "timestamp": "2026-02-16T13:45:00Z",
      "text": "Logic Gap: If we delete the account after 30 days, what happens to the activation link sent in CONF-AUTH-01 1.5? The link has no expiry in the docs. We need to ensure the link doesn't trigger a 500 error on a non-existent account."
    },
    {
      "author": "Security Engineer Viktor",
      "timestamp": "2026-02-17T10:10:00Z",
      "text": "Clarification Needed: When a user manually requests account deletion, should it be immediate, or do we provide a 14-day 'grace period' for recovery before the permanent wipe?"
    }
  ]
},
  {
    "ticket_id": "JIRA-Auth-113",
    "summary": "Registration - Password policy enforcement",
    "description": "Enforce password policy rules during registration and prevent weak passwords.",
    "comments": [
      {
        "author": "Security Engineer Viktor",
        "timestamp": "2026-02-16T13:12:00Z",
        "text": "Missing details: minimum length, complexity requirements, common password blacklist, and whether passphrases are allowed."
      }
    ],
    "attachments": ["EMAIL_CTO_Security_Update.txt"]
  },
{
  "ticket_id": "JIRA-Auth-114",
  "summary": "Allow registration without phone number",
  "description": "Some users are reluctant to provide their phone number during registration. Consider making the phone number optional in the registration form to reduce signup friction. If phone number is optional, the form validation logic and account model may need adjustments.",
  "comments": [
    {
      "author": "Security Engineer Viktor",
      "timestamp": "2026-02-18T06:12:00Z",
      "text": "Do we only accept Hungarian (+36) numbers, or international format as well?"
    },
    {
      "author": "Developer Dave",
      "timestamp": "2026-02-19T10:00:00Z",
      "text": "Logic Check: JIRA-Auth-101 states the 'Submit' button is disabled until ALL mandatory fields are filled. If I make the phone optional here, do I need to update the button logic in 101, or will it still wait for a phone number?"
    }
  ]
},
  {
  "ticket_id": "JIRA-Auth-115",
  "summary": "Registration - UX Improvement: Clear error messages",
  "description": "Our support team reports that users are confused by generic messages. We need to provide clear, actionable feedback during registration.\n\nRequirement:\nIf an email address is already registered, the system should clearly state: 'This email address is already registered. Please log in or reset your password.'",
  "comments": [
    {
      "author": "UX Writer Nora",
      "timestamp": "2026-02-17T09:30:00Z",
      "text": "Generic messages lead to high drop-off rates. Users think the system is broken if they don't get a specific reason for failure."
    }
  ]
},
{
  "ticket_id": "JIRA-Auth-116",
  "summary": "Initial login implementation without MFA",
  "description": "The first implementation of the login endpoint will support email and password authentication only. Multi-factor authentication (MFA) is part of the security roadmap, but will not be implemented in this sprint. Future iterations should extend the authentication flow to support a second factor when enabled.",
  "comments": [
    {
      "author": "Developer Dave",
      "timestamp": "2026-02-18T10:00:00Z",
      "text": "Login logic is ready. MFA is not part of this sprint, we only do password-based auth for now."
    },
    {
      "author": "QA Engineer Marta",
      "timestamp": "2026-02-18T11:30:00Z",
      "text": "Wait, CONF-AUTH-01 Section 9 says MFA is mandatory for platform access. If we launch without it, we violate the spec. Why is there no JIRA ticket for MFA setup?"
    }
  ]
}
]