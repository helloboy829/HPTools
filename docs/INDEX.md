# 文档目录

| 文件 | 内容 |
|---|---|
| 根目录 `README.md` | 仓库入口与文档导航 |
| `docs/README.md` | 项目总览、最终架构决策、Codex 阅读顺序 |
| 根目录 `AGENTS.md` / `docs/AGENTS.md` | 项目级入口和详细 Codex 开发约束 |
| `docs/CODEX_FIRST_PROMPT.md` | 可直接交给 Codex 的启动提示词 |
| `docs/01_PRODUCT_REQUIREMENTS.md` | 产品目标、用户流程、功能需求、范围和术语 |
| `docs/02_ARCHITECTURE.md` | 部署拓扑、模块边界、数据流和故障边界 |
| `docs/03_EXECUTION_ENGINE.md` | 并发模型、执行语义、指标、状态和错误分类 |
| `docs/04_DATASET_AND_REQUESTS.md` | 数据集、文件、请求构建、cURL 导入和 Dify 工作流 |
| `docs/05_PACKAGE_PROTOCOL.md` | 任务包/结果包目录、字段、校验和兼容规则 |
| `docs/06_API_AND_UI.md` | Web API、WebSocket 事件、页面与交互要求 |
| `docs/07_DEPLOYMENT_OFFLINE.md` | Windows/Linux 部署、离线依赖、升级和运维 |
| `docs/08_SECURITY_AND_RELIABILITY.md` | 凭据、目标授权、文件安全、错误处理和恢复 |
| `docs/09_ROADMAP_AND_ACCEPTANCE.md` | 分期交付、验收门槛和测试矩阵 |
| `docs/10_SOURCE_WORKBOOK_NOTES.md` | 源工作簿核验流程、字段映射和导入约束 |
| `docs/11_REAL_PROJECT_PATTERN_ANALYSIS.md` | 本机真实评测项目抽查、对象边界澄清和待确认项 |

### 协议 Schema

`schemas/1.0/` 保存任务包 manifest、task、结果摘要和逐请求记录的 JSON Schema 草案，详见 [`docs/05_PACKAGE_PROTOCOL.md`](05_PACKAGE_PROTOCOL.md)。
