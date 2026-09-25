# AI Lead Analysis & Structured Fact Extraction

## 1. Role & Boundary of AI

In the **AI Lead Automation** architecture, the Large Language Model (LLM) is strictly scoped to **information extraction and semantic interpretation**.

```text
Unstructured, Ambiguous Customer Text
(Multilingual, colloquial, typos, implicit needs)
                    │
                    ▼
       ┌─────────────────────────┐
       │   AI Analysis Layer     │
       │   (OpenAI / LLM)        │
       └────────────┬────────────┘
                    │
                    ▼
Structured, Normalized Factual Attributes
(Industry, Service, Budget, Timeline, Intent, Summary)
```

### What AI Does:
- **Disambiguates Natural Language**: Interprets colloquial phrases (e.g., Thai slang, informal requests, business jargon) into standardized taxonomy.
- **Extracts Hard Facts**: Pulls out stated budgets, currency symbols, and requested project deadlines.
- **Identifies Stated Pain Points**: Summarizes the core business problem succinctly for sales reps.
- **Detects Gaps**: Flags missing critical information (e.g., no email, unspecified budget, unclear scope).
- **Assesses Extraction Confidence**: Provides a self-assessed confidence metric based on clarity of the input text.

### What AI Does NOT Do:
- **Does NOT Calculate Lead Scores**: The AI is never asked "Give this lead a score from 1-100".
- **Does NOT Make Final Commercial Decisions**: The AI does not decide whether a lead is approved, rejected, or routed to enterprise account executives.
- **Does NOT Hallucinate Unstated Information**: If a budget or timeline is not mentioned, it must output `null` and set `stated: false`.

---

## 2. Why Keep AI Separate from Scoring Decisions?

| Issue | Direct AI Scoring ("Score this 1-100") | Separated AI Extraction + Deterministic Rules |
| :--- | :--- | :--- |
| **Explainability** | Opaque: "The AI gave you 74." Sales reps cannot explain why. | Transparent: "25 pts service fit + 20 pts budget + 20 pts urgency = 85 (High)." |
| **Consistency / Drift** | High variance across model updates, temperatures, and prompts. | 100% deterministic: Identical extracted facts always yield the exact same score. |
| **Business Agility** | Modifying business priorities requires rewiring and re-evaluating prompt text. | Modifying priorities simply means tweaking weights in `config/scoring.example.json`. |
| **Auditability** | Non-compliant with enterprise governance and audit requirements. | Fully auditable logs recorded in CRM custom properties. |

---

## 3. Extracted Fact Schema

The AI extraction output is strictly governed by `schemas/lead-analysis.schema.json`:

```json
{
  "industry": "restaurant",
  "service_requested": "LINE AI customer service",
  "problem": "High volume of repetitive customer enquiries regarding branch hours, reservations, and promotions overwhelming staff across 5 locations.",
  "budget": {
    "amount": 80000,
    "currency": "THB",
    "stated": true
  },
  "timeline_days": 28,
  "intent": "high",
  "language": "en",
  "summary": "Multi-location restaurant group seeks LINE AI customer service automation within 4 weeks to resolve repetitive inquiries. Budget approved at 80,000 THB.",
  "missing_information": [
    "company_website",
    "decision_maker_role",
    "current_pos_or_crm_system"
  ],
  "confidence_score": 0.94
}
```

---

## 4. Multilingual & Regional Capabilities

In modern Southeast Asian commerce, customer inquiries frequently mix Thai and English, use romanized Thai (*Karaoke*), or combine English technical terms with Thai conversational grammar:

> *"สวัสดีครับ สนใจทำ LINE bot ต่อกับระบบ POS ที่ร้าน มี 3 สาขา budget ประมาณ 100k เริ่มได้เมื่อไหร่ครับ"*

The extraction layer handles:
- Cross-lingual semantic extraction without requiring translation as a separate pre-step.
- Detection of local currency terms (`THB`, `บาท`, `k`, `หมื่น`, `แสน`).
- Conversion of relative time phrases (*"within a month"*, *"เดือนหน้า"*, *"ด่วนมาก"*, *"ภายใน 2 สัปดาห์"*) into normalized integer days.

---

## 5. Technical Implementation in Workflows

- **Model**: OpenAI `gpt-4o-mini` (fast, cost-effective, structured output compliant) or `gpt-4o`.
- **Enforcement**: OpenAI Structured Outputs (`response_format: { type: "json_schema", json_schema: ... }`) ensures 0% JSON syntax failures.
- **Temperature**: `0.0` for maximum factual consistency and extraction reproducibility.
