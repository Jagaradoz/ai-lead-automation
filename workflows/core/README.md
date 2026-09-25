# Core Lead Intelligence Workflow

## Purpose

The **Core Lead Intelligence Workflow** is the central orchestration engine built in [n8n](https://n8n.io/). It operates independently of intake channels, consuming only **Canonical Lead** objects.

By decoupling the processing engine from lead capture platforms, new channels (Facebook, LINE, Web, Email) can be integrated without modifying the core qualification, scoring, or CRM logic.

---

## Architectural Pipeline

```text
Canonical Lead Payload (HTTP POST / Sub-Workflow Call)
  │
  ├──► 1. Schema Validation (JSON Schema Draft-07 check)
  │        └── Invalid? ──► Error Router / Dead-Letter Log
  │
  ├──► 2. Deduplication Check (CRM / Database lookup by email/phone)
  │        └── Match Found? ──► Merge with Existing Contact & Append Interaction
  │
  ├──► 3. AI Fact Extraction (OpenAI / LLM Structured Output)
  │        ├── Extracts: industry, service_requested, problem, budget, timeline, intent
  │        └── Low Confidence? ──► Set Flag for Human Review
  │
  ├──► 4. Deterministic Scoring Engine (Configurable Rule Execution)
  │        ├── Calculates: Service fit, budget fit, urgency, intent, authority
  │        └── Outputs: Total score (0-100), Priority tier (High/Med/Low/Disqualified), Explanations
  │
  ├──► 5. CRM Synchronization (HubSpot API)
  │        ├── Create/Update Contact
  │        ├── Create Deal (if Qualified)
  │        └── Write AI Summary & Score Explanations to Custom Properties
  │
  └──► 6. Action Dispatcher & Notifications
           ├── High Priority ──► Instant Slack Notification + Auto-assign Sales Rep
           ├── Low / Ambiguous ──► Queue for Human Review
           └── Disqualified / Spam ──► Archive silently
```

---

## Key Components & Nodes

1. **Webhook / Trigger Node**: Receives normalized lead JSON.
2. **Code Node (Validator)**: Validates required fields against `schemas/lead.schema.json`.
3. **AI Agent / LLM Structured Output Node**: Invokes the LLM with a strict JSON schema prompt to extract objective facts without subjective scoring.
4. **Code Node (Rule Engine)**: Executes deterministic business logic defined in `config/scoring.example.json`. Returns an explainable score breakdown.
5. **HubSpot Node**: Interacts with the CRM API using private app credentials.
6. **Notification Node**: Dispatches formatted markdown alerts to Slack/Teams/Email.

---

## Error Handling & Reliability Principles

- **Idempotency**: Every lead carries a unique `lead_id`. Repeated executions check for existing processing runs to avoid duplicate CRM entries or notifications.
- **Dead-Letter Queue (DLQ)**: Malformed payloads or API rate limits trigger an error catch branch, notifying operations without failing silently.
- **Graceful AI Degradation**: If the LLM provider experiences an outage or returns unparseable JSON, the pipeline falls back to rule-only heuristics and flags the lead for manual review.

---

## Implementation Status

- **Status**: [Completed - Milestone 0.1]
- **Artifacts**: Importable n8n workflow pipeline is available in [workflow.json](workflow.json). Includes schema validation, OpenAI fact extraction, deterministic scoring engine, priority router, HubSpot CRM sync, and Slack alert dispatcher.
