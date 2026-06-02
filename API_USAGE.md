# API Usage Policy

OpenRepro-Agent v0.5.2 uses a deterministic mock provider by default and includes an explicit opt-in OpenAI-compatible provider path. Real calls require `api.enable_real_api: true` and an environment-backed API key.

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
  "request_hash": "optional-sha256",
  "prompt_preview": "[REDACTED_SECRET]",
  "response_preview": "MockProvider response...",
  "redaction_enabled": true,
  "cache_enabled": true,
  "cache_namespace": "mock/mock-llm/analyze"
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

Mock and cached events are not counted as real API calls. Real provider events are counted only from provider-returned usage fields. Costs remain zero unless a provider supplies an auditable estimate.

`prompt_preview` and `response_preview` are compact previews for auditability.
When `redact_prompts` is enabled, likely API keys, tokens, secrets, email
addresses, and long key-like strings are replaced with `[REDACTED_SECRET]`.
The full prompt is not written to usage records.

Provider cache files are stored under a provider/model/task namespace:

```text
workspace/provider_cache/<provider>/<model>/<task>/<request_hash>.json
```

The cache policy is stored in `project_config.yaml`:

```yaml
api:
  cache_enabled: true
  cache_ttl_seconds:
  redact_prompts: true
```

## Principles

1. v0.5.2 defaults to mock mode only.
2. Real providers require explicit opt-in and environment-backed secrets.
3. Token counts, costs, cache hits, and task types must be tracked when real providers are used.
4. The project must not invent token usage or cost data.
5. API records must remain auditable and tied to a specific run directory.
6. Usage records must not store unredacted secrets or full prompts by default.
