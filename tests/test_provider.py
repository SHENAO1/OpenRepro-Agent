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
