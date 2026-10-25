"""Smoke test for CI evaluation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.evaluation import CorpusBuilder, EvaluationHarness


def test_corpus_sizes():
    """Test that corpus has minimum required samples."""
    builder = CorpusBuilder()
    attacks, benign = builder.build()

    assert len(attacks) >= 200, f"Expected at least 200 attack samples, got {len(attacks)}"
    assert len(benign) >= 200, f"Expected at least 200 benign samples, got {len(benign)}"

    print(f"Attack samples: {len(attacks)}")
    print(f"Benign samples: {len(benign)}")

    # Check categories
    categories = set(a.category for a in attacks)
    expected_categories = {
        "direct_injection",
        "indirect_injection",
        "encoding_evasion",
        "role_escalation",
        "tool_smuggling",
        "exfiltration",
    }
    for cat in expected_categories:
        assert cat in categories, f"Missing category: {cat}"
        count = sum(1 for a in attacks if a.category == cat)
        print(f"  {cat}: {count} samples")


def test_harness_runs():
    """Test that evaluation harness runs without errors."""
    builder = CorpusBuilder()
    attacks, benign = builder.build()

    harness = EvaluationHarness()

    # Test a few samples
    for sample in attacks[:5] + benign[:5]:
        result = harness.evaluate_sample(sample)
        assert result.sample_id == sample.id
        assert result.category == sample.category
        assert isinstance(result.blocked, bool)
        assert isinstance(result.threat_detected, bool)
        assert isinstance(result.dlp_triggered, bool)
        assert result.latency_ms >= 0

    print("Harness smoke test passed")


def test_evaluation_summary():
    """Test evaluation summary computation."""
    builder = CorpusBuilder()
    attacks, benign = builder.build()

    harness = EvaluationHarness()
    results = []

    # Evaluate subset for speed
    for sample in attacks[:50] + benign[:50]:
        results.append(harness.evaluate_sample(sample))

    # Compute metrics
    tp = sum(1 for r in results if r.blocked and r.expected_blocked)
    fp = sum(1 for r in results if r.blocked and not r.expected_blocked)
    tn = sum(1 for r in results if not r.blocked and not r.expected_blocked)
    fn = sum(1 for r in results if not r.blocked and r.expected_blocked)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"Subset evaluation: P={precision:.3f}, R={recall:.3f}, F1={f1:.3f}")
    print(f"  TP={tp}, FP={fp}, TN={tn}, FN={fn}")

    # Basic sanity checks
    assert 0 <= precision <= 1
    assert 0 <= recall <= 1
    assert 0 <= f1 <= 1


if __name__ == "__main__":
    print("Running evaluation smoke tests...")
    test_corpus_sizes()
    test_harness_runs()
    test_evaluation_summary()
    print("All smoke tests passed!")
