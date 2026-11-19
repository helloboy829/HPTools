# 05 任务包与结果包协议

## 1. 目标和兼容原则

任务包与结果包是 Windows 和 Linux Worker 之间的离线交换格式，不是数据库备份或执行中通信协议。协议必须可校验、可版本化、可审计，并且在任何目标请求发送前完成完整的安全校验。

协议名称建议为 `aiperf-task` 和 `aiperf-result`。首个正式版本草案为 `1.0`；在评审冻结前字段仍属建议。未知且影响执行含义的字段不得静默忽略。接收端不支持的主版本应拒绝；次版本兼容策略应由 Schema 和 capability 明确。

## 2. ZIP 目录结构

### 2.1 任务包

```text
<package-id>.aiperf-task.zip
├── manifest.json
├── task.json
├── datasets/<dataset-version-id>.jsonl
├── assets/<asset-id>                 # 原始字节，不按用户文件名落盘
└── checksums.sha256
```

`manifest.files` 是文件清单权威来源，列出除 `manifest.json` 和 `checksums.sha256` 外的所有载荷文件、大小和 SHA-256。`checksums.sha256` 逐行列出 `manifest.json` 与所有载荷文件的散列，用于在没有解析 ZIP 的情况下检查转运完整性；它不列出自身，因此不存在自引用。接收端要比较两份清单中的载荷散列是否一致。压缩 ZIP 使用标准 ZIP 格式；不支持加密 ZIP。压缩级别不影响语义。

### 2.2 结果包

```text
<run-id>.aiperf-result.zip
├── manifest.json
├── summary.json
├── requests.jsonl
├── steps.jsonl
├── validation.jsonl
├── errors.jsonl
├── worker.log                      # 可选、脱敏、受大小限制
└── checksums.sha256
```

如实现选择单一 `results.jsonl`，必须在协议版本内统一，不可让不同 Worker 同版本产生互不兼容布局。

## 3. manifest 草案

任务包和结果包共用顶层结构，`kind` 区分类型：

```json
{
  "format": "aiperf-package",
  "kind": "task",
  "schema_version": "1.0",
  "package_id": "uuid",
  "created_at_utc": "2026-11-19T02:00:00Z",
  "producer": {
    "app_version": "1.0.0",
    "engine_version": "1.0.0"
  },
  "compatibility": {
    "minimum_worker_version": "1.0.0",
    "required_capabilities": ["multipart", "jsonl-dataset"]
  },
  "task_id": "uuid",
  "task_snapshot_sha256": "64-lowercase-hex",
  "files": [
    {
      "path": "task.json",
      "size_bytes": 2048,
      "sha256": "64-lowercase-hex",
      "media_type": "application/json"
    }
  ]
}
```

结果包额外要求：`kind: "result"`、`run_id`、`source_task_package_id`、`source_task_snapshot_sha256`、`worker_version`、`producer.engine_version`、`started_at_utc`、`finished_at_utc` 和终态。字段值必须由 Schema 校验。

`task_snapshot_sha256` 对 `task.json` UTF-8 原始字节计算 SHA-256；这样不会因 JSON key 顺序、空白或 Unicode 规范化差异产生不同摘要。manifest 本身不参与任务快照摘要。

## 4. task.json 草案

```json
{
  "schema_version": "1.0",
  "task": {
    "task_id": "uuid",
    "name": "example",
    "target": {
      "base_url": "https://authorized.example/api",
      "authorization_acknowledged": true,
      "authorization_reference": "change-ticket-or-owner-reference"
    },
    "execution": {
      "mode": "fixed_concurrency",
      "request_count": 100,
      "concurrency": 10,
      "connect_timeout_seconds": 5,
      "request_timeout_seconds": 30,
      "warmup_count": 0,
      "retry_policy": "none"
    },
    "request_spec": {},
    "dataset": {
      "version_id": "uuid",
      "path": "datasets/dataset-version-id.jsonl",
      "format": "jsonl",
      "sha256": "64-lowercase-hex"
    },
    "credential_refs": [
      {"name": "API_TOKEN", "required": true, "source": "worker_local"}
    ]
  }
}
```

`authorization_acknowledged` 是用户确认记录，不构成网络授权的技术证明。导出端和 Worker 均需对目标地址执行安全策略。真正的秘密不得放在 `credential_refs` 中。

## 5. 结果记录草案

`requests.jsonl` 每行一条逻辑事务结果，建议包含：

