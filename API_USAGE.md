# API Usage Policy

OpenRepro-Agent v0.2.0 does not call real API providers by default.

## Files

Each demo run writes:

```text
api_usage/api_usage.jsonl
api_usage/api_usage_summary.json
```

## JSONL record schema

```json
{
  "timestamp": "2026-xx-xxT20:30:15",
  "provider": "mock",
  "model": "mock-llm",
  "task": "analyze",
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0,
  "estimated_cost_usd": 0.0,
  "cache_hit": false,
  "status": "mocked"
}
```

## Summary schema

```json
{
  "total_calls": 0,
  "total_prompt_tokens": 0,
  "total_completion_tokens": 0,
  "total_tokens": 0,
  "estimated_total_cost_usd": 0.0,
  "providers": {
    "mock": {
      "calls": 0,
      "tokens": 0,
      "estimated_cost_usd": 0.0
    }
  }
}
```

The implementation may include `mock_events` to show how many mock bookkeeping events were written. Mock events are not counted as real API calls.

## Principles

1. v0.2.0 defaults to mock mode only.
2. Future versions may support real providers.
3. Token counts, costs, cache hits, and task types must be tracked when real providers are used.
4. The project must not invent token usage or cost data.
5. API records must remain auditable and tied to a specific run directory.
