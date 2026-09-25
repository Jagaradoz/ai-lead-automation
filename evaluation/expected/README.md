# Evaluation Expected Ground Truth

This directory houses the ground-truth benchmark assertions used by the evaluation harness (introduced in **Milestone 0.6**).

## Purpose

Automated workflows integrating AI cannot rely solely on unit tests. Real-world natural language messages vary widely in structure, vocabulary, tone, and language (e.g., Thai vs. English). 

The evaluation framework verifies that:
1. **AI Extraction Integrity**: The LLM extracts accurate structured facts without hallucinations.
2. **Deterministic Stability**: The rule engine computes consistent, explainable scores from extracted data.
3. **Safety & Routing Precision**: Low-confidence or out-of-scope enquiries are reliably flagged for human review.

---

## Benchmark Comparison Matrix

For each test fixture in `../datasets/sample-leads.json`, an expected ground-truth record defines target parameters:

```json
{
  "lead_id": "lead_eval_001",
  "expected_extraction": {
    "industry": "healthcare",
    "service_requested": "SMS and WhatsApp appointment reminder automation",
    "budget": {
      "amount": 500000,
      "currency": "THB",
      "tolerance_pct": 0.1
    },
    "timeline_days": {
      "min": 20,
      "max": 35
    },
    "intent": "high",
    "language": "en"
  },
  "expected_scoring": {
    "score_range": {
      "min": 75,
      "max": 95
    },
    "expected_priority": "high",
    "must_include_dimensions": ["service_fit", "urgency", "budget_fit"]
  },
  "expected_governance": {
    "requires_human_review": false,
    "review_reasons_contain": []
  }
}
```

---

## Grading Rubrics & Tolerances

| Evaluation Dimension | Metric / Criterion | Success Threshold |
| :--- | :--- | :--- |
| **Field Extraction** | Precision & Recall on key fields (industry, service, budget, timeline) | Exact or semantic equivalent |
| **Budget Extraction** | Value extraction within numeric tolerance | Within ±10% or exact currency |
| **Intent Classification** | Categorical match (`high`, `medium`, `low`, `spam`, `ambiguous`) | Exact category match |
| **Score Variance** | Delta between actual deterministic score and expected score band | 0 point rule deviation |
| **Human Review Triggers** | True positive rate for flagging edge cases (spam, large opportunity, low confidence) | 100% recall on flagged edge cases |

---

## Adding New Test Cases

1. Add the raw or canonical input lead to `../datasets/sample-leads.json`.
2. Add the corresponding expected oracle specification into this directory.
3. Include rationale in the commit describing which real-world failure mode or edge case the lead tests.
