"""API usage bookkeeping for OpenRepro-Agent.

v0.2.0 does not call real model providers.  This module records mock events with
zero tokens and zero cost, and it summarizes only actual non-mocked calls as
billable API calls.  That distinction prevents the tool from inventing token
usage while still preserving the accounting schema needed by future releases.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .utils import iso_now, write_json


@dataclass
class APIUsageRecord:
    timestamp: str
    provider: str
    model: str
    task: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    cache_hit: bool
    status: str


MOCK_PROVIDER = "mock"
MOCK_MODEL = "mock-llm"


def mock_usage_record(task: str) -> APIUsageRecord:
    """Create a zero-token mock usage record."""
    return APIUsageRecord(
        timestamp=iso_now(),
        provider=MOCK_PROVIDER,
        model=MOCK_MODEL,
        task=task,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        estimated_cost_usd=0.0,
        cache_hit=False,
        status="mocked",
    )


def append_usage_record(jsonl_path: Path, record: APIUsageRecord | dict[str, Any]) -> None:
    """Append a usage record to a JSONL file."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(record) if isinstance(record, APIUsageRecord) else record
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def read_usage_records(jsonl_path: Path) -> list[dict[str, Any]]:
    """Read API usage records from JSONL."""
    if not jsonl_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def summarize_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize API usage without counting mocked events as real calls."""
    summary: dict[str, Any] = {
        "total_calls": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "estimated_total_cost_usd": 0.0,
        "mock_events": 0,
        "providers": {
            MOCK_PROVIDER: {
                "calls": 0,
                "tokens": 0,
                "estimated_cost_usd": 0.0,
            }
        },
    }

    for record in records:
        provider = str(record.get("provider", MOCK_PROVIDER))
        provider_summary = summary["providers"].setdefault(
            provider,
            {"calls": 0, "tokens": 0, "estimated_cost_usd": 0.0},
        )
        if record.get("status") == "mocked":
            summary["mock_events"] += 1
            continue

        prompt_tokens = int(record.get("prompt_tokens", 0) or 0)
        completion_tokens = int(record.get("completion_tokens", 0) or 0)
        total_tokens = int(record.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        cost = float(record.get("estimated_cost_usd", 0.0) or 0.0)

        summary["total_calls"] += 1
        summary["total_prompt_tokens"] += prompt_tokens
        summary["total_completion_tokens"] += completion_tokens
        summary["total_tokens"] += total_tokens
        summary["estimated_total_cost_usd"] += cost
        provider_summary["calls"] += 1
        provider_summary["tokens"] += total_tokens
        provider_summary["estimated_cost_usd"] += cost

    summary["estimated_total_cost_usd"] = round(summary["estimated_total_cost_usd"], 8)
    for provider_summary in summary["providers"].values():
        provider_summary["estimated_cost_usd"] = round(provider_summary["estimated_cost_usd"], 8)
    return summary


def write_mock_usage_files(api_usage_dir: Path, task: str) -> dict[str, Any]:
    """Write jsonl and summary files for a mock task."""
    api_usage_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = api_usage_dir / "api_usage.jsonl"
    record = mock_usage_record(task)
    append_usage_record(jsonl_path, record)
    summary = summarize_usage(read_usage_records(jsonl_path))
    write_json(api_usage_dir / "api_usage_summary.json", summary)
    return summary
