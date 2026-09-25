# AI Evaluation & Quality Assurance Strategy

## 1. Why Evaluate AI Automations?

A primary deficiency in conventional AI portfolio projects is the complete lack of systematic testing. Prompts and workflows are often tested informally on one or two hand-crafted examples, with no regression testing when prompts, models, or edge cases change.

In a production-grade automation system:
- LLM model updates (e.g., transitioning from GPT-4o-mini v1 to v2) can silently alter extraction formats or subtle semantic interpretations.
- Prompt tweaks designed to fix one edge case might break extraction on other lead types.
- Scoring rules must remain numerically deterministic and consistent over time.

This project treats **AI evaluation as automated software testing**.

---

## 2. Test Dataset Variety

The initial evaluation suite (`evaluation/datasets/sample-leads.json`) contains 10 baseline fixtures representing critical real-world variations:

| Lead ID | Test Case Persona | Language | Key Challenge / Edge Case |
| :--- | :--- | :--- | :--- |
| `lead_eval_001` | Strong English Healthcare SMB | English | High intent, clear USD budget, tight 30-day timeline |
| `lead_eval_002` | Strong Thai Restaurant Chain | Thai | Multi-branch LINE bot request, Thai currency (`บาท`), 4-week timeline |
| `lead_eval_003` | Weak Inquisitive Lead | English | Casual curiosity, zero budget, zero timeline |
| `lead_eval_004` | Urgent E-Commerce Brand | English | Urgent 14-day timeline, clear integration scope, **missing budget** |
| `lead_eval_005` | Boutique Resort Hotel | Thai | Stated budget, clear scope, **missing timeline / no urgency** |
| `lead_eval_006` | Hardware Server Repair | English | Urgent high-intent tone, but **completely out-of-scope service** |
| `lead_eval_007` | SEO Backlink Promotional Bot | English | **Obvious commercial spam**, malicious URLs, must disqualify |
| `lead_eval_008` | Enterprise Institutional Bank | English | High-value ($45k USD), RFP process, enterprise compliance, **human review trigger** |
| `lead_eval_009` | Solo Community Gym | English | Ultra-low budget ($400 USD), SMB starter tier |
| `lead_eval_010` | Ambiguous Thai Text | Thai | Minimal text (*"สนใจ ขอรายละเอียดหน่อยครับ"*), **low AI confidence trigger** |

---

## 3. Evaluation Dimensions & Ground-Truth Oracle

The evaluation harness introduced in **Milestone 0.6** will execute each fixture through the pipeline and compare actual outputs against ground-truth assertions in `evaluation/expected/`:

```text
               Input Sample Lead
                       │
                       ▼
       ┌───────────────────────────────┐
       │ AI Extraction + Rule Scoring  │
       └───────────────┬───────────────┘
                       │
                       ▼
                 Actual Output
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
Expected Ground Truth          Evaluation Runner
(evaluation/expected/)         (scripts/run-evaluation)
        │                             │
        └──────────────┬──────────────┘
                       ▼
       Automated Benchmark Report
       (Precision, Recall, Drift, Regressions)
```

### Metrics Tracked:

1. **Extraction Accuracy**:
   - Industry detection match (Exact / Semantic equivalent).
   - Stated budget amount (within ±10% tolerance) and currency accuracy.
   - Timeline days extraction (within ±5 days tolerance).
   - Language classification accuracy (`en`, `th`).
2. **Intent Classification**:
   - Confusion matrix across categorical labels (`high`, `medium`, `low`, `spam`, `ambiguous`).
3. **Deterministic Scoring Stability**:
   - Difference between expected score bracket and actual calculated score (Target: 0 point deviation for identical extracted facts).
4. **Governance & Escalation Precision**:
   - Recall on `requires_human_review` flags (100% target for enterprise opportunities and low-confidence leads).

> [!NOTE]
> In accordance with sound engineering practice, this repository does not publish synthetic or fabricated performance benchmark percentages. Real benchmark figures will be generated and published only after executing the Milestone 0.6 evaluation runner.

---

## 4. Benchmark Workflow & CI Integration

Once Milestone 0.6 is deployed, the evaluation harness will run automatically via GitHub Actions / CLI scripts:

```bash
# Planned CLI invocation
npm run test:eval
# or
python scripts/run-evaluation.py
```

The script will:
1. Iterate through all items in `evaluation/datasets/sample-leads.json`.
2. Invoke the structured extraction node and rule scoring logic.
3. Assert results against `evaluation/expected/`.
4. Output a summary table and export a markdown report to `evaluation/reports/latest-run.md`.
5. Exit with non-zero code if any critical regression (e.g. failing to flag spam or miscalculating high-value enterprise thresholds) is detected.
