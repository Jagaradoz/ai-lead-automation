# System Architecture & Technical Design

## 1. Executive Summary

**AI Lead Automation** is engineered as a modular, channel-agnostic lead intelligence pipeline. Rather than coupling specific web forms or advertising platforms directly to a CRM or LLM endpoint, the system enforces a strict separation of concerns:

- **Channel Adapters**: Ingest diverse, non-standard payloads and translate them into a single canonical representation.
- **Data Normalization & Validation**: Guarantees schema adherence and data hygiene before downstream consumption.
- **AI-Powered Fact Extraction**: Leverages Large Language Models exclusively for interpretation of unstructured, multilingual customer text into structured data.
- **Deterministic Business Rules**: Calculates transparent, explainable lead scores without subjective AI opacity.
- **CRM & Follow-up Orchestration**: Updates contact and deal records, dispatches notifications, and triggers human-in-the-loop workflows when necessary.

---

## 2. High-Level Architecture Diagram

```text
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         INBOUND CHANNELS & SOURCES                          │
  │   Website Forms  │  Facebook Lead Ads  │  LINE Official Account  │  Email   │
  └────────┬───────────────────┬───────────────────────┬───────────────────┬────┘
           │                   │                       │                   │
           ▼                   ▼                       ▼                   ▼
  ┌─────────────────┐ ┌─────────────────┐     ┌─────────────────┐ ┌─────────────┐
  │ Website Adapter │ │Facebook Adapter │     │  LINE Adapter   │ │Email Adapter│
  └────────┬────────┘ └────────┬────────┘     └────────┬────────┘ └──────┬──────┘
           │                   │                       │                 │
           └───────────────────┼───────────────────────┴─────────────────┘
                               ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                     CANONICAL LEAD DATA MODEL & INTAKE                      │
  │                  Structured, validated, channel-agnostic JSON               │
  └────────────────────────────────────┬────────────────────────────────────────┘
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                            DATA HYGIENE LAYER                               │
  │   • Schema Validation (JSON Schema Draft-07)                                │
  │   • Deduplication & Identity Resolution (Email / Phone / Tax ID Lookup)    │
  │   • Sanitization & PII Handling                                             │
  └────────────────────────────────────┬────────────────────────────────────────┘
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                       AI FACT EXTRACTION LAYER (LLM)                        │
  │   • Extract: Industry, Requested Service, Stated Problem                    │
  │   • Extract: Budget Amount & Currency, Expected Timeline, Urgency           │
  │   • Language Detection (TH/EN) & Missing Information Identification         │
  │   • Self-Assessed Confidence Score (No Final Scoring Decisions!)            │
  └────────────────────────────────────┬────────────────────────────────────────┘
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                 DETERMINISTIC BUSINESS QUALIFICATION & SCORING              │
  │   • Service Fit (0-25 pts)        • Budget Alignment (0-20 pts)             │
  │   • Implementation Urgency (0-20) • Purchase Intent (0-20 pts)              │
  │   • Authority & Fit (0-15 pts)    • Point-by-point Explainability Log       │
  │   • Assign Priority Tier: High / Medium / Low / Disqualified                │
  └────────────────────────────────────┬────────────────────────────────────────┘
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                     CRM & RECORD MANAGEMENT (HubSpot)                       │
  │   • Upsert Contact Record & Associate Company                               │
  │   • Create/Update Qualified Deal with Pipeline Stage                        │
  │   • Store AI Summary, Extracted Facts, and Score Audit Log in Properties    │
  └────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                  ┌────────────────────┴────────────────────┐
                  ▼                                         ▼
  ┌───────────────────────────────┐         ┌───────────────────────────────────┐
  │    AUTOMATED DISPATCH TIER    │         │      HUMAN-IN-THE-LOOP TIER       │
  │ • High Priority: Slack Alert  │         │ • Flagged: Low AI confidence      │
  │ • Sales Rep Round-Robin Assign│         │ • High-Value Deal Review (>300k)  │
  │ • Automated Calendar Booking  │         │ • Out-of-Scope / Custom Scope     │
  └───────────────┬───────────────┘         └─────────────────┬─────────────────┘
                  │                                           │
                  └─────────────────────┬─────────────────────┘
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         CONVERSION & FEEDBACK LOOP                          │
  │   • Deal Progression Tracking (Won / Lost)                                  │
  │   • Feedback on AI Extraction Accuracy                                      │
  │   • Continual Evaluation Harness Benchmarking                               │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Architectural Principles

### 3.1. The Channel-Independent Core
The core processing system does not know—and does not care—whether a lead originated from a Facebook instant form, a LINE message, or a custom web app. 
- All source-specific logic (e.g., verifying Facebook webhook signatures, querying Meta Graph API for leadgen field arrays, decoding LINE webhook payloads) is isolated in **Channel Adapters**.
- The core pipeline accepts only instances of the **Canonical Lead Model** defined in `schemas/lead.schema.json`.

### 3.2. Strict Separation: AI Interpretation vs. Business Scoring
A widespread flaw in prototype automation is asking an LLM to "score this lead from 1 to 100". This introduces non-deterministic hallucinations, drift across model versions, and a total lack of explainability for sales representatives.
- **AI's Role**: Unstructured data interpretation. The LLM translates ambiguous human text into objective attributes (e.g., `"service_requested": "LINE AI customer service"`, `"budget": {"amount": 80000, "currency": "THB"}`).
- **Rule Engine's Role**: Deterministic business calculations. A declarative ruleset (`config/scoring.example.json`) awards points based on those extracted attributes. If a lead receives an 85, a sales manager can audit exactly why: 25 pts for service fit, 20 for budget, 20 for urgency, 20 for intent.

### 3.3. Human-in-the-Loop Governance
Automation should amplify sales velocity, not replace human judgment.
- Clear criteria trigger human intervention (e.g., model confidence < 0.65, budget >= 300,000 THB, conflicting requirements, detected spam).
- The system automatically compiles the context, pre-fills CRM properties, and notifies the account team with a suggested review action.

### 3.4. Deduplication & Historical Context
Before creating duplicate records in HubSpot or dispatching alerts, leads undergo identity resolution. If an email or phone number matches an existing customer or active opportunity, the interaction is appended to the existing thread rather than spawning a duplicate lead.

---

## 4. Pipeline Execution Stages

| Stage | Responsibility | Primary Technology |
| :--- | :--- | :--- |
| **1. Intake & Adaptation** | Ingest webhook; authenticate payload; map raw fields | n8n Webhook / Channel Adapters |
| **2. Normalization & Validation** | Validate against JSON Schema; sanitize inputs | n8n Code Node (JavaScript / JSON Schema) |
| **3. Deduplication** | Search existing contacts by email/phone; resolve IDs | HubSpot API / PostgreSQL |
| **4. AI Extraction** | Convert messy text into structured factual attributes | OpenAI API (Structured Outputs) |
| **5. Lead Scoring** | Compute point breakdown and assign priority bracket | Rule Engine (n8n Code Node / Config) |
| **6. CRM Sync** | Create/Update contact, deal, and custom properties | HubSpot API Integration |
| **7. Routing & Handoff** | Send Slack notification; route lead; trigger review queue | Slack API / Internal Email Alerts |

---

## 5. Security & Privacy Considerations

- **Zero Hardcoded Credentials**: All tokens and secrets reside in environment variables.
- **PII Handling**: Only required contact information is stored. Messages are sanitized for prompt injection protection before being sent to LLM endpoints.
- **Webhook Authentication**: Verification tokens, HMAC-SHA256 signatures, and IP whitelisting protect webhook ingestion endpoints.
