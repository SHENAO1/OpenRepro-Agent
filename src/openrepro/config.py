"""Project configuration helpers."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .utils import iso_now, read_yaml, write_yaml

CONFIG_FILE = "project_config.yaml"


@dataclass
class DemoConfig:
    """Lightweight BOC-like demo parameters."""

    seed: int = 42
    code_length: int = 128
    samples_per_chip: int = 16
    subcarrier_cycles_per_chip: int = 2
    noise_std: float = 0.05
    output_name: str = "boc_demo"


@dataclass
class APIConfig:
    """API provider configuration.

    v0.4.0 keeps real model calls disabled by default.  Real providers must be
    explicitly enabled in project configuration and backed by environment keys.
    """

    default_provider: str = "mock"
    default_model: str = "mock-llm"
    enable_real_api: bool = False
    api_key_env: str = "OPENAI_API_KEY"
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    cache_enabled: bool = True
    cache_ttl_seconds: int | None = None
    redact_prompts: bool = True


@dataclass
class AnalysisConfig:
    """Rule/mock analyzer configuration."""

    analyzer_version: str = "v1.14.0-rule"
    max_source_preview_chars: int = 4000


@dataclass
class ProjectConfig:
    """Top-level project configuration."""

    project_name: str
    version: str = __version__
    created_at: str = field(default_factory=iso_now)
    description: str = "Paper reproduction project managed by OpenRepro-Agent."
    demo: DemoConfig = field(default_factory=DemoConfig)
    api: APIConfig = field(default_factory=APIConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_CONFIG: dict[str, Any] = ProjectConfig(project_name="openrepro_project").to_dict()


def create_project_config(project_name: str) -> ProjectConfig:
    """Create a default config object for a new project."""
    return ProjectConfig(project_name=project_name)


def save_project_config(project_dir: Path, config: ProjectConfig | dict[str, Any], overwrite: bool = True) -> bool:
    """Save project_config.yaml."""
    data = config.to_dict() if isinstance(config, ProjectConfig) else config
    return write_yaml(project_dir / CONFIG_FILE, data, overwrite=overwrite)


def load_project_config(project_dir: Path) -> dict[str, Any]:
    """Load project_config.yaml, returning a sane default when missing."""
    data = read_yaml(project_dir / CONFIG_FILE, default=None)
    if data is None:
        project_name = project_dir.name
        return create_project_config(project_name).to_dict()
    return data


def get_demo_config(project_dir: Path) -> dict[str, Any]:
    """Return demo configuration with defaults filled in."""
    config = load_project_config(project_dir)
    demo = DemoConfig().__dict__.copy()
    demo.update(config.get("demo", {}) or {})
    return demo


def get_api_config(project_dir: Path) -> dict[str, Any]:
    """Return API provider configuration with defaults filled in."""
    config = load_project_config(project_dir)
    api = APIConfig().__dict__.copy()
    api.update(config.get("api", {}) or {})
    return api


def configure_api_provider(
    project_dir: Path,
    provider: str,
    model: str | None = None,
    enable_real_api: bool | None = None,
    api_key_env: str | None = None,
    endpoint: str | None = None,
    cache_enabled: bool | None = None,
    cache_ttl_seconds: int | None = None,
    redact_prompts: bool | None = None,
) -> dict[str, Any]:
    """Update project API provider configuration without storing secrets."""
    config = load_project_config(project_dir)
    api = get_api_config(project_dir)
    api["default_provider"] = provider
    if model is not None:
        api["default_model"] = model
    if enable_real_api is not None:
        api["enable_real_api"] = bool(enable_real_api)
    if api_key_env is not None:
        api["api_key_env"] = api_key_env
    if endpoint is not None:
        api["endpoint"] = endpoint
    if cache_enabled is not None:
        api["cache_enabled"] = bool(cache_enabled)
    if cache_ttl_seconds is not None:
        api["cache_ttl_seconds"] = int(cache_ttl_seconds)
    if redact_prompts is not None:
        api["redact_prompts"] = bool(redact_prompts)
    config["api"] = api
    save_project_config(project_dir, config)
    return api


def provider_status(project_dir: Path) -> dict[str, Any]:
    """Return provider status without exposing secret values."""
    api = get_api_config(project_dir)
    key_env = str(api.get("api_key_env") or "OPENAI_API_KEY")
    provider = str(api.get("default_provider") or "mock")
    real_enabled = bool(api.get("enable_real_api", False))
    return {
        "schema_version": "0.4.0",
        "default_provider": provider,
        "default_model": str(api.get("default_model") or "mock-llm"),
        "enable_real_api": real_enabled,
        "api_key_env": key_env,
        "api_key_present": bool(os.environ.get(key_env)),
        "endpoint": str(api.get("endpoint") or ""),
        "cache_enabled": bool(api.get("cache_enabled", True)),
        "cache_ttl_seconds": api.get("cache_ttl_seconds"),
        "redact_prompts": bool(api.get("redact_prompts", True)),
        "ready_for_real_calls": provider != "mock" and real_enabled and bool(os.environ.get(key_env)),
        "policy": "Real provider calls require explicit opt-in and environment-backed secrets.",
    }
