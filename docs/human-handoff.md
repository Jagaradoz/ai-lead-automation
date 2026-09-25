# Human-in-the-Loop Governance & Escalation

## 1. Operating Philosophy

A core tenet of **AI Lead Automation** is that **automation does not replace the sales team—it empowers them**.

Premature or unchecked automation risks embarrassing customer interactions, brand damage, and lost revenue. The system divides workflow responsibilities into three distinct operational tiers:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 1. SIMPLE PREDICTABLE TASKS                                            │
│    Action: 100% Automated                                              │
│    Examples: Schema validation, deduplication, contact upsert,         │
│              sending calendar booking link, sending intake brochure.   │
├────────────────────────────────────────────────────────────────────────┤
│ 2. AMBIGUOUS OR UNSTRUCTURED INFORMATION                              │
│    Action: AI-Assisted Extraction & Structuring                        │
│    Examples: Parsing colloquial text, extracting budgets & timelines,  │
│              generating factual 1-sentence summaries.                  │
├────────────────────────────────────────────────────────────────────────┤
│ 3. HIGH-VALUE, UNCERTAIN, OR SENSITIVE SCENARIOS                       │
│    Action: Mandatory Human Review (Human-in-the-Loop)                  │
│    Examples: Enterprise deal sizes, low extraction confidence,         │
│              custom scope requests, angry sentiment, price haggling.   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Trigger Criteria for Human Handoff

The deterministic scoring and AI extraction engines monitor specific safety boundaries. If any of the following conditions trigger, `requires_human_review` is set to `true`:

| Trigger Condition | Threshold / Heuristic | Why Human Intervention Is Required |
| :--- | :--- | :--- |
| **Low AI Confidence** | `confidence_score < 0.65` | The prospect's inquiry is contradictory, vague, or corrupted. Automated action may misinterpret intent. |
| **Large Opportunity Deal** | `budget >= 300,000 THB` (or `$10,000+ USD`) | High-value prospects expect tailored, VIP communication from senior account executives, not automated replies. |
| **Custom / Out-of-Catalog Scope** | High intent but service is outside standard offerings | Potential strategic enterprise opportunity requiring bespoke scoping. |
| **Negative / Frustrated Sentiment** | Detected dissatisfaction or urgent complaint | Risk of escalating frustration if greeted by generic bot responses. |
| **Data Conflict / Ambiguity** | Contradictory information provided across fields | Requires a human to verify details before creating commercial proposals. |
| **Spam / Security Anomaly** | Suspicious URLs, script tags, or promotional spam | Prevents automated outbound messaging from sending company collateral to spam bots. |

---

## 3. Human Handoff Execution Flow

```text
Lead Evaluated by Scoring Engine
  │
  ├──► `requires_human_review == false`
  │        └── Standard automated path (Auto-reply, calendar invite, CRM sync)
  │
  └──► `requires_human_review == true`
           │
           ├── 1. Tag CRM Record: `lead_status = "Needs Human Review"`
           ├── 2. Populate CRM Property: `review_reasons = [...]`
           ├── 3. Place lead in HubSpot "Triage Queue" view
           └── 4. Dispatch High-Priority Slack/Teams Alert with Context Card
```

---

## 4. Alert Notification Design

When human review is triggered, sales reps receive an actionable alert card in their designated Slack channel:

```markdown
⚠️ HUMAN REVIEW REQUIRED — New Inbound Lead Flagged

Prospect: Dr. Sarah Jenkins (SmileCraft Dental Group)
Channel: Website Form | Region: US (Bay Area)
Calculated Priority: HIGH (Score: 85/100)

Review Reason(s):
• High-value opportunity: Stated budget ~$15,000 USD (500,000 THB)
• Requested service: Multi-channel SMS/WhatsApp integration with custom CRM

AI Executive Summary:
"Three-clinic dental practice seeking automated patient scheduling follow-ups and reminders to reduce no-shows. Launch deadline 30 days."

👉 [Open Lead in HubSpot](https://app.hubspot.com/contacts/xxx/contact/yyy)
👉 [Claim Lead & Assign to Me] | [Reclassify as Standard]
```

---

## 5. The Reviewer Feedback Loop

When a salesperson or triage manager reviews a flagged lead:
1. They can approve the automated suggestion or override specific attributes (e.g., adjust budget or industry classification).
2. The override event is logged to the evaluation feedback store.
3. This human-labeled data feeds directly into the **Evaluation Strategy** (`docs/evaluation-strategy.md`) to benchmark and improve future extraction accuracy.
