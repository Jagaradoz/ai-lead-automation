# AI Lead Automation

[![Status: MVP Live](https://img.shields.io/badge/Status-MVP%20Live%20%2F%20Interactive%20Demo-emerald.svg)](#current-status)
[![Architecture: Channel--Independent](https://img.shields.io/badge/Architecture-Channel--Independent-orange.svg)](docs/architecture.md)
[![Tests: Passing](https://img.shields.io/badge/Tests-120%20Passing-brightgreen.svg)](tests/)

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
Status: Usable locally. Web inbox, configurable model, editable scoring rules.
Current Milestone: 0.3 website intake + 0.4 alerts (preview) + 0.6 evaluation harness
```

What works today:

- **Lead inbox**: every processed lead is stored (SQLite) with its score, status (new, contacted, qualified, won, lost, spam) and notes. Filter, search, sort, re-score and export to CSV.
- **Bring your own model**: pick Anthropic, OpenAI, OpenRouter, Groq, DeepSeek, Gemini, a local Ollama or LM Studio server, or any OpenAI-compatible endpoint in *Settings > Model*. With no model configured, a built-in rules engine extracts the facts instead, and every lead shows which engine analyzed it and why.
- **Your business, your rules**: *Settings > Business profile* holds the service catalog, target industries, budget tiers, currencies, timeline buckets, dimension weights, priority thresholds and review triggers. The model prompt and the scoring engine both read it, so nothing about the business is hardcoded.

> [!NOTE]
> Built for local or single-team use. Lead data has no login, so keep the server on your machine or team network. `ADMIN_TOKEN` locks the settings. See [Security notes](#security-notes).

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
│   └── business-profile.default.json   # Default service catalog, scoring weights, thresholds
│
├── web/                                # Build-free web app (inbox, lead detail, settings)
│   ├── index.html, styles.css
│   └── js/                             # ES modules: inbox, lead detail, new lead, settings
│
├── data/                               # Created at runtime, git-ignored
│   ├── settings.json                   # Model settings (includes your API key)
│   ├── business-profile.json           # Your edited business profile
│   └── leads.db                        # Lead inbox (SQLite)
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
└── scripts/                            # Python application code
    ├── serve_api.py                    # FastAPI app (mounts routers, serves web/)
    ├── api/                            # Lead and settings HTTP endpoints
    ├── llm/                            # Model providers + model settings store
    ├── ai_extractor.py                 # Model-or-rules fact extraction with visible fallback
    ├── rules_extractor.py              # Deterministic extraction (EN/TH budgets, timelines, intent)
    ├── scoring_engine.py               # Deterministic scoring driven by the business profile
    ├── business_profile.py             # Profile model, validation, persistence
    ├── lead_store.py                   # SQLite lead repository
    └── normalize.py                    # Channel adapters to the Canonical Lead
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

### 1. Install and run

```bash
pip install -r requirements.txt
python main.py
```
*(On Windows you can also run `.\run.bat`.)*

Open **http://localhost:8000**. Click **New lead**, paste an enquiry (or pick a sample), and choose **Analyze lead**. The lead appears in the inbox with an itemized score that shows the points and the reason for each part.

### 2. Connect a model

Open **Settings > Model**, choose a provider, enter the model name and API key, and click **Test connection**. A sample lead goes to the model, and the page shows whether it answered and how it read the lead. **Save** to use it for new leads.

| Provider | Base URL (pre-filled) | Key |
| :--- | :--- | :--- |
| Anthropic | `https://api.anthropic.com` | required |
| OpenAI, OpenRouter, Groq, DeepSeek, Gemini | pre-filled per provider | required |
| Ollama / LM Studio | `http://localhost:11434/v1`, `http://localhost:1234/v1` | not needed |
| Other OpenAI-compatible server | your URL | optional |

You can also configure the model in `.env` (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`). See [`.env.example`](.env.example). Settings saved in the app take precedence.

Choose what happens when the model fails. By default the lead falls back to the built-in rules and records the reason. Alternatively, the request can return an error and the lead isn't saved.

### 3. Describe your business

Open **Settings > Business profile** and replace the example agency with your own:

- **What you sell**: each service has a tier (core, adjacent, out of scope) and keywords. The model maps each lead to one of these services, and the tier decides the service-fit points.
- **Who you sell to**: target industries and company sizes, plus the job titles that count as decision makers.
- **Scoring**: the weight of each of the 7 dimensions (must total 100), budget tiers in your base currency, exchange rates, timeline buckets, and priority thresholds.

After you save, you can re-score the existing inbox with the new rules. Re-scoring doesn't call the model.

### 4. Send leads from other systems

```bash
curl -X POST http://localhost:8000/api/leads/process \
  -H "Content-Type: application/json" \
  -d '{"contact": {"name": "Pat", "email": "pat@example.com"}, "company": {"name": "Example Co"}, "message": "We need a LINE bot for bookings, budget 80k THB, within a month."}'
```

The endpoint accepts website form, LINE webhook, Facebook Lead Ads and canonical payloads. Full API docs are at `/docs`.

### 5. Dashboard, next steps and demo data

- **Dashboard** (`#/dashboard`): leads per day, priority mix, volume and win rate per channel, pipeline by status, median analysis time.
- **Next step** on every lead: owner, response target and a first reply drafted in the customer's language (Thai or English), asking only for details that are missing. Disqualified leads get no automatic reply.
- **Demo data**: fill the inbox with 24 realistic Thai/English leads spread over two weeks, run through the real pipeline and tagged *Demo*. Sales outcomes (won/lost) are simulated so the charts have data.

```bash
python -m scripts.seed_demo_leads            # built-in scenarios
python -m scripts.seed_demo_leads --llm 20   # plus 20 written by your configured model
python -m scripts.seed_demo_leads --clear    # remove demo leads only
```

### 6. Model page: evidence the scoring works

The **Model** page (`#/model`) shows two evaluations:

1. The message pipeline against 10 hand-labeled enquiries (extraction, priority, safety flags).
2. A conversion model trained on a real public dataset: [X Education lead scoring](https://www.kaggle.com/datasets/amritachatterjee09/lead-scoring-dataset), 9,240 leads with a converted/not-converted outcome. Logistic regression and gradient boosting are compared with a baseline that always guesses "no" on 2,310 held-out leads. The page shows ROC, confusion matrix, calibration, feature importance and lift. For example, the top 20% of scored leads convert at 82%, against 39% on average.

```bash
pip install -r requirements-ml.txt
python -m scripts.train_conversion_model     # downloads the CSV to data/, writes evaluation/models/conversion-model.json
```

### 7. Run the quality suites

```bash
python main.py --test   # unit + API tests (includes the 10-lead benchmark)
python main.py --val    # schemas, examples, datasets, default business profile
python main.py --eval   # ground-truth benchmark report (rules engine)
```

### Security notes

- API keys are stored in plain text in `data/settings.json` on the server and are never returned to the browser. Keep `data/` private (it is git-ignored).
- The server binds to `127.0.0.1` and only answers to the host names in `ALLOWED_HOSTS`. Writes from other websites are rejected.
- `ADMIN_TOKEN` protects settings only: changing the model or key, testing a connection, listing models and editing the business profile. **Lead data has no login.** Anyone who can reach the server can read and export leads, so don't expose it beyond your machine or team network without a login in front of it (for example, a reverse proxy with authentication).
- A saved API key is only sent to the server it was saved for. If you change the base URL, you must enter the key again. Model servers on link-local or cloud-metadata addresses are refused.
- Lead text is untrusted. The UI renders it as text only, a Content-Security-Policy is set, and the model prompt tells the model to ignore instructions inside the lead.

---

## 12. Copyright & Intellectual Property

Copyright &copy; 2026 Jagaradoz. All rights reserved.
