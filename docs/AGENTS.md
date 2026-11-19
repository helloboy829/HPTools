# AGENTS.md — Codex 项目开发指令

你正在开发 AI-PERF，一个用于内网 AI 组件/API 的跨平台性能测试平台。请把本文件和 `docs/` 目录视为项目需求基线。

## A. 开发前必须完成
- 完整阅读根目录 `README.md` 和 `docs/` 所有文档。
- 不要仅凭 README 开始编码。
- 先输出需求理解、架构图、数据模型、模块边界、风险和分期计划。
- 如果仓库已有代码，先检查现状，不要覆盖或重写无关实现。
- 任何不确定的需求列为问题，不得擅自假设。

## B. 不可违反的架构约束
1. Windows 是唯一 Web 管理端，FastAPI 提供 API 和 Vue 编译后的静态页面。
2. Windows 使用 Python/Conda 运行，不依赖 Docker、Node.js 运行时、Redis、MySQL。
3. Linux 仅运行 Docker Worker，不部署 Web 管理端。
4. Windows 本机和 Linux Worker 必须复用同一份核心 Python Engine。
5. 第一阶段跨机通信使用标准 ZIP 任务包/结果包，不依赖两端网络互通。
6. Linux Worker 必须能脱离 Windows 独立运行，任务开始后不能依赖管理端心跳。
7. SQLite 用于 Windows 管理端元数据；Linux Worker 的任务状态和结果落盘到挂载目录中的 JSON/CSV/SQLite（按实现复杂度选最简单可靠方案），不能要求共享 Windows 数据库。
8. 并发默认最大 100，配置值必须做服务端校验；不得仅在前端限制。
9. 不得把真实密钥写入日志、普通配置导出、任务 ZIP、错误明细或报告。
10. 不得默认对未知 IP/域名发起压测；必须有用户确认/目标授权提示和目标地址校验。

## C. 跨平台编码规则
- Python 3.11+，使用 `pathlib.Path` 管理路径。
- 使用 UTF-8；处理 Windows 中文路径、空格、反斜杠。
- 不使用 `bash`、`ps`、`kill` 等 Linux 命令作为核心业务实现。
- 不依赖当前工作目录；所有路径由配置/应用根目录解析。
- 文件名不能直接拼接用户输入形成任意路径；必须防止路径穿越。
- 文件流式读取和上传；禁止将所有附件一次性读入内存。
- 临时文件、文件句柄、aiohttp Session/Connector 必须有明确生命周期。
- 统一使用 UTC 时间存储，前端按本地时区显示。
- 统一错误码、日志字段和结果 Schema。
- 对 aiohttp、FastAPI、SQLite 等依赖锁定版本；Windows 与 Linux 离线依赖分别构建。

## D. 代码质量
- 核心 Engine 与 Web/API 层分离；Engine 不导入 FastAPI。
- 所有外部输入都做 Pydantic/等价模型校验。
- 重要逻辑必须有单元测试；文件/请求链路有集成测试。
- 每个阶段完成后执行格式检查、静态检查、单元测试。
- 不得吞异常；错误必须归类、记录并进入结果。
- 日志默认脱敏 Authorization、Cookie、Token、Secret、密码、签名。
- 不在代码、示例、测试数据中使用真实内网密钥或真实生产凭据。

## E. 推荐开发顺序
1. 仓库骨架、配置、日志、跨平台路径、数据模型。
2. 请求定义与 curl 导入。
3. 数据集/文件管理和 Request Builder。
4. 统一 Engine、并发控制、指标、错误处理。
5. Result Validator、报告数据模型。
6. Windows FastAPI + Vue 管理端。
7. CLI、任务包/结果包协议。
8. Linux Docker Worker。
9. 离线安装包、跨平台验收。
10. SSH/SFTP 自动化（后续，不阻塞前九项）。

## F. 不允许的实现捷径
- 不要把每个测试用例写成硬编码 Python 脚本。
- 不要只支持 JSON；必须考虑 multipart、多文件、表单、原始文本、二进制和多步骤工作流。
- 不要用单纯 HTTP 200 判断业务成功。
- 不要把任务 ZIP 当作数据库备份。
- 不要将 Linux Worker 做成必须连接 Windows 才能运行的远程 Agent。
- 不要在第一期引入 Ray/Celery/Redis/Kafka 来实现 100 并发。
- 不要宣称“实时监控 Linux 任务”，除非真实实现了可用的数据回传通道；第一期 Linux 任务是离线执行、执行日志本地查看、结果包回传。
- 不要把静态 HTML 报告误认为 Linux Web 管理端。

## G. 每次提交/阶段交付说明
说明：
- 实现了哪些功能；
- 修改了哪些文件；
- 如何运行；
- 如何测试；
- 测试结果；
- 尚未实现/已知限制；
- 对 Windows 和 Linux 分别验证了什么。
