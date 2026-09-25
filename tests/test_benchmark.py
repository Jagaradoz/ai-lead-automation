"""
test_benchmark.py
The ground-truth benchmark runs as part of the test suite, so rule changes that
regress scoring, extraction or safety flags fail CI.
"""

import pytest

from scripts.run_evaluation import run_benchmarks
from scripts.validate_schemas import main as validate_all


def test_benchmark_is_fully_accurate_with_default_profile(tmp_path):
    stats = run_benchmarks(reports_dir=tmp_path)

    assert stats["total"] == 10
    assert stats["extraction_accuracy"] == 100
    assert stats["scoring_accuracy"] == 100
    assert stats["safety_accuracy"] == 100
    assert (tmp_path / "latest-benchmark.md").exists()


def test_schemas_examples_and_profile_validate():
    with pytest.raises(SystemExit) as exit_info:
        validate_all()
    assert exit_info.value.code == 0
