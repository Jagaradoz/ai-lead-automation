# Website Intake Adapter Workflow

## Purpose

The **Website Intake Adapter** serves as the initial channel-specific ingestion layer for website contact forms, landing pages, and quote request calculators.

It receives raw HTTP POST submissions from website frontends, cleanses the data, maps custom form field names into the canonical lead format, and invokes the **Core Lead Intelligence Workflow**.

---

## Data Flow

```text
Visitor Submits Form (Website Frontend)
  │
  ▼
HTTP POST to Webhook Endpoint (/webhook/leads/website)
  │
  ├──► 1. Rate Limiting & Spam Filter (Honeypot + IP check)
  │
  ├──► 2. Channel Normalization Adapter (Code Node)
  │        Maps raw fields (e.g. `work_email` -> `contact.email`)
  │        Assigns unique `lead_id` and UTC timestamp
  │
  ├──► 3. Structural Validation
  │        Verifies compliance with `schemas/lead.schema.json`
  │
  └──► 4. Forward to Core Workflow (Execute Workflow Node)
```

---

## Field Mapping Example

| Website Form Field | Canonical Lead Property | Transformation / Notes |
| :--- | :--- | :--- |
| `fields.full_name` | `contact.name` | Trimmed string |
| `fields.work_email` | `contact.email` | Lowercased, email regex validated |
| `fields.contact_number` | `contact.phone` | Stripped of spaces and hyphens |
| `fields.company_title` | `company.name` | Default `null` if empty string |
| `fields.inquiry_text` | `message` | Primary body for AI extraction |
| `tracking.source` | `metadata.utm_source` | Preservation of attribution data |
| `submission_id` | `external_id` | Foreign identifier from form system |

---

## Security & Resilience

- **Honeypot Check**: Invisible form fields checked to drop dumb bot submissions before triggering LLM calls.
- **CORS / Secret Header**: Shared webhook secret verified in request headers.
- **Immediate HTTP 202 Response**: Acknowledges receipt immediately so visitor browser does not experience lag during downstream LLM analysis.

---

## Implementation Status

- **Status**: [Planned - Milestone 0.3]
- **Target Integrations**: Webflow forms, WordPress Elementor/CF7, custom Next.js/HTML lead forms.
