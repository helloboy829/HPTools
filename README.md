# AI-PERF

<p align="center">
  <img src="icon/logo.png" alt="AI-PERF logo" width="180">
</p>

AI-PERF 是面向内网 AI API / AI 组件的跨平台性能测试平台。它提供 Windows 本机管理端和执行能力，并通过离线任务包与 Linux Docker Worker 交换任务和结果。

## 文档入口

- [项目需求、架构与工作流总览](docs/README.md)
- [Codex 开发约束](docs/AGENTS.md)
- [文档目录](docs/INDEX.md)
- [产品需求规格](docs/01_PRODUCT_REQUIREMENTS.md)
- [系统架构](docs/02_ARCHITECTURE.md)
- [执行引擎](docs/03_EXECUTION_ENGINE.md)
- [数据集与请求构建](docs/04_DATASET_AND_REQUESTS.md)
- [任务包/结果包协议](docs/05_PACKAGE_PROTOCOL.md)
- [管理端 API 与 UI](docs/06_API_AND_UI.md)
- [部署与离线交付](docs/07_DEPLOYMENT_OFFLINE.md)
- [安全与可靠性](docs/08_SECURITY_AND_RELIABILITY.md)
- [路线图与验收](docs/09_ROADMAP_AND_ACCEPTANCE.md)
- [源工作簿适配说明](docs/10_SOURCE_WORKBOOK_NOTES.md)
- [ZIP 协议 JSON Schema 草案](schemas/1.0/)

## 核心架构边界

- Windows 是唯一 Web 管理端；FastAPI 提供 API 和 Vue 编译后的静态资源。
- Windows 使用 Python/Conda，可在本机运行任务；运行时不依赖 Docker 或 Node.js。
- Linux 只运行 Docker Worker，不部署 Web 管理端。
- Windows 与 Linux 共用同一套核心 Python Engine。
- 第一阶段通过标准 ZIP 任务包/结果包离线交换，不依赖两端网络互通。
- 第一阶段并发硬上限为 100；自动 SSH/SFTP 传输属于后续阶段。
- 真实凭据不能进入普通配置导出、任务包、日志、错误明细或报告。

## 文档状态

`docs/01_*` 至 `docs/10_*` 是供评审和实施使用的详细规格基线。凡现有项目资料没有明确依据的产品选择，都在文档中标注为“建议基线”或“待确认”，不能视为已经由业务方确认。源工作簿尚未随当前目录提供，因此 `docs/10_SOURCE_WORKBOOK_NOTES.md` 不声称掌握其真实表头或字段。

## 本地开发

需要 Python 3.11 或更高版本。首期基础测试使用标准库：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests/unit -v
```

POSIX shell:

```sh
PYTHONPATH=src python -m unittest discover -s tests/unit -v
```
