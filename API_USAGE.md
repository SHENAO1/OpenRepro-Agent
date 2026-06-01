# API Usage Policy

OpenRepro-Agent v0.3.1 does not implement real API providers. It uses a deterministic mock provider and cache-aware usage records by default.

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
  "status": "mocked",
  "request_hash": "optional-sha256"
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
  "mock_events": 1,
  "cached_events": 0,
  "cache_hits": 0,
  "cache_misses": 1,
  "request_hashes": [],
  "providers": {
    "mock": {
      "calls": 0,
      "tokens": 0,
      "estimated_cost_usd": 0.0
    }
  }
}
```

Mock and cached events are not counted as real API calls.

## Principles

1. v0.3.1 defaults to mock mode only.
2. Future versions may support real providers with explicit opt-in.
3. Token counts, costs, cache hits, and task types must be tracked when real providers are used.
4. The project must not invent token usage or cost data.
5. API records must remain auditable and tied to a specific run directory.
