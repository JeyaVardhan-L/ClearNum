"""Unit test verifying the discovery benchmark suite and precision metrics."""

from backend.app.engines.discovery.benchmark import run_benchmark


def test_discovery_benchmark_metrics():
    metrics = run_benchmark()
    assert metrics.total_cases >= 14
    assert metrics.true_positives >= 8
    assert metrics.true_negatives >= 5
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.false_positive_rate == 0.0
    assert metrics.duplicate_rate == 0.0
    assert metrics.evidence_completeness == 1.0
    assert metrics.avg_latency_ms < 50.0  # Fast local in-memory evaluation
