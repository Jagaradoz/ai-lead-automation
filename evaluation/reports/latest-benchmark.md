# AI Lead Automation - Evaluation Benchmark Report

**Generated At**: 2026-09-25 07:08:38 UTC  
**Total Evaluation Leads**: 10  
**Extraction Accuracy**: 100.0%  
**Scoring Model Accuracy**: 100.0%  
**Safety & Governance Recall**: 100.0%  

---

## Detailed Lead Results Matrix

| Lead ID | Contact / Company | Intent | Stated Budget | Timeline | Score | Priority | Review Flag | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `lead_eval_001` | Dr. Sarah Jenkins | `high` | 500,000 THB | 30 days | **100** | `HIGH` | `True` | **PASSED** |
| `lead_eval_002` | คุณวิชัย กิตติวงศ์ | `high` | 120,000 THB | 28 days | **95** | `HIGH` | `False` | **PASSED** |
| `lead_eval_003` | Tom | `low` | None | Unstated | **18** | `DISQUALIFIED` | `True` | **PASSED** |
| `lead_eval_004` | Elena Rostova | `high` | None | 14 days | **75** | `HIGH` | `False` | **PASSED** |
| `lead_eval_005` | กานดา สุวรรณเมธี | `medium` | 50,000 THB | Unstated | **65** | `MEDIUM` | `False` | **PASSED** |
| `lead_eval_006` | Robert Henderson | `high` | None | 1 days | **60** | `MEDIUM` | `True` | **PASSED** |
| `lead_eval_007` | SEO Specialist Kevin | `spam` | 49 USD | 14 days | **0** | `DISQUALIFIED` | `True` | **PASSED** |
| `lead_eval_008` | Marcus Vance | `high` | 500,000 THB | 20 days | **95** | `HIGH` | `True` | **PASSED** |
| `lead_eval_009` | Dave Miller | `medium` | 15,000 THB | 14 days | **60** | `MEDIUM` | `False` | **PASSED** |
| `lead_eval_010` | สมบัติ | `ambiguous` | None | Unstated | **0** | `DISQUALIFIED` | `True` | **PASSED** |

---

## Key Verification Observations

1. **Enterprise Opportunity Routing**: High-value leads (`lead_eval_001`, `lead_eval_008`) with budgets >= 300,000 THB are automatically flagged for senior sales representative oversight.
2. **Spam & Disqualification**: Automated commercial solicitation (`lead_eval_007`) is immediately penalized with 0 points, mapped to `DISQUALIFIED`, and suppressed from outbound messaging.
3. **Out-of-Scope Isolation**: Non-software enquiries (hardware repair `lead_eval_006`) are granted 0 service fit points and flagged for human intervention before sales contact.
4. **Multilingual Ingestion**: Thai-language inquiries (`lead_eval_002`, `lead_eval_005`, `lead_eval_010`) are normalized, categorized, and scored without cross-lingual bias.
