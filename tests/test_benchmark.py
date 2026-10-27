"""Unit tests verifying all modular discovery benchmark suites and precision metrics."""

from backend.app.engines.discovery.benchmark import (
    run_benchmark,
    run_matching_benchmark,
    run_normalization_benchmark,
    run_provider_benchmark,
    run_e2e_pipeline_benchmark,
)


def test_discovery_matching_benchmark_metrics():
    metrics = run_matching_benchmark()
    # Expanded corpus has 22 cases
    assert metrics.total_cases == 22
    assert metrics.true_positives == 14
    assert metrics.true_negatives == 8
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.false_positive_rate == 0.0
    assert metrics.duplicate_rate == 0.0
    assert metrics.evidence_completeness == 1.0
    assert metrics.avg_latency_ms < 50.0  # Fast local in-memory evaluation
    assert "in-memory" in metrics.scope_note.lower()


def test_normalization_benchmark_suite():
    metrics = run_normalization_benchmark()
    assert metrics.total_cases >= 8
    assert metrics.passed_cases == metrics.total_cases
    assert metrics.accuracy == 1.0
    assert metrics.avg_latency_ms < 150.0


def test_provider_adapter_benchmark_suite():
    metrics = run_provider_benchmark()
    assert metrics.total_adapters == 4
    assert metrics.scenarios_tested >= 5
    assert metrics.passed_adapters >= 3


def test_e2e_pipeline_benchmark_suite():
    metrics = run_e2e_pipeline_benchmark()
    assert metrics.total_injected_records == 5
    assert metrics.deduplicated_records == 3
    assert metrics.duplicate_reduction_rate == 0.4  # 2 of 5 duplicates eliminated
    assert metrics.db_persistence_verified is True
