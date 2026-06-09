# OpenRepro-Agent

[English](README.md) | [简体中文](README.zh-CN.md)

OpenRepro-Agent 是一个用于构建可审计论文复现工作区的 Python CLI。它把笔记、证据、实验、输出、报告和交接文件放在同一个项目结构里，方便人类维护者和受控智能体继续推进工作，同时保留来源追踪。

当前版本：**v1.58.0**。本项目仍是 alpha 阶段的工程脚手架，不是全自动论文复现系统。

## 安装

```bash
git clone https://github.com/SHENAO1/OpenRepro-Agent.git
cd OpenRepro-Agent
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

需要 Python 3.10 或更高版本。

## 快速开始

运行内置 demo 工作流：

```bash
openrepro start random_search_demo
openrepro status random_search_demo
openrepro cockpit build random_search_demo --zip
```

常用审阅和交接命令：

```bash
openrepro evidence-graph random_search_demo
openrepro agent-task-spec random_search_demo
openrepro evidence-package random_search_demo --zip
openrepro bench-lite
```

demo 只产生流程证据和 toy 执行证据，不代表论文已经被完整复现。

## 手动流程

```bash
openrepro init my_repro
openrepro ingest my_repro --source path/to/paper_or_notes.pdf
openrepro analyze my_repro
openrepro plan my_repro
openrepro approve-candidates my_repro --all --reviewer human
openrepro scaffold-experiment my_repro --experiment-id baseline --template basic
openrepro run-experiment my_repro --experiment-id baseline --confirm
openrepro quality-gate my_repro --all
openrepro evidence-package my_repro --zip
```

完整命令请使用 `openrepro --help` 和 `openrepro <command> --help` 查看。

## 注意事项

- 默认不会调用真实模型 API；除非显式配置真实 provider，否则使用确定性的 mock provider。
- API key 从环境变量读取，不会写入项目文件。
- 公式、参数、数据集语义、实现选择和最终复现结论仍需要人工审阅。
- 不得伪造 benchmark 结果、使用量、成本估计、准确率提升或复现成功声明。

## 文档

- [路线图](ROADMAP.md)
- [架构](docs/architecture.md)
- [开发者指南](docs/developer_guide.md)
- [API 使用策略](API_USAGE.md)
- [贡献指南](CONTRIBUTING.md)

## 许可证

MIT
