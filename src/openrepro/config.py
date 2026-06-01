"""Project configuration helpers."""

from __future__ import annotations

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

    v0.2.0 keeps real model calls disabled by default.  The fields are kept so
    later releases can add providers without changing the project schema.
    """

    default_provider: str = "mock"
    default_model: str = "mock-llm"
    enable_real_api: bool = False


@dataclass
class AnalysisConfig:
    """Rule/mock analyzer configuration."""

    analyzer_version: str = "v0.2.0-rule"
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
