# 03 执行引擎、并发与指标

## 1. 目的和状态

本文件统一 Windows 和 Linux 的执行语义。固定请求数 + 固定并发已确认作为首期唯一负载模式（2026-11-19）；并发硬上限为 100，Windows 和 Linux 共享 Engine。其他执行模式和具体指标公式仍属**建议基线**，需在对应实现阶段冻结。

## 2. 运行配置

建议 Run 配置字段：

| 字段 | 建议类型/范围 | 说明 |
|---|---|---|
| `request_count` | 正整数，上限待确认 | 正式阶段要调度的逻辑事务数 |
| `concurrency` | 整数 1..100 | 最大同时在途逻辑事务数；服务端再次校验 |
| `request_timeout_seconds` | 正数，上限待确认 | 单个 HTTP 尝试的整体期限 |
| `connect_timeout_seconds` | 正数且不大于总超时 | 建连期限，便于区分连接故障 |
| `warmup_count` | 非负整数，建议默认 0 | 可选预热事务；单独统计且不计正式结果 |
| `dataset_mode` | `sequential` / `cycle` / `random_seeded` | 数据行选择方式；随机模式记录种子 |
| `retry_policy` | 建议仅 `none` 为首期 | 自动重试会改变请求负载和统计口径 |
| `max_response_bytes` | 正整数，需配置 | 超过时停止缓存正文；不应停止读取策略未知，待确认 |

配置值必须在 API、CLI 和包导入路径复用同一模型验证。客户端界面限制不能代替服务端限制。

## 3. 建议的首期执行模型

**首期已确认：固定事务数 + 固定并发（闭环并发模型）。** Engine 同时维护最多 `concurrency` 个在途事务；事务结束后补充下一个，直到已调度数达到 `request_count` 或收到取消信号。它适合首期比较响应时间和并发负载，不能等价于固定 RPS 测试。

- 总事务数固定；无预热时正式事务总数为 `request_count`。
- 数据集按顺序取行；不足时循环。随机模式如果实现，必须记录随机种子。
- 默认不重试，避免重复副作用和统计歧义。以后如支持重试，逻辑事务与 HTTP 尝试要分别计数。
- 首期不保证恒定到达率；报表必须显示“固定并发”而不是称为固定 RPS。
- 一次多步骤流程默认以一个逻辑事务计数，每个步骤另计请求级指标；整体事务时延是从首步开始到最后必要步骤完成的时间。该口径须评审确认。
- 按配置规则判断业务结果；业务失败的 HTTP 请求仍是已完成事务，不算传输错误。

## 4. 执行生命周期和状态机

```text
created → validating → queued → running → finalizing → completed
                   ↘ failed       ↘ failed       ↘ failed
                                   ↘ cancelling → cancelled
                                   ↘ interrupted
```

建议状态定义：

- `created`：已保存配置，尚无 Run。
- `validating`：检查请求、数据集、目标授权、并发、凭据引用和文件。
- `queued`：校验完成，等候执行资源。
- `running`：事务正在调度或在途。
- `cancelling`：停止派发新事务；已在途请求按取消策略结束。
- `finalizing`：写入尾部结果、汇总、文件和包。
- `completed`：正常耗尽任务。
- `failed`：运行前校验或引擎级不可恢复失败；需错误码和原因。
- `cancelled`：收到取消后完成清理。
- `interrupted`：进程/容器非正常终止且无法确认已完整结束。

终态不可回到运行态。重复取消应幂等。WebSocket 断连不能更改 Run 状态。

## 5. 时延定义

每个单步 HTTP 请求建议记录以下时点，精度使用单调时钟计算时长：

1. `scheduled_at`：Engine 决定该事务可执行。
2. `started_at`：HTTP 请求开始发送前。
3. `response_headers_at`：收到响应头（若传输库提供可靠钩子）。
4. `completed_at`：响应体读到终止或受限读取策略结束。

建议指标：

- **端到端请求时延**：`completed_at - started_at`，包含客户端接收响应体时间，不包含 Engine 等待调度时间。
- **调度等待时间**：`started_at - scheduled_at`，用于识别本地排队。
- **TTFB**：`response_headers_at - started_at`，仅当传输库的时间点语义经验证后提供。
- **事务时延**：多步骤事务从首步开始到成功结束或失败停止的时间；并行分支若未来支持，需定义关键路径口径。

失败请求仍可有已观测时延；连接前失败应无 HTTP 状态码。

## 6. 指标定义

建议所有聚合指标带有统计时间窗与样本数量。

