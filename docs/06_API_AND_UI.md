# 06 管理端 API 与 UI

## 1. 范围

本文件规定 Windows 管理端的 API/UI 职责和建议接口。该接口基线是为补齐现有规格提出的建议，正式实施前需要和前端、运维及单用户/多用户边界一起评审。Linux 不提供管理 Web API。

## 2. API 约定

### 2.1 通用约定

- 路径前缀建议 `/api/v1`；JSON 使用 UTF-8，时间使用 RFC 3339 UTC，例如 `2026-11-19T02:00:00Z`。
- ID 使用 UUID 字符串；分页使用 `limit`、`cursor`，默认排序稳定。
- 成功响应包含稳定资源 ID 和必要元数据；创建任务与启动 Run 是不同操作。
- 输入使用 Pydantic/等价 Schema 验证；未知字段策略须统一，不能让前端绕过服务端限制。
- 上传采用 `multipart/form-data` 流式处理；服务端先写临时文件并完成校验，成功后原子提交。
- 破坏性操作需确认，并按任务状态限制删除；历史 Run 不能因删除模板而变得不可解释。
- HTTP 错误状态表达请求/API 层问题；业务规则失败属于已完成测试结果，不是 API 错误响应。

### 2.2 错误响应

建议统一结构：

```json
{
  "error": {
    "code": "CONCURRENCY_LIMIT_EXCEEDED",
    "message": "并发必须在允许范围内",
    "details": [{"field": "execution.concurrency", "reason": "maximum is 100"}],
    "request_id": "uuid"
  }
}
```

`message` 和 `details` 不能包含凭据。错误码应稳定并有目录；不要把 Python traceback 原样返回给浏览器。

## 3. 建议 API 资源

| 方法与路径 | 用途 | 主要验证 |
|---|---|---|
| `GET /api/v1/health` | 本机服务健康状态 | 不返回秘密、完整路径或环境变量 |
| `GET/POST /api/v1/environments` | 查询/创建 API 环境 | URL、名称和安全策略 |
| `GET/PATCH/DELETE /api/v1/environments/{id}` | 管理环境 | 被任务引用时的删除策略 |
| `POST /api/v1/environments/{id}/connectivity-check` | 低负载连通性检查 | 单独确认，不等同压力测试 |
| `POST /api/v1/requests/parse-curl` | cURL 文本转草稿 | 永不执行命令；返回不支持选项和警告 |
| `GET/POST /api/v1/request-specs` | 管理请求/工作流定义 | step ID、变量引用、规则 Schema |
| `GET/PATCH/DELETE /api/v1/request-specs/{id}` | 修改请求定义 | 被历史 Run 快照引用时保留版本 |
| `POST /api/v1/datasets` | 创建数据集元信息 | 格式、大小和文件数量限制 |
| `POST /api/v1/datasets/{id}/versions` | 上传/导入新版本 | 分块/流式保存；安全校验 |
| `GET /api/v1/datasets/{id}/versions/{version}/preview` | 分页预览和字段映射 | 不返回未授权的大量文件内容 |
| `POST /api/v1/tasks/validate` | 运行前/导出前配置校验 | 目标、授权、引用、并发和附件 |
| `GET/POST /api/v1/tasks` | 查询/创建任务配置 | 服务端输入 Schema |
| `GET/PATCH/DELETE /api/v1/tasks/{id}` | 管理任务配置 | Run 快照不可变 |
| `POST /api/v1/tasks/{id}/runs` | 启动 Windows 本机 Run | 目标确认、并发上限、单机资源 |
| `GET /api/v1/runs` | 分页列出执行实例 | 过滤状态、目标和时间范围 |
| `GET /api/v1/runs/{id}` | 读取 Run 快照与 summary | 不暴露凭据或未脱敏响应 |
| `POST /api/v1/runs/{id}/cancel` | 取消运行 | 幂等；只停止派发并按策略清理 |
| `GET /api/v1/runs/{id}/requests` | 分页读取逐请求结果 | 不一次性载入大型结果 |
| `GET /api/v1/runs/{id}/errors` | 查询分类错误和失败样本 | 敏感内容脱敏 |
| `GET /api/v1/runs/{id}/report` | 获取报告模型或下载 | 版本和字段稳定 |
| `POST /api/v1/packages/tasks` | 生成任务 ZIP | 导出前校验；可返回流式下载 |
| `POST /api/v1/packages/results/import` | 上传并导入结果 ZIP | 暂存、校验、幂等和大小限制 |
| `GET /api/v1/packages/imports/{id}` | 查看导入记录 | 状态、校验摘要和冲突信息 |

