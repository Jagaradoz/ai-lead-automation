# Staged Product Roadmap

This document outlines the phased development roadmap for **AI Lead Automation**.

To maintain absolute clarity regarding project status, milestones are labeled using standard lifecycle badges:
- `[Current]` — Actively being specified, scaffolded, or implemented.
- `[Planned]` — Next in sequence; architectural dependencies defined.
- `[Future]` — Later horizon; scheduled after core milestones achieve stability.
- `[Experimental]` — Exploration or spike for emerging capabilities.

---

## Phase 0: Foundations & Core Intelligence (Milestones 0.1 – 0.6)

### Milestone 0.0 — Scaffolding & Architecture `[Current]`
- [x] Repository organization and directory structure.
- [x] Canonical Lead schema definition (`schemas/lead.schema.json`).
- [x] AI analysis extraction schema (`schemas/lead-analysis.schema.json`).
- [x] Deterministic scoring schema (`schemas/lead-score.schema.json`).
- [x] Comprehensive architectural and technical documentation.
- [x] 10 diverse initial sample evaluation leads (`evaluation/datasets/sample-leads.json`).
- [x] Declarative scoring rules configuration (`config/scoring.example.json`).

### Milestone 0.1 — Lead Intelligence Core `[Planned]`
- [ ] Implement core n8n workflow pipeline (`workflows/core/`).
- [ ] End-to-end execution path:
  `Test JSON Payload ──► Webhook ──► Normalize ──► Validate ──► AI Fact Extraction ──► Deterministic Rule Engine ──► Structured Output JSON`
- [ ] OpenAI Structured Outputs JSON schema integration.
- [ ] Configurable rule execution node with point-by-point explanations.

### Milestone 0.2 — CRM Integration (HubSpot) `[Planned]`
- [ ] HubSpot Private App API configuration.
- [ ] Contact creation and update logic (mapping `contact.email` and `contact.phone`).
- [ ] Deal creation for qualified leads with pipeline stage assignments.
- [ ] Custom CRM properties: `lead_score_total`, `lead_score_priority`, `ai_lead_summary`, `ai_extracted_budget`, `score_audit_trail`.

### Milestone 0.3 — Website Intake Channel `[Planned]`
- [ ] Website intake adapter workflow (`workflows/website/`).
- [ ] Public webhook endpoint with honeypot spam protection.
- [ ] Mapping raw form fields into Canonical Lead representation.
- [ ] Interactive demo web form for live test submissions.

### Milestone 0.4 — Smart Alerts & Notifications `[Planned]`
- [ ] High-priority lead Slack / Teams alert card dispatcher.
- [ ] Direct deep link into HubSpot record.
- [ ] Fallback email notifications for unassigned leads.

### Milestone 0.5 — Deduplication & Identity Resolution `[Planned]`
- [ ] Identity lookup before record creation (query HubSpot by email, phone, or company domain).
- [ ] Existing contact resolution: append new inquiry activity to existing contact thread instead of spawning duplicates.
- [ ] Existing customer detection (suppress marketing outreach if prospect is an existing active client).

### Milestone 0.6 — Automated Evaluation Harness `[Planned]`
- [ ] Automated evaluation runner CLI script (`scripts/run-evaluation`).
- [ ] Ground-truth oracle assertions in `evaluation/expected/`.
- [ ] Automated benchmark report generation (`evaluation/reports/`) tracking extraction precision, recall, and scoring drift.

---

## Phase 1: Production Polish & Channel Expansion (Milestones 1.0 – 1.3)

### Milestone 1.0 — Portfolio-Ready Vertical Slice `[Planned]`
- [ ] Fully functional end-to-end demo: Live Web Form → Core Pipeline → AI Extraction → Rule Scoring → HubSpot CRM → Slack Alert.
- [ ] Screencast walkthrough, architectural diagrams, and documented results.

### Milestone 1.1 — Facebook Lead Ads Integration `[Future]`
- [ ] Facebook webhook challenge verification handshake.
- [ ] Meta Graph API leadgen payload retrieval.
- [ ] Facebook adapter workflow (`workflows/facebook/`) mapping Meta field arrays to Canonical Lead format.
- [ ] Zero alterations required in core workflow engine.

### Milestone 1.2 — Automated Follow-Up Sequences `[Future]`
- [ ] State-based email/SMS nurture sequences triggered by lead priority.
- [ ] Follow-up cancellation if prospect books meeting or replies.
- [ ] Stalled lead re-engagement reminders.

### Milestone 1.3 — Monitoring & Operational Observability `[Future]`
- [ ] n8n execution telemetry tracking (processing latency, LLM token usage, failure rates).
- [ ] Scoring distribution dashboards (percentage High / Medium / Low / Disqualified).
- [ ] Alerting on third-party API rate limits (HubSpot, OpenAI, Meta).

---

## Phase 2: Advanced Conversational Channels (Milestone 2.0)

### Milestone 2.0 — LINE OA Conversational Qualification `[Future]`
- [ ] LINE Official Account Messaging API integration (`workflows/line/`).
- [ ] Webhook HMAC-SHA256 signature verification.
- [ ] Multi-turn conversational qualification agent:
  - Answers initial business FAQs.
  - Dynamically asks follow-up questions to gather missing fields (budget, timeline, specific requirements).
  - Automatically compiles chat transcript into a Canonical Lead once qualification thresholds are achieved.
- [ ] Submits synthesized lead to core pipeline seamlessly.
