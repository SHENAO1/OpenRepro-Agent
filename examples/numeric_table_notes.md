# Numeric Table Toy Notes

These notes describe a small reproducibility task with explicit numeric
settings. They are intentionally simple so OpenRepro can exercise ingestion,
candidate extraction, planning, and workflow-evidence reporting without
claiming a full paper reproduction.

Formula:

```text
y_i = beta_0 + beta_1 x_i + epsilon_i
```

Parameters:

| name | value | note |
| --- | ---: | --- |
| beta_0 | 0.25 | toy intercept |
| beta_1 | 1.50 | toy slope |
| noise_std | 0.05 | synthetic noise level |
| sample_count | 64 | generated examples |

Expected workflow evidence:

- Preserve the source notes in the project source index.
- Extract formula and parameter candidates as unverified evidence.
- Generate a plan, model ledger, run manifest, demo metrics, and benchmark
  report.
- Do not report a scientific reproduction score.
