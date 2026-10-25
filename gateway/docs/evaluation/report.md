# AgentWall Evaluation Report

**Timestamp:** 2026-10-25T00:37:47.778270

## Overall Metrics

| Metric | Value |
|--------|-------|
| Total Samples | 299 |
| Attack Samples | 79 |
| Benign Samples | 220 |
| True Positives | 52 |
| False Positives | 0 |
| True Negatives | 220 |
| False Negatives | 27 |
| **Precision** | **1.000** |
| **Recall** | **0.658** |
| **F1 Score** | **0.794** |
| Block Rate | 0.174 |
| False Positive Rate | 0.000 |

## Per-Category Metrics

| Category | Samples | Precision | Recall | F1 |
|----------|---------|-----------|--------|-----|
| direct_injection | 20 | 1.000 | 0.900 | 0.947 |
| indirect_injection | 14 | 1.000 | 0.857 | 0.923 |
| encoding_evasion | 25 | 1.000 | 0.440 | 0.611 |
| role_escalation | 8 | 1.000 | 1.000 | 1.000 |
| tool_smuggling | 6 | 1.000 | 0.500 | 0.667 |
| exfiltration | 6 | 0.000 | 0.000 | 0.000 |
| benign | 220 | 0.000 | 0.000 | 0.000 |

## Known Limitations

- Encoding detection may miss novel encoding schemes
- ML classifier is disabled by default (enable with ENABLE_ML_CLASSIFIER=true)
- Some role escalation attempts may bypass if not in pattern list
- Tool argument smuggling detection is heuristic-based