| 指标 | 建议定义 |
|---|---|
| `scheduled_count` | 已进入 Engine 调度的逻辑事务数 |
| `completed_count` | 正常得到终止状态的事务数，包含 HTTP/业务失败 |
| `success_count` | 满足 HTTP 和全部必需业务规则的事务数 |
| `failure_count` | 终止但不成功的事务数 |
| `cancelled_count` | 被取消且未正常结束的事务数 |
| `in_flight_count` | 当前在途事务数 |
| `success_rate` | `success_count / completed_count`；无分母时为 null |
| `throughput_completed_per_sec` | 完成事务数除以从首个开始到最后完成的运行时长 |
| `throughput_success_per_sec` | 成功事务数除以同一运行时长 |
| `latency_ms` | 每事务/步骤时延样本及 min/mean/median/p90/p95/p99/max |
| `http_status_counts` | 按 HTTP 状态码计数 |
| `error_counts` | 按统一错误类别计数 |
| `validation_failure_counts` | 按校验规则 ID 和失败原因聚合 |

建议百分位采用 nearest-rank：排序后取 `ceil(p * n)` 位置（索引从 1 起）；空样本为 null。小样本仍可显示百分位，但报告必须显示样本数。是否采用 HDR histogram 或流式近似算法待确认；若任务规模大，禁止无限保留所有样本于内存。

`run_duration_seconds` 建议取第一个正式事务启动到所有已派发事务结束；未完成而取消的运行应同时显示总墙钟时长和完成样本统计窗口。

## 7. 业务校验

建议校验分阶段：

1. HTTP 层条件：状态码允许列表、必要响应头。
2. 响应字段条件：JSON Pointer 等明确路径、存在/不存在、相等/包含、数值范围。
3. 多步关联条件：前一步字段提取并填入后续步骤。

默认所有标记为 required 的规则都通过时业务成功。规则缺失字段、响应格式错误或响应体超限时应记录 `not_evaluable` 或失败原因，不可静默通过。首期不执行任意用户脚本，也不调用模型裁判。

## 8. 错误分类

建议统一类别：

| 类别 | 示例 | HTTP 状态 |
|---|---|---|
| `DNS_ERROR` | 域名无法解析 | null |
| `CONNECT_ERROR` | 拒绝连接、无法建立连接 | null |
| `TLS_ERROR` | 证书校验或 TLS 握手失败 | null |
| `CONNECT_TIMEOUT` | 建连超时 | null |
| `REQUEST_TIMEOUT` | 整体请求超时 | null 或库给出的响应状态 |
| `CONNECTION_RESET` | 对端/中间设备重置 | null 或已收到状态 |
| `HTTP_STATUS_FAILURE` | 响应状态不满足规则 | 实际状态码 |
| `VALIDATION_FAILURE` | 业务响应规则失败 | 实际状态码 |
| `REQUEST_BUILD_ERROR` | 变量缺失、文件引用无效 | 通常为 null |
| `PACKAGE_VALIDATION_ERROR` | 包结构/版本/散列非法 | 不适用 |
| `CANCELLED` | 用户取消 | 可有部分响应信息 |
| `ENGINE_INTERNAL_ERROR` | 未预期引擎异常 | 可能为 null |

错误中可存脱敏后的短说明、稳定错误码和可安全复现的上下文；不得保存 Authorization、Cookie、Token 或完整秘密响应。

## 9. 取消、重试与资源回收

- 取消后停止创建新事务；正在途中的请求应发起取消并等待有限清理时间。
- 已结束结果先持久化，再发进度事件。
- 单个请求异常不得使其他独立事务丢失结果；引擎级异常需以明确 Run 终态结束。
- HTTP 客户端会话、连接器、文件句柄、临时目录必须在 Run 结束/取消/失败时关闭。
- 重试首期默认关闭。将来若加入，`logical_transaction_id` 和 `attempt_index` 必须分离，并明确是否再次计入吞吐和业务成功率。

## 10. 事件模型

建议 Engine 产生只追加的领域事件：`run_started`、`progress_updated`、`request_completed`（可按采样或批量推送）、`validation_failed`、`run_cancelling`、`run_finished`。事件消费者可持久化、展示或汇总；UI 事件传输不得成为执行正确性的唯一来源。

## 11. 待确认

1. 恒定 RPS、持续时间或递增负载模式是否排入后续阶段（首期不支持）。
2. 多步骤流程是否以整个事务作为成功率和吞吐主口径。
3. 预热、自动重试、重定向和连接复用策略。
4. 百分位算法、最大请求数/运行时长和结果存储容量。
5. 超时究竟是整体时限还是各步骤独立时限。
6. 响应体最大读取量、压缩响应和流式响应如何统计。
