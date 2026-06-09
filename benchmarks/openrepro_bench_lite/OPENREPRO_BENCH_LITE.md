# OpenRepro-Bench Lite

- schema_version: 1.53.0
- suite_path: `benchmarks\openrepro_bench_lite\suite.json`
- bench_dir: `benchmarks\openrepro_bench_lite`

| Task | Title | Difficulty | Focus |
| --- | --- | --- | --- |
| bench_lite_boc_notes | BOC-like workflow notes | starter | source ingestion, rule analysis, plan generation, and demo evidence |
| bench_lite_random_search_notes | Random-search toy workflow notes | starter | candidate extraction from optimization-style notes plus demo evidence |
| bench_lite_numeric_table_notes | Numeric table toy workflow notes | starter | parameter/table-like evidence extraction plus demo evidence |

## Run

```bash
openrepro bench-lite
```

## Policy

OpenRepro-Bench Lite reports workflow-compliance evidence only. It does not claim paper reproduction success or scientific benchmark scores.
