# 02 系统架构与模块边界

## 1. 文档状态与决策级别

本文件展开既有架构约束。标注“明确约束”的内容不得由实现者自行更改；标注“建议基线”的具体实现选择需要评审。

## 2. 部署拓扑

```text
┌──────────────────────── Windows 主机 ──────────────────────────┐
│ 浏览器 → Vue3 编译静态资源 → FastAPI 管理/API                    │
│                              │                                  │
│         SQLite 元数据 ───────┼────── 任务/数据/结果服务           │
│                              │                                  │
│         本机执行器/CLI ──────┴────── 共享 Python 核心包           │
└──────────────────────────────┬──────────────────────────────────┘
                               │ 任务 ZIP / 结果 ZIP
                      人工经堡垒机传递（第一阶段）
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│ Linux 主机：Docker Worker CLI → 包验证 → 共享核心包 → 本地持久化 │
│                              │                                  │
│                    挂载目录（状态、日志、结果）                   │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 明确约束

- Windows 是唯一 Web 管理端；默认在 `127.0.0.1:8000` 提供页面和 API。
- Windows 使用 Python/Conda，不需 Docker 或 Node.js 运行时。
- Vue/TypeScript 在构建阶段编译为静态资源；FastAPI 托管构建产物。
- Linux 只运行 Docker Worker；不需要浏览器访问 Linux，也不部署 FastAPI 管理端。
- 两端不假设网络互通；第一阶段离线交换标准 ZIP。
- Windows 关机或断网不能影响已在 Linux 启动的任务。
- 两端复用同一套核心 Python Engine、请求构建、指标计算和结果校验源码。
- SQLite 仅用于 Windows 管理端元数据；Worker 结果写其挂载目录。

### 2.2 建议的运行身份和路径

**建议基线：** Windows 数据、附件、任务包和结果包均存于显式配置的应用数据目录，不把用户当前目录作为根路径。Linux 将只读任务输入与可写输出目录分开挂载；运行容器使用非 root 用户，根文件系统只读（若所用依赖允许）。具体目录、UID/GID 和备份位置待部署环境确认。

## 3. 逻辑模块

```text
UI ──HTTP/WebSocket──> API 层 ──> Application Services ──> Domain/Core
                            │             │                   │
                            │             ├── SQLite           ├── Request Builder
                            │             ├── Package Service   ├── Dataset Reader
                            │             └── Run Coordinator   ├── Engine/Scheduler
                            │                                   ├── Validator/Metrics
                            └── Static Assets                   └── Result Schema

Worker CLI ──> Package Validator ──> Application Services ──> 同一 Domain/Core
                         │                                      │
                         └── Local State/Artifacts <────────────┘
```

| 模块 | 输入 | 输出 | 依赖规则 |
|---|---|---|---|
| Domain 模型 | 已验证字段 | 不可变任务/请求/结果对象 | 不依赖 Web、数据库或操作系统 shell |
| Request Builder | 请求定义、数据行、凭据运行时提供器 | HTTP 请求计划/流 | 不执行导入命令；敏感值只在发送时注入 |
| Dataset Reader | CSV/JSON/XLSX 等来源及映射 | 逐行结构化值和文件流 | 采用流式/分批读取；路径受根目录约束 |
| Engine | 任务快照、请求计划、执行策略 | 事件流、请求结果、汇总指标 | 与 FastAPI/UI 解耦；负责并发上限和取消 |
| Validator | 响应元信息/有限响应字段、规则 | 通过/失败/不适用及说明 | 规则版本化；不隐式调用 LLM/OCR |
| Persistence | 领域事件/结果 | SQLite 或 Worker 本地文件 | 通过接口隔离，不让 Engine 依赖管理 API |
| Package Service | 快照和数据/文件引用 | ZIP 包或解析对象 | 校验路径、大小、版本和哈希；无秘密 |
| FastAPI | HTTP 输入和 UI 请求 | JSON、静态资源、WebSocket 事件 | 仅 Windows 管理端 |
| Worker CLI | ZIP、挂载目录和本机秘密引用 | 本地 Run、日志、结果 ZIP | 不连接管理端，不运行 Web 服务 |

## 4. 依赖方向和代码组织建议

建议依赖方向为 `api/cli → application → domain/core`，持久化适配器和请求传输适配器实现核心定义的接口。核心引擎不导入 FastAPI、Vue、SQLite 驱动的具体实现或平台专用命令。

建议包布局：

```text
src/aiperf/
  domain/          # 任务、请求、数据集、Run、结果模型
  application/     # 创建、启动、取消、导入导出用例
  engine/          # 调度、并发、请求发送、指标、取消
  requests/        # 请求解析、模板、multipart、cURL 导入
  datasets/        # 文件识别、读取、字段映射、附件流
  validation/      # 规则模型和执行器
  packages/        # task/result ZIP 协议
  persistence/     # Windows SQLite 与 Worker 本地存储适配器
  api/             # FastAPI 路由、WebSocket、静态文件
  cli/             # 本机 CLI 和 Worker CLI 入口
