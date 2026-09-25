# Project Goals & Portfolio Vision

## 1. What This Project Demonstrates

**AI Lead Automation** is a portfolio project engineered to demonstrate practical, production-minded automation architecture for modern B2B/B2C sales pipelines.

Many early AI projects follow a superficial pattern:
> *"Form submission → Pass raw prompt to ChatGPT → Write output to CRM"*

While functionally appealing in a demo video, this approach fails in real commercial operations because:
- AI outputs are non-deterministic and hallucination-prone.
- Lead scoring based on LLM whims cannot be audited or explained to sales executives.
- Disparate acquisition channels (Facebook, LINE, web forms, email) produce messy, fragmented data schemas.
- There is no deduplication, error recovery, evaluation harness, or human oversight.

This repository demonstrates the engineering rigor required to build a **reliable, auditable, multi-channel lead intelligence engine**.

---

## 2. The Business Problem

Modern service and technology businesses capture enquiries from multiple marketing and communication channels simultaneously:

1. **Website contact and demo request forms**
2. **Meta (Facebook & Instagram) Lead Ads**
3. **Facebook Page direct messages**
4. **LINE Official Account chats (crucial in Southeast Asia & Japan)**
5. **Direct sales emails**

Without systematic automation, organizations suffer from severe operational friction:

- **Slow Response Times**: Research consistently shows that contacting a prospect within 5 minutes yields a 21x higher qualification rate compared to 30 minutes. Manual triage often takes hours or days.
- **Lost & Fragmented Leads**: Enquiries landing on social apps (like LINE or Facebook) remain trapped in individual chat threads and never reach the central CRM.
- **Inconsistent Qualification**: Sales representatives apply varying standards to evaluate prospect viability, leading to subjective lead categorization.
- **Manual Data Entry Burden**: Reps spend hours copying text from chats and emails into CRM records rather than engaging customers.
- **Duplicate Customer Records**: Prospects submitting multiple inquiries across channels create fragmented CRM profiles, confusing sales teams.
- **Poor Prioritization**: High-value enterprise prospects sit in the queue behind tire-kickers and promotional spam.
- **Forgotten Follow-ups**: Inquiries that do not convert immediately are forgotten without automated nurture triggers.

---

## 3. The Technical Solution

**AI Lead Automation** solves these challenges through a modular, channel-independent automation pipeline:

1. **Unified Intake**: Channel adapters translate disparate payloads into an identical **Canonical Lead Model**.
2. **AI Fact Extraction**: LLMs are employed strictly for what they do best: parsing messy, multilingual human text into structured factual attributes.
3. **Explainable Deterministic Scoring**: Business rules—not opaque AI models—calculate points, evaluate thresholds, and assign priority tiers. Every score includes a human-readable justification.
4. **Automated CRM Sync**: HubSpot contacts and deals are created or updated automatically with structured metadata.
5. **Smart Routing & Alerts**: Urgent, high-value leads trigger instant Slack alerts and round-robin rep assignments; ambiguous or edge cases route cleanly to human review.
6. **Continuous Evaluation**: A test harness benchmarks extraction accuracy and score stability against ground-truth datasets.

---

## 4. Key Engineering Competencies Highlighted

| Competency | Demonstrated In Repository |
| :--- | :--- |
| **Workflow Orchestration** | Designing resilient, decoupled pipelines in n8n (`workflows/`) |
| **Domain Data Modeling** | Defining strict JSON Schemas for canonical entities (`schemas/`) |
| **Structured AI Outputs** | Constraining LLMs to deterministic JSON schemas without hallucinations (`schemas/lead-analysis.schema.json`) |
| **Explainable Business Logic** | Transparent, configurable scoring models separated from AI prompts (`config/scoring.example.json`) |
| **Multi-Channel Integration** | Architectural design for Facebook Lead Ads, LINE Messaging API, and Webhook protocols (`workflows/`) |
| **Human-in-the-Loop Governance** | Defined boundary conditions for automation vs. human intervention (`docs/human-handoff.md`) |
| **Automated AI Evaluation** | Test suites and ground-truth validation datasets (`evaluation/`) |
| **Operational Reliability** | Dead-letter queues, idempotent handling, and graceful degradation principles (`docs/architecture.md`) |

---

## 5. Current Scope vs. Long-Term Vision

This repository is an evolving demonstration project. It is **not** a finished SaaS product. 

Development follows a staged roadmap:
- **Current Milestone**: Repository scaffolding, domain architecture, schema definitions, sample evaluation datasets, and configuration blueprints.
- **Immediate Next Milestone (0.1)**: Core n8n intelligence pipeline (Test JSON → Normalization → AI Extraction → Deterministic Score).
- **Subsequent Milestones**: HubSpot integration, real web forms, Slack alerts, Facebook Lead Ads, deduplication, and conversational LINE qualification.
