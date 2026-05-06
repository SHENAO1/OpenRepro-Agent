"""Built-in lightweight BOC-like demo runner."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import __version__
from .api_usage import write_mock_usage_files
from .artifact_manager import RunDirectory
from .config import get_demo_config, load_project_config
from .document_loader import load_source_index
from .utils import iso_now, read_yaml, relpath, safe_write_text, write_json, write_yaml


def _generate_prn_code(length: int, rng: np.random.Generator) -> np.ndarray:
    """Generate a bipolar pseudo-random spreading code."""
    return rng.choice(np.array([-1.0, 1.0]), size=length)


def _generate_square_subcarrier(total_samples: int, samples_per_chip: int, cycles_per_chip: int) -> np.ndarray:
    """Generate a simple square-wave subcarrier.

    This is a lightweight BOC-like placeholder, not a strict navigation-signal
    implementation.
    """
    samples = np.arange(total_samples)
    phase = 2.0 * np.pi * cycles_per_chip * samples / samples_per_chip
    return np.where(np.sin(phase) >= 0.0, 1.0, -1.0)


def generate_boc_like_signal(config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Generate a noisy BOC-like signal and its normalized autocorrelation."""
    seed = int(config.get("seed", 42))
    code_length = int(config.get("code_length", 128))
    samples_per_chip = int(config.get("samples_per_chip", 16))
    cycles_per_chip = int(config.get("subcarrier_cycles_per_chip", 2))
    noise_std = float(config.get("noise_std", 0.05))

    if code_length <= 0:
        raise ValueError("code_length must be positive")
    if samples_per_chip <= 1:
        raise ValueError("samples_per_chip must be greater than 1")
    if cycles_per_chip <= 0:
        raise ValueError("subcarrier_cycles_per_chip must be positive")
    if noise_std < 0:
        raise ValueError("noise_std must be non-negative")

    rng = np.random.default_rng(seed)
    code = _generate_prn_code(code_length, rng)
    spreading = np.repeat(code, samples_per_chip)
    subcarrier = _generate_square_subcarrier(spreading.size, samples_per_chip, cycles_per_chip)
    clean_signal = spreading * subcarrier
    noisy_signal = clean_signal + rng.normal(0.0, noise_std, clean_signal.size)
    correlation = np.correlate(noisy_signal, noisy_signal, mode="full")
    peak_abs = float(np.max(np.abs(correlation)))
    if peak_abs > 0:
        correlation = correlation / peak_abs

    meta = {
        "seed": seed,
        "code_length": code_length,
        "samples_per_chip": samples_per_chip,
        "subcarrier_cycles_per_chip": cycles_per_chip,
        "noise_std": noise_std,
    }
    return noisy_signal, correlation, meta


def _write_run_log(run_dirs: RunDirectory, lines: list[str]) -> None:
    run_log = run_dirs.logs / "run.log"
    safe_write_text(run_log, "\n".join(lines) + "\n")