```

这是目录建议，不要求每个目录首期都成为独立安装包。

## 5. 数据流

### 5.1 Windows 本机运行

用户输入 → API/Pydantic 校验 → 任务快照 → Run Coordinator → 共享 Engine → 请求构建/数据流 → 目标 API → 结果与事件 → SQLite/结果文件 → 页面快照/事件推送。

WebSocket 仅用于展示，不是任务执行的控制通道。断开页面不能取消或破坏任务；客户端重连应先获取 Run 快照，再接收后续事件。

### 5.2 Linux 离线运行

任务配置 → 导出前验证 → task manifest 与内容清单 → ZIP → Worker 安全解包到隔离目录 → schema/哈希/目标/凭据引用检查 → 共享 Engine → Worker 本地结果 → result ZIP → Windows 校验和导入。

Worker 不读取 Windows SQLite、不向 Windows 回连、不依赖管理端心跳。第一阶段不定义执行中实时回传。

## 6. 持久化边界

- Windows SQLite：API 配置（秘密引用除外）、请求定义、数据集元数据、任务版本、Run 索引、导入记录及必要聚合结果。
- Windows 文件存储：数据集源文件、附件、执行日志和导入包，按保留策略管理。
- Linux Worker：任务快照、状态、结构化结果和日志写入显式挂载目录。是否采用 JSONL、CSV 或 SQLite 由实现复杂度评估，默认建议 JSONL 追加写入加 summary JSON。
- ZIP 是交换格式，不是任一端的数据库备份，也不保证包含 Windows 管理历史。
- 所有时间戳以 UTC 保存，界面本地化显示。

## 7. 状态与故障边界

Task 是配置对象；Run 是一次执行实例。建议 Run 状态：`queued → validating → running → finalizing → completed`；终态还包括 `failed`、`cancelled`、`interrupted`。具体转移见 `03_EXECUTION_ENGINE.md`。

- UI/API 崩溃不应导致正在本机 Engine 执行的任务无记录；实现需明确是同进程任务还是独立本机进程。首期建议同进程后台任务，但重启恢复能力需单独验收。
- Windows 断电时，SQLite 事务保证元数据一致；逐条结果应可恢复到最后成功提交点。
- Worker 容器停止时，已写入的状态和结果保留在挂载卷；默认不承诺正在途中的请求可恢复或恰好执行一次。
- 包校验失败应在发送任何目标请求前终止。
- 目标服务异常仅影响当前 Run，不应损坏其他任务数据。

## 8. 安装和版本兼容

Windows 与 Worker 必须携带可识别的应用版本、Engine 版本、任务 Schema 版本和结果 Schema 版本。任务包应声明最低/最高兼容范围；Worker 在发现不支持的字段或版本时拒绝运行，不应静默忽略影响安全或执行含义的字段。详细格式见 `05_PACKAGE_PROTOCOL.md`。

## 9. 待确认

1. Windows API 是否永远只绑定 loopback；若局域网访问，认证和 TLS 如何提供。
2. Worker 是否支持单机多容器并行，及同一挂载卷的锁策略。
3. 本机 Windows 任务是同进程后台任务还是独立子进程；崩溃恢复目标是什么。
4. Worker 状态文件选 JSONL/SQLite 的最终方案和保留策略。
5. 允许的 CPU、内存、磁盘、文件大小和任务运行时上限。
