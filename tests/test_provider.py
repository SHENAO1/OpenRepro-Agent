from pathlib import Path

from openrepro.api_usage import read_usage_records, summarize_usage
from openrepro.config import configure_api_provider, provider_status
from openrepro.project_manager import init_project
from openrepro.provider import ProviderDisabledError, ProviderRequest, complete_with_cache, get_provider


def test_mock_provider_response_is_deterministic():
    provider = get_provider("mock")
    request = ProviderRequest(task="summary", prompt="Summarize BOC notes.")

    first = provider.complete(request)
    second = provider.complete(request)

    assert first.request_hash == second.request_hash
    assert first.content == second.content
    assert first.status == "mocked"


def test_provider_cache_records_miss_then_hit(tmp_path: Path):
    provider = get_provider("mock")
    request = ProviderRequest(task="summary", prompt="Summarize BOC notes.")
    cache_dir = tmp_path / "cache"
    api_usage_dir = tmp_path / "api_usage"

    first = complete_with_cache(provider, request, cache_dir, api_usage_dir)
    second = complete_with_cache(provider, request, cache_dir, api_usage_dir)

    records = read_usage_records(api_usage_dir / "api_usage.jsonl")
    summary = summarize_usage(records)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert summary["total_calls"] == 0
    assert summary["mock_events"] == 1
    assert summary["cached_events"] == 1
    assert summary["cache_hits"] == 1
    assert summary["cache_misses"] == 1
    assert first.request_hash in summary["request_hashes"]
    assert (cache_dir / "mock" / "mock-llm" / "summary" / f"{first.request_hash}.json").exists()


def test_provider_usage_redacts_prompt_and_response_previews(tmp_path: Path):
    provider = get_provider("mock")
    request = ProviderRequest(task="summary", prompt="api_key=sk-testsecret1234567890 user=a@example.com")
    cache_dir = tmp_path / "cache"
    api_usage_dir = tmp_path / "api_usage"

    complete_with_cache(provider, request, cache_dir, api_usage_dir)

    records = read_usage_records(api_usage_dir / "api_usage.jsonl")
    record = records[0]

    assert "sk-testsecret" not in record["prompt_preview"]
    assert "a@example.com" not in record["prompt_preview"]
    assert "[REDACTED_SECRET]" in record["prompt_preview"]
    assert record["redaction_enabled"] is True
    assert record["cache_namespace"] == "mock/mock-llm/summary"


def test_provider_cache_can_be_disabled(tmp_path: Path):
    provider = get_provider("mock")
    request = ProviderRequest(task="summary", prompt="Summarize BOC notes.")
    cache_dir = tmp_path / "cache"
    api_usage_dir = tmp_path / "api_usage"

    first = complete_with_cache(provider, request, cache_dir, api_usage_dir, cache_enabled=False)
    second = complete_with_cache(provider, request, cache_dir, api_usage_dir, cache_enabled=False)
    records = read_usage_records(api_usage_dir / "api_usage.jsonl")

    assert first.cache_hit is False
    assert second.cache_hit is False
    assert not list(cache_dir.rglob("*.json"))
    assert all(record["cache_enabled"] is False for record in records)


def test_openai_provider_requires_explicit_enable():
    try:
        get_provider("openai")
    except ProviderDisabledError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("Expected ProviderDisabledError")


def test_configure_provider_records_status_without_secret(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    config = configure_api_provider(
        project,
        provider="openai",
        model="gpt-test",
        enable_real_api=True,
        api_key_env="OPENAI_API_KEY",
    )
    status = provider_status(project)

    assert config["default_provider"] == "openai"
    assert status["enable_real_api"] is True
    assert status["api_key_present"] is False
    assert status["ready_for_real_calls"] is False
    assert status["cache_enabled"] is True
    assert status["redact_prompts"] is True