def _write_correlation_figure(correlation: np.ndarray, path: Path) -> None:
    lags = np.arange(-(len(correlation) // 2), len(correlation) // 2 + 1)
    if len(lags) != len(correlation):
        lags = np.arange(len(correlation)) - int(np.argmax(np.abs(correlation)))
    fig = plt.figure(figsize=(8, 4.5))
    plt.plot(lags, correlation)
    plt.title("Lightweight BOC-like Autocorrelation")
    plt.xlabel("Lag (samples)")
    plt.ylabel("Normalized correlation")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _write_demo_report(run_dirs: RunDirectory, project_name: str, metrics: dict[str, Any], params: dict[str, Any]) -> Path:
    report = f"""# Demo Run Report

## 项目

{project_name}

## Demo 类型

Lightweight BOC-like signal demo。该 Demo 用于验证 OpenRepro-Agent v0.1.0 的实验闭环，不声称完整复现任何论文或工程级 BOC 捕获/跟踪算法。

## 已完成

- [x] 生成伪随机扩频码
- [x] 生成简单方波子载波
- [x] 合成 BOC-like 调制信号并添加噪声
- [x] 计算自相关函数
- [x] 保存数据、图表、日志、metadata、API usage 占位统计和 handoff

## 部分完成

- [ ] 仅实现自相关演示，尚未实现完整捕获/跟踪链路

## 未完成

- [ ] 论文级参数复现
- [ ] 多实验矩阵
- [ ] 与真实数据集或基准结果对比

## Demo 参数

```json
{params}
```

## 指标

```json
{metrics}
```

## 输出产物

- figures/correlation.png
- data/demo_signal.npy
- data/correlation.npy
- data/demo_metrics.json
- logs/run.log
- api_usage/api_usage.jsonl
- api_usage/api_usage_summary.json
- metadata.json

## 待确认

- 子载波定义是否匹配目标论文
- 码长、采样率、噪声模型是否匹配论文实验

## 下一步建议

将真实论文中的信号模型、参数表和评估协议填入 MODEL_LEDGER.md 与 EXPERIMENT_PLAN.md，再扩展 Demo Runner。
"""
    path = run_dirs.reports / "demo_report.md"
    safe_write_text(path, report)
    return path


def _write_run_handoff(run_dirs: RunDirectory, project_name: str, metrics: dict[str, Any]) -> None:
    content = f"""# Run Agent Handoff

## 项目

{project_name}

## 本次运行状态

- 已完成：lightweight BOC-like Demo 运行完成。
- 部分完成：产物齐全，但算法仅是 v0.1.0 演示版本。
- 未完成：论文级 BOC 捕获/跟踪复现、参数扫描、benchmark 对比。
- 待确认：真实论文模型和参数。

## 关键指标

- signal_length: {metrics.get('signal_length')}
- correlation_peak: {metrics.get('correlation_peak')}
- correlation_peak_index: {metrics.get('correlation_peak_index')}
- run_time_seconds: {metrics.get('run_time_seconds')}

## 下一步建议

1. 检查 `reports/demo_report.md` 与 `data/demo_metrics.json`。
2. 将模型假设同步到项目级 `handoff/MODEL_LEDGER.md`。
3. 为后续真实复现增加参数扫描和论文公式校验。
"""
    safe_write_text(run_dirs.handoff / "AGENT_HANDOFF.md", content)


def run_demo(project_dir: Path) -> dict[str, Any]:
    """Run the built-in BOC-like demo and save a complete artifact bundle."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    start = time.perf_counter()
    config = load_project_config(project_dir)
    project_name = config.get("project_name", project_dir.name)
    demo_config = get_demo_config(project_dir)
    run_dirs = RunDirectory.create(project_dir, project_name)

    log_lines = [
        f"[{iso_now()}] Starting OpenRepro-Agent demo run",
        f"Project: {project_name}",
        "Demo: lightweight BOC-like signal and autocorrelation",
    ]

    signal, correlation, resolved_params = generate_boc_like_signal(demo_config)
    np.save(run_dirs.data / "demo_signal.npy", signal)
    np.save(run_dirs.data / "correlation.npy", correlation)
    _write_correlation_figure(correlation, run_dirs.figures / "correlation.png")

    peak_index = int(np.argmax(np.abs(correlation)))
    metrics = {
        "signal_length": int(signal.size),
        "correlation_peak": float(correlation[peak_index]),
        "correlation_peak_index": peak_index,
        "run_time_seconds": 0.0,
        "generated_at": iso_now(),
    }

    safe_write_text(run_dirs.code / "README.md", """# Code Snapshot Placeholder

v0.1.0 records the demo algorithm in `src/openrepro/demo_runner.py` in the repository. This run directory keeps a lightweight note rather than copying the full source tree.
""")

    project_config_snapshot = project_dir / "project_config.yaml"
    if project_config_snapshot.exists():
        shutil.copy2(project_config_snapshot, run_dirs.configs / "project_config_snapshot.yaml")
    else:
        write_yaml(run_dirs.configs / "project_config_snapshot.yaml", config)

    api_summary = write_mock_usage_files(run_dirs.api_usage, task="run-demo")

    elapsed = time.perf_counter() - start
    metrics["run_time_seconds"] = round(float(elapsed), 6)
    write_json(run_dirs.data / "demo_metrics.json", metrics)

    source_index = load_source_index(project_dir)
    metadata = {
        "project_name": project_name,
        "openrepro_version": __version__,
        "run_id": run_dirs.root.name,
        "run_dir": str(run_dirs.root),
        "created_at": iso_now(),
        "demo_type": "lightweight_boc_like_autocorrelation",
        "demo_parameters": resolved_params,
        "metrics": metrics,
        "source_files": [s.get("source_name") for s in source_index.get("sources", [])],
        "artifact_paths": {
            "run_log": relpath(run_dirs.logs / "run.log", run_dirs.root),
            "figure": relpath(run_dirs.figures / "correlation.png", run_dirs.root),
            "signal": relpath(run_dirs.data / "demo_signal.npy", run_dirs.root),
            "correlation": relpath(run_dirs.data / "correlation.npy", run_dirs.root),
            "metrics": relpath(run_dirs.data / "demo_metrics.json", run_dirs.root),
            "demo_report": relpath(run_dirs.reports / "demo_report.md", run_dirs.root),
            "api_usage_summary": relpath(run_dirs.api_usage / "api_usage_summary.json", run_dirs.root),
        },
        "api_usage_summary": api_summary,
        "limitations": [
            "Demo is lightweight BOC-like only.",
            "No real model API was called.",
            "No benchmark result is claimed.",
        ],
    }
    write_json(run_dirs.root / "metadata.json", metadata)

    _write_demo_report(run_dirs, project_name, metrics, resolved_params)
    _write_run_handoff(run_dirs, project_name, metrics)
    log_lines.extend(
        [
            f"[{iso_now()}] Saved data and figure artifacts",
            f"[{iso_now()}] Saved mock API usage summary",
            f"[{iso_now()}] Completed run in {metrics['run_time_seconds']} seconds",
        ]
    )
    _write_run_log(run_dirs, log_lines)
    return metadata
