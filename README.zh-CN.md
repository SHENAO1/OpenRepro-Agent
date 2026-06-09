# OpenRepro-Agent

[English](README.md) | [简体中文](README.zh-CN.md)

OpenRepro-Agent 是一个用于构建可审计论文复现工作区的 Python CLI。它帮助你把论文笔记、候选公式、实验脚手架、运行证据、校验输出和交接文件放进同一个可复现项目结构中。

`main` 当前版本：**v1.26.0**。本项目仍是 alpha 阶段的工程脚手架，不是全自动论文复现系统。

## 为什么做

论文复现经常失败，不是因为单个脚本缺失，而是因为笔记、假设、公式、数据集、代码、日志和审阅决策分散在不同文件夹或聊天记录里。OpenRepro-Agent 关注的是让复现流程可运行、可检查，并明确标记哪些内容已验证、缺失、过期或仍需人工审阅。

## 亮点

- 为 sources、configs、data、experiments、outputs、reports 和 handoff 文件提供统一项目结构。
- 支持 Markdown、文本和 PDF 导入，并保留来源追踪。
- 基于规则提取公式候选和参数候选。
- 在实验脚手架生成前加入人工候选审批门禁。
- 支持实验规格、输入校验、运行 manifest、质量门禁和运行对比。
- 支持数据注册、运行 lineage、claim trace、readiness scorecard 和 evidence package。
- 生成 review site、dashboard、reviewer packet 和 collaboration pack 等静态审阅产物。
- 默认使用 mock provider；真实 OpenAI-compatible API 需要显式启用。
- 支持 workflow-compliance benchmark 和 benchmark suite。

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

使用内置的 BOC 风格笔记运行一个小型本地流程：

```bash
openrepro init boc_demo
openrepro configure-provider boc_demo --provider mock --disable-real-api
openrepro ingest boc_demo --source examples/boc_notes.md
openrepro analyze boc_demo
openrepro plan boc_demo
openrepro list-candidates boc_demo
openrepro approve-candidates boc_demo --all --reviewer human
openrepro scaffold-experiment boc_demo --experiment-id boc_candidate_exp --template boc-like
openrepro validate-inputs boc_demo --experiment-id boc_candidate_exp
openrepro validate-experiment-spec boc_demo --experiment-id boc_candidate_exp
openrepro run-experiment boc_demo --experiment-id boc_candidate_exp --confirm
openrepro quality-gate boc_demo --all
openrepro evidence-package boc_demo --zip
openrepro status boc_demo
```

这些输出只代表流程证据和 toy 执行证据，不代表论文已经被完整复现。

## API 配置

OpenRepro 默认使用确定性的 mock provider。除非显式启用真实 API 并通过环境变量提供密钥，否则不会发起真实模型调用。

Mock 模式：

```bash
openrepro configure-provider boc_demo --provider mock --disable-real-api
```

OpenAI-compatible API：

```bash
openrepro configure-provider boc_demo \
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
openrepro configure-provider boc_demo `
  --provider openai `
  --model mimo-v2.5 `
  --enable-real-api `
  --api-key-env OPENREPRO_API_KEY `
  --endpoint https://token-plan-cn.xiaomimimo.com/v1/chat/completions
```

OpenRepro 只会把 provider 名称、模型名、endpoint、缓存策略、脱敏策略和 API-key 环境变量名写入 `project_config.yaml`，不会保存 API key 的真实值。

## 主要产物

- `workspace/`：分析、候选审阅、校验、lineage、readiness 和工作流状态产物。
- `experiments/`：受保护的实验脚手架和实验规格。
- `outputs/`：带时间戳的运行输出、指标、日志、manifest 和质量门禁。
- `reports/`：报告、evidence package、dashboard 和审阅产物。
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