路由是推荐命名，不应在缺少产品确认时当作兼容 API 承诺。正式发布后需对接口进行版本治理。

## 4. WebSocket 进度通道

建议路径：`/api/v1/runs/{run_id}/events`。客户端先获取当前 Run 快照，再建立 WebSocket；事件包含递增 `sequence`，允许断连后通过轮询快照恢复，不依赖事件历史永久保留。

建议事件：

```json
{"type":"run.progress","run_id":"uuid","sequence":12,
 "at_utc":"2026-11-19T02:01:00Z",
 "data":{"scheduled":80,"completed":72,"success":68,"failed":4,"in_flight":8}}
```

其他事件：`run.state_changed`、`run.summary_updated`、`run.warning`、`run.finished`。不要通过事件传递 Authorization、Token、完整二进制响应或秘密变量值。高频逐请求事件可采样或批量合并，完整结果从分页 API 获取。

WebSocket 只服务 Windows 本机 Run 展示；第一阶段不声称可实时监控 Linux 离线任务。

## 5. 页面结构建议

1. **总览**：最近 Run、运行状态、失败概览、存储/版本健康信息。
2. **API 环境**：目标地址、认证类型、秘密引用、连通性检查和授权提示。
3. **请求定义**：单请求编辑、多步步骤列表、cURL 导入草稿、变量和业务规则。
4. **数据集**：导入、格式识别、字段映射、分页预览、附件状态、版本历史。
5. **任务配置**：选择执行端、请求/数据集快照、并发/数量/超时、目标授权确认、预检查报告。
6. **运行监控**：Run 状态、请求数、错误类别、时延摘要；可取消 Windows Run。
7. **结果详情**：汇总图表、逐请求表、筛选失败项、步骤详情和脱敏错误。
8. **导入/导出**：任务包导出、结果包导入校验、导入历史和冲突处理。
9. **设置**：应用目录、日志和结果保留、版本信息；秘密配置入口需严格限制显示/导出。

页面操作应说明 destructive/负载行为。例如“开始压测”必须展示目标 URL、并发、请求数、数据集版本和授权确认，不应把确认藏在默认勾选项里。

## 6. UI 校验与可访问性

- 前端做即时字段提示，后端对所有输入再验证。
- 校验错误显示字段路径、简明原因和修复方向，不只显示“请求失败”。
- 页面状态要区分 API 请求失败与 Run 执行失败。
- 大型结果和数据集采用分页/虚拟列表，不一次渲染全部记录。
- 上传显示文件名、大小、哈希/校验状态和失败原因；不显示秘密内容。
- 进度指标注明统计口径和样本数；未完成时不展示为最终结果。
- 颜色不是唯一状态提示；表单和表格使用键盘可访问控件。

## 7. 本机安全边界

当前产品默认访问 `127.0.0.1:8000`。若服务未来绑定到局域网地址，必须在开放之前确定身份认证、CSRF、CORS、会话、TLS、审计和多用户权限。不得仅因它是“内网工具”就无认证监听所有网卡。

如使用浏览器 Cookie 会话，状态改变请求应实施 CSRF 防护；如使用 bearer 凭据，存储和日志脱敏规则需明确。健康检查不应泄漏操作系统环境变量或完整文件系统路径。

## 8. 待确认

1. API 是否作为本地使用的长期兼容接口，或仅供内置前端使用。
2. 是否需要登录、用户角色和本机多用户隔离。
3. 是否需要从 UI 管理 Linux Worker 本地秘密（按隔离架构建议不要远程管理）。
4. 结果报告导出 PDF/HTML/CSV/XLSX 的首期范围。
5. WebSocket 进度频率、重连期限和取消确认交互。
