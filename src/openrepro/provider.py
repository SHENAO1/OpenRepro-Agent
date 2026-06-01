"""Provider abstraction and deterministic cache-backed mock provider."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .api_usage import append_usage_record, summarize_usage, read_usage_records
from .utils import iso_now, read_json, write_json


@dataclass
class ProviderRequest:
    """A provider request that can be hashed and cached."""

    task: str
    prompt: str
    provider: str = "mock"
    model: str = "mock-llm"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_hash_payload(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "prompt": self.prompt,
            "provider": self.provider,
            "model": self.model,
            "metadata": self.metadata,
        }

    def request_hash(self) -> str:
        payload = json.dumps(self.to_hash_payload(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ProviderResponse:
    """A provider response with cache and usage metadata."""

    provider: str
    model: str
    task: str
    content: str
    request_hash: str
    cache_hit: bool
    status: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseProvider:
    """Base provider interface."""

    name = "base"
    model = "base-model"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError


class MockProvider(BaseProvider):
    """Deterministic mock provider used by default."""

    name = "mock"
    model = "mock-llm"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        request_hash = request.request_hash()
        content = (
            f"MockProvider response for task={request.task}; "
            f"request_hash={request_hash[:16]}; no real API call was made."
        )
        return ProviderResponse(
            provider=self.name,
            model=request.model or self.model,
            task=request.task,
            content=content,
            request_hash=request_hash,
            cache_hit=False,
            status="mocked",
            created_at=iso_now(),
        )


class ProviderDisabledError(ValueError):
    """Raised when a non-mock provider is requested while real APIs are disabled."""


def get_provider(name: str = "mock", enable_real_api: bool = False) -> BaseProvider:
    """Return a provider instance.

    v0.3.1 intentionally ships only the mock provider. Non-mock providers are
    reserved for a future opt-in release.
    """
    normalized = (name or "mock").lower()
    if normalized == "mock":
        return MockProvider()
    if not enable_real_api:
        raise ProviderDisabledError(
            f"Provider '{name}' is disabled. v0.3.1 only enables the mock provider by default."
        )
    raise ProviderDisabledError(f"Provider '{name}' is not implemented in v0.3.1.")


def complete_with_cache(
    provider: BaseProvider,
    request: ProviderRequest,
    cache_dir: Path,
    api_usage_dir: Path | None = None,
) -> ProviderResponse:
    """Complete a request using a JSON cache and optionally write usage files."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    request_hash = request.request_hash()
    cache_path = cache_dir / f"{request_hash}.json"
    if cache_path.exists():
        cached = read_json(cache_path, default={}) or {}
        response = ProviderResponse(
            provider=str(cached.get("provider", provider.name)),
            model=str(cached.get("model", request.model)),
            task=str(cached.get("task", request.task)),
            content=str(cached.get("content", "")),
            request_hash=request_hash,
            cache_hit=True,
            status="cached",
            created_at=iso_now(),
        )
    else:
        response = provider.complete(request)
        write_json(cache_path, response.to_dict())

    if api_usage_dir is not None:
        api_usage_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = api_usage_dir / "api_usage.jsonl"
        append_usage_record(
            jsonl_path,
            {
                "timestamp": response.created_at,
                "provider": response.provider,
                "model": response.model,
                "task": response.task,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "cache_hit": response.cache_hit,
                "status": response.status,
                "request_hash": response.request_hash,
            },
        )
        write_json(api_usage_dir / "api_usage_summary.json", summarize_usage(read_usage_records(jsonl_path)))

    return response
