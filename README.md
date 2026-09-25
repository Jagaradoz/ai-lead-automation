# AI Lead Automation

[![Status: Early Development](https://img.shields.io/badge/Status-Early%20Development%20%2F%20Infrastructure%20Phase-blue.svg)](#current-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture: Channel--Independent](https://img.shields.io/badge/Architecture-Channel--Independent-orange.svg)](docs/architecture.md)

> **Portfolio Project**: A demonstration of multi-channel lead intake, AI-assisted factual extraction, explainable deterministic lead scoring, and automated CRM orchestration.

---

## 1. What This Project Is

**AI Lead Automation** is an architectural portfolio project designed to demonstrate how modern AI and workflow automation solve enterprise lead management bottlenecks.

The central concept is simple yet powerful:

> **Receive leads from multiple channels, normalize them into a single canonical format, analyze them with AI to extract structured facts, qualify and score them using transparent, explainable business rules, store them in a CRM, and automate appropriate sales actions.**

This project is built to showcase thoughtful automation architecture rather than a superficial "ChatGPT + Zapier" demo. It enforces clean separation of concerns, auditable decision-making, and robust engineering hygiene.

---

## 2. The Problem

Businesses generating customer demand across diverse channels (website forms, Meta ads, messaging apps, and email) frequently face severe operational friction:

- **Slow Response Times**: Leads drop cold when sales teams take hours or days to respond.
- **Lost & Trapped Leads**: Inquiries on messaging platforms (e.g., LINE, WhatsApp) remain trapped in silos, never reaching the CRM.
- **Inconsistent Qualification**: Different sales reps apply subjective, inconsistent criteria to evaluate prospects.
- **Manual Data Entry**: Reps waste valuable selling hours manually copying and pasting customer notes into CRM records.
- **Duplicate Records**: The same customer submitting multiple inquiries across channels creates fragmented profiles.
- **Forgotten Follow-ups**: Inactive or stalled leads slip through the cracks without automated follow-up triggers.
- **Poor Prioritization**: High-value enterprise prospects sit in the same queue behind tire-kickers and commercial spam.

---

## 3. The Proposed Solution

This project automates the entire lead journey from initial contact to CRM synchronization:

1. **Multi-Channel Adapters**: Ingest inquiries from website forms, Facebook Lead Ads, LINE Official Account, and emails into an identical internal representation.
2. **Canonical Normalization**: Standardizes data schema before any AI or business processing occurs.
3. **AI Fact Extraction**: Employs LLMs strictly to parse unstructured natural language and extract objective facts (industry, service requested, budget, timeline, intent).
4. **Deterministic Scoring**: Calculates transparent, point-by-point scores using configurable business rules—never opaque AI score guesses.
5. **Automated CRM Sync**: Creates/updates HubSpot contacts, associates deals, and saves full audit logs in custom properties.
6. **Smart Routing & Human-in-the-Loop**: Dispatches instant alerts for high-priority leads, while safely flagging ambiguous or enterprise deals for manual human review.

---

## 4. System Architecture

```text
Lead Sources (Website, Facebook Ads, LINE OA, Email)
       │
       ▼
Channel Adapters (Transform source payloads into common schema)
       │
       ▼
Canonical Lead Model (Validated against JSON Schema)
       │
       ▼
Validation & Deduplication Layer
       │
       ▼
AI Fact Extraction Layer (LLM extracts facts, industry, budget, timeline)
       │
       ▼
Deterministic Business Qualification & Scoring Engine (0 - 100 pts)
       │
       ▼
CRM Synchronization (HubSpot Contacts, Deals, Custom Properties)
       │
       ▼
Action Dispatcher & Human-in-the-Loop Governance
       ├── High Priority ──► Instant Slack Alert & Sales Rep Assignment
       ├── Uncertain / VIP ──► Flagged for Human Review Queue
       └── Disqualified ──► Silent Archive / Nurture Campaign
```

---

## 5. Current Status & Milestone

```text
Status: Early development / infrastructure phase
Current Milestone: Milestone 0.0 — Scaffolding & Lead Domain Architecture
```

> [!NOTE]
> This is an evolving portfolio demonstration project. It is **not** currently presented as a finished production SaaS product. The focus of this milestone is establishing clean architecture, domain schemas, baseline evaluation datasets, and transparent documentation.

---

## 6. Core Design Principles

- **Channel-Independent Core**: The processing engine consumes only canonical leads. Ingestion channels can be added or modified without changing core qualification logic.
- **AI for Interpretation, Rules for Decisions**: AI extracts facts from messy language; deterministic, auditable rules calculate scores.
- **Explainability First**: Every lead score contains an itemized breakdown. Sales reps always understand *why* a lead received its priority.
- **Human-in-the-Loop**: High-value opportunities, low-confidence extractions, or custom requests cleanly escalate to humans.
- **Testability & Evaluation**: AI outputs and rule calculations are systematically evaluated against ground-truth datasets.
- **Incremental Staged Growth**: Built in clear vertical slices—keeping early stages simple while preparing for multi-channel expansion.
- **Reliability Before Complexity**: Enforces schema validation, idempotency, and dead-letter handling before adding complex features.

---

## 7. Technology Direction

To maintain absolute transparency, the table below distinguishes between **currently utilized** technologies and **planned** implementation tools:

| Area | Current Milestone (0.0) | Planned / Future Milestones |
| :--- | :--- | :--- |
| **Workflow Orchestration** | Architectural specifications | **n8n** (self-hosted / cloud) |
| **Data Contracts** | **JSON Schema Draft-07** | Automated runtime validator nodes |
| **Custom Code / Scripts** | Standard JSON & Markdown docs | **Node.js / TypeScript** or Python scripts |
| **AI Extraction Provider** | Schema design (`lead-analysis`) | **OpenAI API** (`gpt-4o-mini` Structured Outputs) |
| **CRM Platform** | Schema mappings | **HubSpot CRM** (Private App API) |
| **Acquisition Channels** | Sample datasets | **Website Webhooks**, **Meta Graph API**, **LINE Messaging API** |
| **Persistence / Memory** | Git version control | **PostgreSQL / Supabase** (for identity deduplication) |

---

## 8. Staged Roadmap

| Version | Milestone | Description | Status |
| :---: | :--- | :--- | :---: |
| **0.0** | **Scaffolding & Architecture** | Repository structure, Canonical Lead schema, AI schema, scoring rules config, 10 sample evaluation leads, system docs. | `[Current]` |
| **0.1** | **Lead Intelligence Core** | End-to-end n8n workflow: Test Lead → Webhook → Normalize → Validate → AI Extraction → Rule Scoring → Result. | `[Planned]` |
| **0.2** | **CRM Synchronization** | HubSpot contacts, deals, custom properties for AI summaries and score audit logs. | `[Planned]` |
| **0.3** | **Website Intake Channel** | Webhook adapter for landing page contact form submissions. | `[Planned]` |
| **0.4** | **Smart Notifications** | Slack / Teams notification cards for high-priority leads with direct HubSpot links. | `[Planned]` |
| **0.5** | **Deduplication Engine** | Identity matching by email/phone to merge inquiries and prevent duplicate records. | `[Planned]` |
| **0.6** | **Evaluation Suite** | Automated benchmark test harness asserting extraction accuracy and score stability. | `[Planned]` |
| **1.0** | **Portfolio-Ready Vertical Slice** | Polished, documented end-to-end web lead qualification flow. | `[Planned]` |
| **1.1** | **Facebook Lead Ads** | Meta Graph API leadgen adapter feeding the unchanged core engine. | `[Future]` |
| **1.2** | **Follow-up Automation** | Automated nurture triggers and stalled lead re-engagement sequences. | `[Future]` |
| **1.3** | **Observability & Monitoring** | Telemetry tracking for workflow execution, API latencies, and score distributions. | `[Future]` |
| **2.0** | **LINE OA Conversational Qualification** | Conversational agent on LINE OA gathering missing qualification facts before generating canonical leads. | `[Future]` |

---

## 9. Repository Structure

```text
ai-lead-automation/
├── README.md                           # Main portfolio overview and architecture
├── LICENSE                             # MIT License
├── .gitignore                          # Git hygiene for Node, Python, and secrets
├── .env.example                        # Template for required environment variables
│
├── docs/                               # Comprehensive architectural documentation
│   ├── architecture.md                 # Deep-dive pipeline design & data flow
│   ├── project-goals.md                # Business problems, motivations, & competencies
│   ├── lead-model.md                   # Canonical Lead Model specification
│   ├── ai-analysis.md                  # Role of AI in fact extraction vs. scoring
│   ├── lead-scoring.md                 # Deterministic scoring rules & 7 dimensions
│   ├── human-handoff.md                # Human-in-the-loop philosophy & escalation rules
│   ├── evaluation-strategy.md          # Benchmark test strategy & quality metrics
│   └── roadmap.md                      # Phased roadmap from v0.0 to v2.0
│
├── schemas/                            # JSON Schema Draft-07 specifications
│   ├── lead.schema.json                # Canonical Lead data contract
│   ├── lead-analysis.schema.json       # AI structured fact extraction schema
│   └── lead-score.schema.json          # Deterministic score & audit log schema
│
├── config/                             # Business configuration
│   └── scoring.example.json            # Declarative scoring weights, rules, & thresholds
│
├── examples/                           # Concrete JSON fixtures illustrating pipeline lifecycle
│   ├── incoming-lead.json              # 1. Raw unstructured website form payload
│   ├── normalized-lead.json            # 2. Transformed Canonical Lead object
│   ├── ai-analysis.json                # 3. AI structured fact extraction output
│   └── scored-lead.json                # 4. Final scored lead with point explainability
│
├── evaluation/                         # Evaluation & quality assurance harness
│   ├── datasets/
│   │   └── sample-leads.json           # 10 realistic, diverse evaluation leads
│   ├── expected/
│   │   └── README.md                   # Ground-truth oracle assertion specifications
│   └── reports/
│       └── .gitkeep                    # Target directory for automated test runs
│
├── workflows/                          # n8n workflow blueprints & channel adapters
│   ├── core/                           # Core Lead Intelligence Workflow
│   │   └── README.md
│   ├── website/                        # Website Intake Adapter
│   │   └── README.md
│   ├── facebook/                       # Facebook Lead Ads Adapter
│   │   └── README.md
│   └── line/                           # LINE OA Conversational Qualification Adapter
│       └── README.md
│
└── scripts/                            # Planned developer utilities & runners
    └── README.md                       # Validation and evaluation CLI tools
```

---

## 10. Sample Lead Walkthrough

To understand how data flows through the system, inspect the step-by-step example files in `examples/`:

1. [`incoming-lead.json`](examples/incoming-lead.json) — Raw website form submission with custom field names.
2. [`normalized-lead.json`](examples/normalized-lead.json) — Clean, validated Canonical Lead representation.
3. [`ai-analysis.json`](examples/ai-analysis.json) — Structured factual attributes extracted by AI (budget, timeline, service, intent).
4. [`scored-lead.json`](examples/scored-lead.json) — Transparent lead score (90/100, High Priority) with complete itemized explanations.

---

## 11. Getting Started & Verification

```bash
# Clone the repository
git clone https://github.com/your-username/ai-lead-automation.git
cd ai-lead-automation

# Copy environment configuration
cp .env.example .env

# Explore schemas and sample leads
cat schemas/lead.schema.json
cat evaluation/datasets/sample-leads.json
```

---

## 12. License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
