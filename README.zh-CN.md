# OpenRepro-Agent

[English](README.md) | [简体中文](README.zh-CN.md)

OpenRepro-Agent 是一个用于构建可审计论文复现工作区的 Python CLI。它帮助你导入论文或笔记、提取候选证据、生成受保护的实验脚手架、运行 toy 或已验证流程、校验产物，并打包给人类维护者或代码代理继续接手。

当前版本：**v1.58.0**。本项目仍是 alpha 阶段的工程脚手架，不是全自动论文复现系统。

## 为什么做

论文复现经常失败，不是因为单个脚本缺失，而是因为笔记、公式、假设、数据、代码、日志和审阅决策分散在不同文件夹或聊天记录里。OpenRepro-Agent 的目标是把这些材料放进一个可运行、可检查、可交接的项目结构中，并明确标记哪些内容已验证、缺失、过期或仍需人工审阅。

## 亮点

- 为论文笔记、配置、数据、实验、输出、报告和交接文件提供统一项目结构。
- 支持 Markdown、文本和 PDF 导入，并保留来源追踪。
- 基于规则提取公式候选、参数候选和论文证据。
- 在生成实验脚手架前加入人工候选审阅门禁。
- 支持实验规格、输入校验、运行 manifest、质量门禁和运行对比。
- 支持数据集卡片、轻量数据质量门禁、lineage、claim trace、统一 evidence graph、readiness review 和 evidence package。
- 支持 runner-neutral 的受控智能体任务合同，并提供显式结果 schema 和护栏。
- 提供静态审阅界面，包括 dashboard、evidence explorer 和 reproduction cockpit。
- 默认使用 mock provider；真实 OpenAI-compatible API 需要显式启用。
- 内置 starter workflow 和 OpenRepro-Bench Lite，用于可重复的流程检查。

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

运行内置的 random-search toy paper 工作流：

```bash
openrepro start random_search_demo
```

该命令会创建项目、导入内置笔记、分析候选公式和参数、生成受保护的实验脚手架、运行实验、执行质量门禁，并写入报告和交接文件。

常用后续命令：

```bash
openrepro status random_search_demo
openrepro cockpit build random_search_demo --zip
openrepro evidence-graph random_search_demo
openrepro agent-task-spec random_search_demo
openrepro evidence-package random_search_demo --zip
openrepro bench-lite
```

这些输出只代表流程证据和 toy 执行证据，不代表论文已经被完整复现。

## API 配置

OpenRepro 默认使用确定性的 mock provider。除非显式启用真实 API 并通过环境变量提供密钥，否则不会发起真实模型调用。

Mock 模式：

```bash
openrepro configure-provider random_search_demo --provider mock --disable-real-api
```

OpenAI-compatible API：

```bash
openrepro configure-provider random_search_demo \
  --provider openai \
  --model gpt-4.1-mini \
  --enable-real-api \
  --api-key-env OPENAI_API_KEY \
  --endpoint https://api.openai.com/v1/chat/completions
```

在运行真实 provider 调用前设置环境变量：

```bash
export OPENAI_API_KEY="<your-api-key>"
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
```

第三方 OpenAI-compatible 服务需要传入完整的 chat completions endpoint。如果服务给出的 Base URL 是 `https://example.com/v1`，则应配置为 `https://example.com/v1/chat/completions`。

Token Plan 示例：

```powershell
$env:OPENREPRO_API_KEY = "<your-token-plan-api-key>"
openrepro configure-provider random_search_demo `
  --provider openai `
  --model mimo-v2.5 `
  --enable-real-api `
  --api-key-env OPENREPRO_API_KEY `
  --endpoint https://token-plan-cn.xiaomimimo.com/v1/chat/completions
```

OpenRepro 只会把 provider 名称、模型名、endpoint、缓存策略、脱敏策略和 API-key 环境变量名写入 `project_config.yaml`，不会保存 API key 的真实值。

## 核心流程

手动项目通常按下面的路径推进：

```bash
openrepro init my_repro
openrepro ingest my_repro --source path/to/paper_or_notes.pdf
openrepro analyze my_repro
openrepro plan my_repro
openrepro list-candidates my_repro
openrepro approve-candidates my_repro --all --reviewer human
openrepro scaffold-experiment my_repro --experiment-id baseline --template basic
openrepro validate-experiment-spec my_repro --experiment-id baseline
openrepro run-experiment my_repro --experiment-id baseline --confirm
openrepro quality-gate my_repro --all
openrepro evidence-package my_repro --zip
```

完整命令参考请使用：

```bash
openrepro --help
openrepro <command> --help
```

## 主要产物

- `workspace/`：分析、候选审阅、数据质量、lineage、readiness 和工作流状态产物。
- `experiments/`：受保护的实验脚手架和实验规格。
- `outputs/`：带时间戳的运行输出、指标、日志、manifest 和质量门禁。
- `reports/`：报告、dashboard、evidence package、review site 和 cockpit。
- `handoff/`：给人类维护者和代码代理的交接文件。
- `benchmarks/`：workflow-compliance benchmark 任务和索引。

## 文档

- [路线图](ROADMAP.md)
- [架构](docs/architecture.md)
- [开发者指南](docs/developer_guide.md)
- [API 使用策略](API_USAGE.md)
- [贡献指南](CONTRIBUTING.md)

## 当前限制

OpenRepro-Agent 不能完整阅读或理解论文，不能自动验证数学公式，不能自动验证数据集语义，不能为任意论文生成完整仿真代码，也不能宣称科学复现成功。公式、参数、数据语义、实现选择和最终复现结论都需要人工审阅。

## 不伪造结果策略

项目不得伪造 benchmark 结果、用户数量、token 用量、成本估计、准确率提升、效率提升，也不得宣称轻量 demo 等同于完整论文复现。

## 许可证

MIT
