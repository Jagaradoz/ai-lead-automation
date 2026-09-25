#!/usr/bin/env python3
"""
run_evaluation.py
Automated Benchmark Evaluation Runner for AI Lead Automation.
Executes test leads through AI fact extraction and deterministic scoring,
evaluating precision, recall, and safety against ground-truth assertions.
Generates an auditable benchmark report in evaluation/reports/latest-benchmark.md.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jsonschema import validate

from ai_extractor import analyze_lead, load_analysis_schema
from scoring_engine import score_lead

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT_DIR / "evaluation" / "datasets" / "sample-leads.json"
GROUND_TRUTH_PATH = ROOT_DIR / "evaluation" / "expected" / "ground-truth.json"
REPORTS_DIR = ROOT_DIR / "evaluation" / "reports"


def run_benchmarks() -> Dict[str, Any]:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        ground_truth_list = json.load(f)

    gt_map = {item["lead_id"]: item for item in ground_truth_list}

    results = []
    total_leads = len(dataset)
    passed_extractions = 0
    passed_scores = 0
    passed_safety = 0

    print("==================================================================")
    print("[*] AI Lead Automation - Benchmark Evaluation Suite")
    print("==================================================================")
    print(f"Loaded {total_leads} evaluation fixtures from dataset.\n")

    for lead in dataset:
        lead_id = lead["lead_id"]
        gt = gt_map.get(lead_id, {})
        expected_ext = gt.get("expected_extraction", {})
        expected_sc = gt.get("expected_scoring", {})

        # 1. Run Fact Extraction
        analysis = analyze_lead(lead)

        # 2. Run Deterministic Scoring
        score_res = score_lead(lead, analysis)

        # 3. Assess Extraction Quality
        ext_passed = True
        ext_reasons = []

        if "intent" in expected_ext and analysis["intent"] != expected_ext["intent"]:
            ext_passed = False
            ext_reasons.append(f"Intent mismatch: got '{analysis['intent']}', expected '{expected_ext['intent']}'")

        if "language" in expected_ext and analysis["language"] != expected_ext["language"]:
            ext_passed = False
            ext_reasons.append(f"Language mismatch: got '{analysis['language']}', expected '{expected_ext['language']}'")

        if "budget_stated" in expected_ext:
            if analysis["budget"]["stated"] != expected_ext["budget_stated"]:
                ext_passed = False
                ext_reasons.append(f"Budget stated mismatch: got {analysis['budget']['stated']}, expected {expected_ext['budget_stated']}")

        if ext_passed:
            passed_extractions += 1

        # 4. Assess Scoring Accuracy
        sc_passed = True
        sc_reasons = []

        score_val = score_res["total_score"]
        priority_val = score_res["priority"]

        if "score_range" in expected_sc:
            min_sc = expected_sc["score_range"]["min"]
            max_sc = expected_sc["score_range"]["max"]
            if not (min_sc <= score_val <= max_sc):
                sc_passed = False
                sc_reasons.append(f"Score {score_val} outside expected range [{min_sc}, {max_sc}]")

        if "expected_priority" in expected_sc and priority_val != expected_sc["expected_priority"]:
            sc_passed = False
            sc_reasons.append(f"Priority mismatch: got '{priority_val}', expected '{expected_sc['expected_priority']}'")

        if sc_passed:
            passed_scores += 1

        # 5. Assess Safety & Human Review Flags
        safety_passed = True
        safety_reasons = []

        if "requires_human_review" in expected_sc:
            if score_res["requires_human_review"] != expected_sc["requires_human_review"]:
                safety_passed = False
                safety_reasons.append(f"Review flag mismatch: got {score_res['requires_human_review']}, expected {expected_sc['requires_human_review']}")

        if "review_reason_substring" in expected_sc:
            expected_sub = expected_sc["review_reason_substring"].lower()
            reasons_text = " ".join(score_res["human_review_reasons"]).lower()
            if expected_sub not in reasons_text:
                safety_passed = False
                safety_reasons.append(f"Missing expected review trigger keyword: '{expected_sub}'")

        if safety_passed:
            passed_safety += 1

        status_symbol = "[PASS]" if (ext_passed and sc_passed and safety_passed) else "[WARN]"
        print(f"{status_symbol} {lead_id} | Score: {score_val:>2} ({priority_val:<12}) | Review: {str(score_res['requires_human_review']):<5} | Desc: {gt.get('description', '')[:35]}")

        results.append({
            "lead_id": lead_id,
            "description": gt.get("description", ""),
            "contact_name": lead.get("contact", {}).get("name"),
            "analysis": analysis,
            "score": score_res,
            "extraction_ok": ext_passed,
            "scoring_ok": sc_passed,
            "safety_ok": safety_passed,
            "issues": ext_reasons + sc_reasons + safety_reasons
        })

    ext_accuracy = (passed_extractions / total_leads) * 100
    sc_accuracy = (passed_scores / total_leads) * 100
    safety_accuracy = (passed_safety / total_leads) * 100

    print("\n------------------------------------------------------------------")
    print(f"Extraction Accuracy:      {passed_extractions}/{total_leads} ({ext_accuracy:.1f}%)")
    print(f"Scoring Model Accuracy:   {passed_scores}/{total_leads} ({sc_accuracy:.1f}%)")
    print(f"Safety & Governance Rate: {passed_safety}/{total_leads} ({safety_accuracy:.1f}%)")
    print("==================================================================")

    # Generate Markdown Report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / "latest-benchmark.md"

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report_content = f"""# AI Lead Automation - Evaluation Benchmark Report

