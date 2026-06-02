"""Provider abstraction and deterministic cache-backed mock provider."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .api_usage import append_usage_record, summarize_usage, read_usage_records
from .utils import iso_now, read_json, slugify, truncate, write_json

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b[A-Za-z0-9_-]{32,}\b"),
]


def redact_text(text: str, max_chars: int = 500) -> str:
    """Return a compact preview with likely secrets redacted."""
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return truncate(redacted, max_chars)


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
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

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


class OpenAICompatibleProvider(BaseProvider):
    """Minimal OpenAI-compatible chat completions provider.

    It is available only when real APIs are explicitly enabled. The provider
    uses environment variables for secrets and does not estimate costs.
    """

    name = "openai"

    def __init__(
        self,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        endpoint: str = "https://api.openai.com/v1/chat/completions",
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.endpoint = endpoint

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ProviderDisabledError(
                f"Provider 'openai' requires environment variable {self.api_key_env}."
            )
        request_hash = request.request_hash()
        payload = {
            "model": request.model or self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": 0,
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderDisabledError(f"Provider 'openai' request failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise ProviderDisabledError(f"Provider 'openai' request failed: {exc.reason}") from exc

        choices = data.get("choices", [])
        content = ""
        if choices:
            content = str((choices[0].get("message") or {}).get("content") or "")
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        return ProviderResponse(
            provider=self.name,
            model=str(data.get("model") or request.model or self.model),
            task=request.task,
            content=content,
            request_hash=request_hash,
            cache_hit=False,
            status="completed",
            created_at=iso_now(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=0.0,
        )


class ProviderDisabledError(ValueError):
    """Raised when a non-mock provider is requested while real APIs are disabled."""


def get_provider(
    name: str = "mock",
    enable_real_api: bool = False,
    model: str | None = None,
    api_key_env: str = "OPENAI_API_KEY",
    endpoint: str | None = None,
) -> BaseProvider:
    """Return a provider instance.

    v0.4.0 keeps mock mode as the default. OpenAI-compatible calls are available
    only when real API use is explicitly enabled and secrets stay in env vars.
    """
    normalized = (name or "mock").lower()
    if normalized == "mock":
        return MockProvider()
    if normalized in {"openai", "openai-compatible"}:
        if not enable_real_api:
            raise ProviderDisabledError(
                f"Provider '{name}' is disabled. Set enable_real_api=true before making real calls."
            )
        return OpenAICompatibleProvider(
            model=model or "gpt-4.1-mini",
            api_key_env=api_key_env,
            endpoint=endpoint or "https://api.openai.com/v1/chat/completions",
        )
    if not enable_real_api:
        raise ProviderDisabledError(
            f"Provider '{name}' is disabled. Set enable_real_api=true before making real calls."
        )
    raise ProviderDisabledError(f"Provider '{name}' is not implemented in v0.4.0.")


def complete_with_cache(
    provider: BaseProvider,
    request: ProviderRequest,
    cache_dir: Path,
    api_usage_dir: Path | None = None,
    cache_enabled: bool = True,
    cache_ttl_seconds: int | None = None,
    redact_prompts: bool = True,
) -> ProviderResponse:
    """Complete a request using a JSON cache and optionally write usage files."""
    cache_namespace = "/".join(
        [
            slugify(provider.name),
            slugify(request.model or provider.model),
            slugify(request.task),
        ]
    )
    namespaced_cache_dir = cache_dir / cache_namespace
    namespaced_cache_dir.mkdir(parents=True, exist_ok=True)
    request_hash = request.request_hash()
    cache_path = namespaced_cache_dir / f"{request_hash}.json"
    cache_is_fresh = cache_path.exists()
    if cache_is_fresh and cache_ttl_seconds is not None:
        cache_age_seconds = max(0.0, time.time() - cache_path.stat().st_mtime)
        cache_is_fresh = cache_age_seconds <= cache_ttl_seconds
    if cache_enabled and cache_is_fresh:
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
        if cache_enabled:
            write_json(cache_path, response.to_dict())

    if api_usage_dir is not None:
        api_usage_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = api_usage_dir / "api_usage.jsonl"
        prompt_preview = redact_text(request.prompt) if redact_prompts else truncate(request.prompt, 500)
        response_preview = redact_text(response.content) if redact_prompts else truncate(response.content, 500)
        append_usage_record(
            jsonl_path,
            {
                "timestamp": response.created_at,
                "provider": response.provider,
                "model": response.model,
                "task": response.task,
                "prompt_tokens": 0 if response.cache_hit else response.prompt_tokens,
                "completion_tokens": 0 if response.cache_hit else response.completion_tokens,
                "total_tokens": 0 if response.cache_hit else response.total_tokens,
                "estimated_cost_usd": 0.0 if response.cache_hit else response.estimated_cost_usd,
                "cache_hit": response.cache_hit,
                "status": response.status,
                "request_hash": response.request_hash,
                "prompt_preview": prompt_preview,
                "response_preview": response_preview,
                "redaction_enabled": redact_prompts,
                "cache_enabled": cache_enabled,
                "cache_namespace": cache_namespace,
            },
        )
        write_json(api_usage_dir / "api_usage_summary.json", summarize_usage(read_usage_records(jsonl_path)))

    return response