```json
{
  "run_id": "uuid",
  "transaction_id": "uuid",
  "request_index": 1,
  "dataset_row_id": "row-0001",
  "status": "completed",
  "started_at_utc": "2026-11-19T02:01:00Z",
  "duration_ms": 512.4,
  "http_status": 200,
  "success": true,
  "error_code": null,
  "validation_summary": {"passed": 2, "failed": 0, "not_evaluable": 0}
}
```

`steps.jsonl` 存工作流步骤级请求结果；`validation.jsonl` 存规则 ID、结果和安全说明；`errors.jsonl` 存脱敏分类错误。`summary.json` 存最终 Run 状态、配置摘要、指标、计数、版本和统计口径标识。请求结果禁止默认保存秘密响应正文。

## 6. 校验与解包要求

接收端应先检查中央目录和元数据，再安全解压到新建临时目录。校验通过并完成原子移动/提交后才允许执行或导入。

必须拒绝：

- `..`、绝对路径、盘符、UNC、混合分隔符逃逸、规范化后逃逸根目录的条目；
- 符号链接、重复规范化路径、大小写折叠冲突（尤其 Windows 导入）、目录/文件冲突；
- 声明文件缺失、大小或 SHA-256 不匹配、未声明的额外执行文件；
- 不支持的 schema 主版本、未知必需能力或任务 Engine 不兼容；
- 包内真实凭据（按已知字段和值策略检测；不能把扫描结果视作绝对保证）；
- 超过配置的压缩文件数、解压总大小、单文件大小或压缩比限制。

具体资源阈值须配置并记录版本，数值待部署环境和数据规模确认。解压过程不能直接使用 ZIP 内路径拼接目标路径；每个文件解析后必须确认在隔离根目录内。

## 7. 目标与秘密校验

- 目标 URL 必须是用户显式配置并确认的地址。
- Worker 在启动前检查 scheme、host、port、解析后的地址及重定向策略。
- Linux 本地 secret provider 必须能解析所有 required credential ID；缺失时不得发请求。
- Worker 不因导入任务包自动设置系统代理或执行包内命令。
- 任务包不得包含环境变量全量转储、Shell 脚本或可执行插件。

允许访问私有内网地址是产品场景需要；因此不能简单封禁全部 RFC1918 地址。授权白名单、网段/端口范围和 DNS 解析变化策略待部署方确认。

## 8. 结果导入和幂等

Windows 导入流程：验证 ZIP → 验证 manifest/哈希/关联 → 暂存和解析 → 数据库事务写入导入记录和 Run → 原子移动附件/日志 → 返回结果。

建议按 `result package_id` 幂等：同一 package ID 和相同内容再次导入返回已导入记录；相同 ID 但内容哈希不同则拒绝并提示冲突。不得用同名文件覆盖既有执行记录。

若结果包引用未知任务，建议仍允许以只读孤立 Run 导入并标示“缺少原始任务元数据”，但必须匹配自身内嵌的任务快照摘要。该行为待确认。

## 9. JSON Schema

当前仓库附带首版机器可校验 Schema：

- [`schemas/1.0/manifest.schema.json`](../schemas/1.0/manifest.schema.json)
- [`schemas/1.0/task.schema.json`](../schemas/1.0/task.schema.json)
- [`schemas/1.0/result-summary.schema.json`](../schemas/1.0/result-summary.schema.json)
- [`schemas/1.0/request-record.schema.json`](../schemas/1.0/request-record.schema.json)

这些 Schema 以 JSON Schema Draft 2020-12 编写，是**协议草案**；提交实现前应以实际请求模型和结果模型做一致性评审，再将 Schema 同时用于导出校验、导入校验和协议测试。复杂的 ZIP 路径安全、内容哈希、跨字段一致性及执行安全校验无法仅由 JSON Schema 表达，接收端必须另外实现并测试。

## 10. 待确认

1. Schema 文件的 JSON Schema 方言和版本升级规则。
2. ZIP 文件数、大小、压缩比和单附件上限。
3. Checksums 是否单独文件或只存在 manifest。
4. Worker 与 Engine 的兼容矩阵及升级/降级策略。
5. 未知任务结果、重复导入和部分结果包的处理规则。
6. 是否需签名包以防篡改；SHA-256 只检测损坏，不证明发送者身份。
7. Worker 本机秘密提供器格式和权限要求。
