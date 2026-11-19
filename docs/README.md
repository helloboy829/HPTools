# AI-PERF：AI 组件 API 性能测试平台

> 本目录是交给 Codex 阅读和执行的项目需求、架构、接口、数据格式、部署与验收基线。
> 目标不是生成一份概念 Demo，而是实现一个能在受限内网环境中长期使用的工具。

## 1. Codex 首先阅读什么

按以下顺序完整阅读，不要只读本文件：

1. `AGENTS.md`：Codex 的开发约束与工作方式。
2. `docs/01_PRODUCT_REQUIREMENTS.md`：产品目标、用户流程、功能范围。
3. `docs/02_ARCHITECTURE.md`：最终部署架构和模块边界。
4. `docs/03_EXECUTION_ENGINE.md`：压测模型、并发、指标、事务定义。
5. `docs/04_DATASET_AND_REQUESTS.md`：数据集、文件、多文件、curl、请求构建。
6. `docs/05_PACKAGE_PROTOCOL.md`：Windows 与 Linux 的离线任务包/结果包协议。
7. `docs/06_API_AND_UI.md`：管理端 API 与网页页面要求。
8. `docs/07_DEPLOYMENT_OFFLINE.md`：Windows Conda、Linux Docker、离线依赖交付。
9. `docs/08_SECURITY_AND_RELIABILITY.md`：凭据、文件安全、错误处理、恢复。
10. `docs/09_ROADMAP_AND_ACCEPTANCE.md`：分期开发、验收标准和测试清单。
11. `docs/10_SOURCE_WORKBOOK_NOTES.md`：已提供的《AI组件测试对象清单》实际结构与适配注意事项。

## 2. 产品一句话定义

AI-PERF 是一个面向内网 AI API / AI 组件的跨平台性能测试工具。用户通过 Windows 浏览器管理 API、测试数据集和任务；任务可在 Windows 本机执行，也可打包后通过堡垒机 SSH/SFTP 传到 Linux Docker Worker 执行；执行结果再回传 Windows 统一查看、比较和导出。

## 3. 最终架构决策（不可擅自改成其他方案）

- Windows 是唯一的 Web 管理端：Python + Conda 启动 FastAPI，浏览器访问 `http://127.0.0.1:8000`。
- Windows 本机同时可以执行压测任务。
- Linux 不部署 Web 管理端，不要求本地浏览器能访问 Linux。
- Linux 仅部署 Docker Worker，通过 CLI 接收任务包、执行任务、导出结果包。
- Windows 与 Linux 不假设网络互通；第一期采用离线任务包双向传输。
- 文件传输路径为人工经堡垒机 SSH/SFTP 上传、下载；自动化 SSH/SFTP 是后续阶段，必须适配堡垒机审批/MFA/命令限制。
- Windows 与 Linux 必须共用同一套 Python 核心压测引擎、请求构建、指标计算和结果校验代码。
- 两端独立运行：Windows 关机、断网后，Linux 已启动的任务仍能继续执行并在 Linux 本地保存结果。
- 第一阶段默认并发上限 100，必须可配置并有硬上限保护；不能默认无限并发。
- 不引入 Redis、Kafka、Celery、Ray、MySQL 等非必要基础设施。
- Web 前端使用 Vue3/TypeScript 开发，但最终编译为静态文件，由 FastAPI 提供；Windows 运行时不需要 Node.js。
- Windows 运行不需要 Docker；Linux 运行依赖 Docker。

## 4. 核心产品流程

### Windows 本机执行
创建任务 -> 选择 Windows -> 选择 API/数据集 -> 配置并发/请求数/超时 -> 本机 Engine 执行 -> WebSocket 实时展示 -> 保存结果/报告。

### Linux 执行
创建任务 -> 选择 Linux -> 校验任务配置与数据集 -> 导出任务 ZIP -> 经堡垒机上传 Linux -> Linux Worker 校验并执行 -> 生成结果 ZIP -> 经堡垒机下载 -> Windows 导入结果 ZIP -> 统一报告展示。

## 5. 当前明确的边界

- 工具负责发送请求、测量性能、检查可配置的业务成功条件；不自动理解所有 AI 输出是否正确。
- AI 输出质量的深度评估（LLM-as-a-judge、OCR、语义评分）不是第一期默认能力。第一期先提供可配置规则和人工核验字段。
- 对 PDF/Word/Excel/图片的压测，必须保留真实文件上传链路。除非用户明确选择“预处理文本模式”，否则不得将 PDF 转成文本后替代原始文件上传。
- “解析文件格式”首先是文件识别、校验、预览、字段映射和用例关联，不等于一定要 OCR 或抽取全部正文。
- 任务包中不得明文保存真实 Token、Secret Key、HMAC 密钥等凭据。
- 目标 API 地址由用户显式配置；不能自动扫描网段或对未知目标发起压力测试。

## 6. 给 Codex 的首轮任务

先阅读全部文档，输出：
1. 需求理解摘要；
2. 模块依赖图；
3. 建议的仓库目录结构；
4. 数据库 ER 草图；
5. 关键数据模型；
6. 分阶段实施计划；
7. 文档中存在的冲突、缺失和需要用户确认的问题。

不要一开始就生成一大坨代码。确认设计后，先搭建可运行骨架和自动化测试，再按阶段开发。不得悄悄改变本文档中的架构决策。