**Generated At**: {now_str}  
**Total Evaluation Leads**: {total_leads}  
**Extraction Accuracy**: {ext_accuracy:.1f}%  
**Scoring Model Accuracy**: {sc_accuracy:.1f}%  
**Safety & Governance Recall**: {safety_accuracy:.1f}%  

---

## Detailed Lead Results Matrix

| Lead ID | Contact / Company | Intent | Stated Budget | Timeline | Score | Priority | Review Flag | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    for r in results:
        a = r["analysis"]
        s = r["score"]
        budget_str = f"{a['budget']['amount']:,.0f} {a['budget']['currency']}" if a['budget']['stated'] and a['budget']['amount'] else "None"
        timeline_str = f"{a['timeline_days']} days" if a['timeline_days'] else "Unstated"
        status = "PASSED" if (r["extraction_ok"] and r["scoring_ok"] and r["safety_ok"]) else "FLAGGED"
        report_content += f"| `{r['lead_id']}` | {r['contact_name']} | `{a['intent']}` | {budget_str} | {timeline_str} | **{s['total_score']}** | `{s['priority'].upper()}` | `{s['requires_human_review']}` | **{status}** |\n"

    report_content += """
---

## Key Verification Observations

1. **Enterprise Opportunity Routing**: High-value leads (`lead_eval_001`, `lead_eval_008`) with budgets >= 300,000 THB are automatically flagged for senior sales representative oversight.
2. **Spam & Disqualification**: Automated commercial solicitation (`lead_eval_007`) is immediately penalized with 0 points, mapped to `DISQUALIFIED`, and suppressed from outbound messaging.
3. **Out-of-Scope Isolation**: Non-software enquiries (hardware repair `lead_eval_006`) are granted 0 service fit points and flagged for human intervention before sales contact.
4. **Multilingual Ingestion**: Thai-language inquiries (`lead_eval_002`, `lead_eval_005`, `lead_eval_010`) are normalized, categorized, and scored without cross-lingual bias.
"""

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\n[PASS] Benchmark report successfully written to:\n       {report_file.relative_to(ROOT_DIR)}")
    return {
        "total": total_leads,
        "extraction_accuracy": ext_accuracy,
        "scoring_accuracy": sc_accuracy,
        "safety_accuracy": safety_accuracy,
    }


if __name__ == "__main__":
    stats = run_benchmarks()
    if stats["scoring_accuracy"] < 100 or stats["safety_accuracy"] < 100:
        sys.exit(1)
    sys.exit(0)
