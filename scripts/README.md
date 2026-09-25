# Automation Scripts & Tooling

This directory provides developer utilities, local testing scripts, schema validators, the deterministic scoring engine, and the evaluation benchmark runner.

---

## Available Tooling

### 1. Schema & Data Validator (`scripts/validate_schemas.py`)
- **Purpose**: Validates all JSON Schemas, canonical payload examples, configuration files, and evaluation datasets against JSON Schema Draft-07.
- **Run**:
  ```bash
  python scripts/validate_schemas.py
  ```

### 2. Deterministic Scoring Engine (`scripts/scoring_engine.py`)
- **Purpose**: Calculates transparent, point-by-point qualification scores (0-100), operational priority brackets (`high`, `medium`, `low`, `disqualified`), and human review triggers.
- **Run**:
  ```bash
  python scripts/scoring_engine.py
  ```

### 3. Channel Normalizer (`scripts/normalize.py`)
- **Purpose**: Converts raw, platform-specific payloads (Website forms, LINE OA webhooks, Meta Lead Ads) into validated Canonical Leads.
- **Run**:
  ```bash
  python scripts/normalize.py
  ```

### 4. AI Fact Extractor (`scripts/ai_extractor.py`)
- **Purpose**: Scopes AI strictly to objective fact extraction. Supports both live OpenAI Structured Outputs (`gpt-4o-mini`) and zero-cost offline semantic pattern extraction for local test runs.
- **Run**:
  ```bash
  python scripts/ai_extractor.py
  ```

### 5. Automated Evaluation Harness (`scripts/run_evaluation.py`)
- **Purpose**: Executes the benchmark test suite across 10 diverse lead fixtures, testing extraction fidelity, deterministic scoring accuracy, and safety flag recall against oracle ground-truth assertions. Automatically generates `evaluation/reports/latest-benchmark.md`.
- **Run**:
  ```bash
  python scripts/run_evaluation.py
  ```

### 6. Mock Webhook Dispatcher (`scripts/send_test_lead.py`)
- **Purpose**: Dispatches test leads to a local or remote n8n intake webhook (`POST /webhook/leads/incoming`).
- **Run**:
  ```bash
  python scripts/send_test_lead.py --lead-id lead_eval_001
  python scripts/send_test_lead.py --raw
  ```
