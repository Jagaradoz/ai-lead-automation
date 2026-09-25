# Deterministic Lead Scoring & Explainability

## 1. The Core Philosophy: Explainable Lead Scoring

In traditional sales development, scoring models frequently suffer from one of two extremes:
1. **Opaque AI Scoring**: An LLM assigns a subjective number (e.g., "78/100") with no consistent rubric, leaving salespeople distrustful of lead assignments.
2. **Naive Keyword Filters**: Rigid CRM point rules (e.g., "+5 points if email is provided") that fail to comprehend customer intent or nuances in natural language.

**AI Lead Automation** combines the strengths of both while eliminating their flaws:
- **AI extracts facts**: The LLM reliably identifies the customer's stated industry, requested service, budget, and timeline.
- **Business rules calculate points**: A deterministic rule engine executes a weighted scoring rubric against those extracted attributes.

```text
Extracted Facts (from AI Analysis)
  │
  ▼
Rule Engine (config/scoring.example.json)
  │
  ├── Service Fit:          25 / 25 pts  ("Core offering match: LINE AI")
  ├── Purchase Intent:      20 / 20 pts  ("Stated high intent & approved budget")
  ├── Urgency:              20 / 20 pts  ("Timeline < 30 days")
  ├── Budget Fit:           15 / 20 pts  ("80,000 THB fits SMB tier")
  ├── Decision Authority:    0 /  5 pts  ("Authority not specified")
  ├── Company Fit:           5 /  5 pts  ("Multi-branch restaurant profile")
  └── Data Completeness:     5 /  5 pts  ("Email, phone, and company present")
  ───────────────────────────────────────
  Total Score:              90 / 100 pts
  Priority Tier:            HIGH
```

---

## 2. The 7 Scoring Dimensions

The scoring engine evaluates leads across seven distinct, configurable dimensions:

### 1. Service Fit (Max 25 pts)
Measures alignment between what the prospect wants and what the business actually sells.
- **25 pts**: Direct match for core offerings (e.g., LINE AI bot, CRM automation, lead intelligence).
- **15 pts**: Adjacent offerings (e.g., custom webhooks, data pipelines).
- **0 pts**: Out of scope (e.g., hardware repairs, SEO backlinks, native mobile apps).

### 2. Purchase Intent (Max 20 pts)
Reflects commercial readiness and buying signals.
- **20 pts**: High intent (specific problem, ready to proceed, approved budget).
- **10 pts**: Medium intent (evaluating options, asking for high-level pricing).
- **0 pts**: Low intent or academic interest.
- **Disqualified**: Commercial spam or irrelevant promotional submissions.

### 3. Urgency / Timeline Fit (Max 20 pts)
Evaluates when the client needs the solution deployed.
- **20 pts**: High urgency (within 30 days).
- **12 pts**: Medium urgency (30 to 90 days).
- **5 pts**: Low urgency (>90 days or unspecified).

### 4. Budget Fit (Max 20 pts)
Compares stated financial budget against commercial service pricing.
- **20 pts**: Stated budget meets or exceeds mid-market / enterprise threshold (>= 100,000 THB).
- **15 pts**: Stated budget fits standard starter / SMB packages (40,000 - 99,999 THB).
- **10 pts**: Budget unstated (neutral baseline points; will be qualified during discovery).
- **5 pts**: Stated budget below minimum viable engagement (< 40,000 THB).

### 5. Decision Authority (Max 5 pts)
Identifies whether the submitter is an executive or business owner.
- **5 pts**: Founder, CEO, VP, Managing Director.
- **0 pts**: Unspecified or non-decision-maker.

### 6. Company Fit (Max 5 pts)
Assesses whether the business operates in a priority target vertical.
- **5 pts**: Target vertical (healthcare, restaurant chains, ecommerce, professional services).
- **0 pts**: Unknown or non-target vertical.

### 7. Data Completeness (Max 5 pts)
Rewards submission quality.
- **5 pts**: Both verified email and direct phone number plus company name provided.
- **3 pts**: Basic contact info only (email only or phone only).

---

## 3. Priority Thresholds & Action Routing

The composite score (0-100) maps directly to actionable operational tiers:

| Score Band | Priority Tier | Operational Action |
| :--- | :--- | :--- |
| **75 - 100** | **HIGH** | Instant Slack alert to senior sales reps; auto-create HubSpot Deal; target response < 5 minutes. |
| **45 - 74** | **MEDIUM** | Standard lead queue; automated calendar booking invite sent via email/LINE. |
| **20 - 44** | **LOW** | Added to marketing nurture newsletter; self-service resource link dispatched. |
| **0 - 19** | **DISQUALIFIED** | Marked disqualified in CRM; auto-archived; zero salesperson time expended. |

---

## 4. Full Auditability & CRM Integration

Every scoring calculation produces an `explanations` array in `schemas/lead-score.schema.json`.

When the lead syncs to HubSpot, this audit trail is written directly into custom CRM properties:
- `lead_score_total`: `90`
- `lead_score_priority`: `high`
- `lead_score_reasons`:
  ```text
  [Service Fit: 25/25] Direct match for core automation offerings ('LINE AI customer service').
  [Purchase Intent: 20/20] High intent: stated concrete problem, approved budget, explicit deadline.
  [Urgency: 20/20] High urgency: requested implementation timeframe is 28 days.
  [Budget Fit: 15/20] Stated budget of 80,000 THB fits starter/SMB multi-branch package.
  [Decision Authority: 0/5] Authority level not specified.
  [Company Fit: 5/5] Restaurant chain vertical matches target customer profile.
  [Data Completeness: 5/5] Complete contact details provided.
  ```

A sales rep or manager opening HubSpot can instantly see exactly why the lead is prioritized, building immediate trust in the automation system.
