# 04 数据集、文件和请求构建

## 1. 范围与原则

本规格定义从可执行测试用例到真实 HTTP 请求的映射。首期要区分两种“文件格式”：一是作为用例输入的数据源（CSV/JSON/JSONL/XLSX 的正式支持清单仍待确认）；二是被测 API 要接收的真实附件（图片、PDF、Excel 等，按请求场景上传原文件）。把 `.xlsx` 当 API 附件支持，不自动意味着必须把任意 XLSX 工作簿解析成用例；支持 CSV 用例也不意味着可以把 PDF 附件抽取文本来替代原文件。对上传文件的压力测试必须实际上传原文件；只有用户明确选择“预处理文本模式”时才可用预处理后的文本替代原始文件。

具体格式支持级别若标为“建议基线”，实施前应结合源工作簿和样例确认。数据文件不得执行宏、公式、脚本或 Shell 命令。

## 2. 数据集对象和版本

建议数据集由逻辑对象、不可变版本、可执行用例、预期结果、来源记录和附件组成。组件登记清单（含组件名称、接口信息和验收来源）是另一类导入对象，不直接当作可执行数据集：

```text
Dataset(id, name, source_format)
  └── DatasetVersion(id, version, source_sha256, schema, created_at)
        ├── TestCase(case_id, ordinal, values, payload?, expected?, provenance)
        └── Asset(asset_id, safe_name, size, media_type, sha256, storage_ref)

ComponentRegistrySource(id, source_sha256, source_format, mapping_version)
  └── ComponentProfile / ScenarioProfile 草稿（审核后才可执行）
```

`TestCase` 是一条待执行的业务样本，不是已渲染的 HTTP 请求。建议字段包括：稳定 `case_id`、有序 `ordinal`、保留 JSON 原生类型的 `values`、可选完整 `payload`、可选异构 `expected`、Asset 引用及来源/清洗记录。`payload` 可以为空，由已审核的 Scenario 映射构造；不得从字段名猜测请求含义。`expected` 由显式 evaluator/schema 解释，不能假定所有组件都返回同一形状。附件通过 Asset ID 引用，不能在用例中保存绝对路径。

若产品支持组件清单导入，应将其用于登记组件、功能层级、接口示例、验收来源和附件说明；其工作表、表头行、列映射和清单版本必须在预览时由用户确认。导入先生成未启用草稿，不自动执行网络请求。正式清单导入是否进入首版仍待确认，也可以先由用户手工维护 ComponentProfile。

创建 Run 时固定 `dataset_version_id`、用例 ID 与顺序、附件哈希以及 Request/Scenario/Evaluation Profile 版本。更新源文件或清洗规则应生成新 DatasetVersion，不覆盖已被历史 Run 引用的内容。

### 2.1 建议首期输入格式

| 格式 | 建议支持方式 | 注意事项 |
|---|---|---|
| CSV | UTF-8/UTF-8 BOM；首行字段名需经预览确认 | 分隔符和引号按 RFC 4180 兼容规则；其他编码要明确导入选项 |
| JSON | 根节点数组或定义明确的行数组 | 不允许任意对象展开造成歧义；对象型字典须选择显式路径/映射 |
| JSONL | 每行一个 JSON 对象 | 错误报告包含行号和字段路径；大文件逐行读取 |
| XLSX | 仅在格式清单获批后作为数据源；用户指定 sheet、标题行和数据范围 | 公式缓存值、合并单元格、隐藏行、多 sheet 行为待确认；禁止执行宏 |
| 附件目录 | CSV/JSON 行通过相对路径引用 | 限定在数据集根目录，禁止路径穿越和符号链接逃逸 |

此表是格式候选，不代表首期导入格式已全部批准。必须区分“解析 XLSX 用例工作簿”和“把 XLSX 文件作为 HTTP 附件上传”；分别定义格式、预览、安全检查和验收标准。源项目存在多种组件清单和用例文件形态，不存在已确认的单一全局表头，见 `10_SOURCE_WORKBOOK_NOTES.md` 和 `11_REAL_PROJECT_PATTERN_ANALYSIS.md`。

### 2.2 数据行字段语义

建议把每条用例的输入值视为 JSON object；字符串、数字、布尔、null 和数组/对象均保留类型。字段名区分大小写。空白字符串与 null 不自动等价。输入缺字段、额外字段、类型不匹配时，在预览/校验时明确报出。用例预期结果、来源/清洗记录、附件引用是独立于输入值的字段；不同组件的 `expected` 形状可以不同，但必须绑定明确的评估规则版本。

附件字段可以使用资产引用对象，而不是把文件二进制塞入 JSON：

```json
{
  "case_id": "case-001",
  "values": {"prompt": "总结此文件"},
  "asset_refs": [
    {"asset_id": "asset-uuid", "field": "document", "role": "input"}
  ],
  "expected": null,
  "provenance": {"source_file": "cases.jsonl", "source_line": 1}
}
```

### 2.3 当前 Reader v1 实现边界

`aiperf.datasets` 当前提供独立的可执行用例读取器，技术实现支持 CSV、JSON 数组和 JSONL；它只负责把源记录转换为有序 `DatasetCase` 并给出导入诊断，不负责组件清单导入、Asset 落盘/去重、字段映射界面、请求构建、执行或效果评估。XLSX/XLS 用例工作簿解析仍待确认，不因 Excel 可作为 HTTP 附件而默认启用。

- 调用方必须显式传入绝对源路径和 `DatasetFormat`；附件校验时还要显式传绝对 `dataset_root`。
- CSV 使用 UTF-8/UTF-8 BOM 和首行表头。`case_id`、`component_id`、`scenario_id`、`payload`、`expected`、`source`、`metadata`、`asset_refs` 和 `input_paths` 列映射到同名用例字段；其它列（包括名为 `values` 的列）保持为 `values` 中的字符串。字段名为空或重复、数据行列数不匹配均会报错。单元格保持原始字符串，`001`、`false`、空单元格及看起来像 JSON 的文本不会被自动转型或反序列化。
- JSON 输入必须是对象数组；JSONL 每个非空物理行必须是一个对象。JSON/JSONL 中字符串、数字、布尔、null、数组和对象保留 JSON 类型；重复对象键、非标准 `NaN`/`Infinity` 常量及转换为非有限浮点数的溢出数值会拒绝。字符串内序列化的 JSON 不会二次解析。
- 对象可以使用显式 `values` 对象；未放入 `values` 的业务字段会并入 `values`。`case_id`、`component_id`、`scenario_id`、`payload`、`expected`、`source`、`metadata`、`asset_refs` 和 `input_paths` 会作为独立用例字段保留。CSV 的 `provenance` 列和 JSON/JSONL 的 `provenance` 字段均保留在 `provenance.source_metadata`，读取器同时写入源文件名和物理记录起始行。
- 缺少 `case_id`、JSON null ID 或 CSV 空 ID 时，读取器按源顺序生成 `row-000001` 等 ID；显式重复 ID、JSON 空白 ID 会给出可定位错误。重复 ID 检测需要在导入期间保存已见 ID 集合，因此额外内存随用例数量增加；正文记录仍逐条产出。
- 空 CSV/JSONL 行默认报错；只有显式设置 `DatasetReaderOptions(skip_blank_rows=True)` 才跳过。跳过空行不增加用例 ordinal。错误详情只含源文件名、行号、字段和固定原因，不回显数据值或附件路径。
- `input_paths`、结构化 JSON/JSONL 的 `asset_refs[*].path` 和 `DatasetReaderOptions.attachment_fields` 指定的字段只用于路径安全检查；值保持原样，不会因此自动转成 Asset。null、空字符串和空数组表示没有本地路径；非空路径必须是数据集根目录下存在的普通文件；拒绝绝对路径、盘符/UNC 路径、`..` 穿越、缺失文件和解析到根目录之外的符号链接。已管理的 `asset_id` 不当成本地路径处理。CSV 的单元格一律作为字符串保留，不会把其中的 JSON 文本解析成 `asset_refs` 对象。

`DatasetCase` 是 frozen dataclass，可防止字段重绑定；其中用于保留原生 JSON 类型的 dict/list 是普通 Python 容器，仍可被调用方修改。创建 DatasetVersion/Run 快照时，后续服务必须进行独立序列化或复制，不能把该读取对象本身当作深度不可变快照。

CSV 和 JSONL 按行读取，JSON 数组按记录增量解码。每条记录及单个字段仍需驻留内存；格式总大小、单记录大小、总附件大小和保留期还没有业务批准值，需在后续导入/资产服务中单独配置和验收。读取器不计算完整 DatasetVersion 哈希；创建不可变版本和资产哈希属于后续服务层。

用例读取使用共享 Engine 包中的纯 Python 接口：

```python
from pathlib import Path

from aiperf.datasets import DatasetFormat, DatasetReaderOptions, iter_dataset_cases

for case in iter_dataset_cases(
    Path(r"D:\datasets\cases.jsonl"),
    DatasetFormat.JSONL,
    dataset_root=Path(r"D:\datasets"),
    options=DatasetReaderOptions(attachment_fields=("document_path",)),
):
    print(case.ordinal, case.case_id, case.values)
```

以上目录和字段仅作 API 用法示意，不是产品默认路径或固定业务 schema。

## 3. 文件管理与安全

- 上传按流处理；服务端设置可配置的单文件、总量和文件数量限制（具体数值待确认）。
- 原始文件名仅作展示元数据；落盘名使用随机 ID 或内容哈希，不能直接拼接用户文件名。
- 保存大小、SHA-256、识别的媒体类型和导入来源；客户端声明的 MIME 类型不能单独作为真实性依据。
- 文件引用必须解析到应用控制的存储根目录；拒绝 `..`、绝对路径、UNC 路径、盘符路径、符号链接越界。
- 预览只处理允许的格式和有限范围，不执行 Excel 宏、嵌入对象、脚本或外链。
- 任务包导出时只包含该任务实际引用的附件；重复附件可按 SHA-256 去重，但引用关系需保留。
- 文件读取使用流或受限缓存；不因并发数等于 100 就把 100 份大文件全部复制到内存。

## 4. 请求定义

建议一个 RequestSpec 可以是单个 HTTP 请求，也可以由有序 Step 列表组成。

### 4.1 单请求字段

| 字段 | 说明 |
|---|---|
| `method` | 标准 HTTP 方法；不支持或危险方法需显式策略 |
| `url` | 相对路径或完整 URL；目标基址由 API 环境/任务明确配置 |
| `query` | 有序键值项；支持模板变量 |
| `headers` | 键值项；凭据字段只能用安全引用，不允许秘密常量被导出 |
| `body.kind` | `none`、`json`、`form`、`multipart`、`text`、`binary` |
| `timeout` | 可覆盖默认值的有界时限 |
| `redirect_policy` | 建议首期默认不跟随跨主机重定向 |
| `response_rules` | HTTP 和业务校验配置 |

请求头应允许重复键的行为需确认；敏感头默认标记并脱敏显示。

### 4.2 多步流程

Step 按稳定 `step_id` 和顺序执行。每一步可读取数据集变量和此前步骤输出。建议首期只支持串行步骤，不支持并行分支、条件循环或任意脚本。前一步失败时是否停止后续步骤应由流程策略明确，默认建议 fail-fast。

每一步结果保留请求耗时、HTTP 状态、传输错误、规则结果和被允许的字段提取结果。事务总结果由步骤策略聚合，不用最后一步的 HTTP 200 简单替代。

## 5. 变量插值与凭据

建议变量语法：

- `{{dataset.field_name}}`：当前数据行字段。
- `{{steps.upload.output#/data/id}}`：之前步骤 JSON Pointer 路径的提取值。
- `{{secrets.API_TOKEN}}`：执行端秘密提供器提供的值。

以上语法属于建议基线，正式冻结前须确认转义和嵌套规则。缺失变量应在运行前或构建请求时失败并产生明确错误，不能悄悄替换为空字符串。

秘密值只能在发送阶段注入内存，不应复制到任务快照、错误文本、WebSocket、日志、导出包或普通报告。Windows 和 Linux 各自独立配置同名 secret ID；任务包只保留 ID 和必需性标记。

## 6. multipart 和多文件

每个 multipart part 建议具备：

```json
{
  "name": "files",
  "kind": "file",
  "source": {"dataset_field": "document"},
  "filename_mode": "asset_name",
  "media_type_mode": "detected"
}
```

文本 part 可配置固定值或变量。相同 `name` 多次出现应保留为多个 part，不应被字典覆盖。实际请求使用随机 boundary，并由 HTTP 客户端正确编码。用户可以为每个 part 指定字段名、文件名策略和可选媒体类型覆盖；媒体类型不能改变原始文件内容。

需要分别验收：一个文件、同字段多文件、多字段不同文件、文本字段+文件、空附件、非 ASCII 文件名、大附件、附件丢失和附件哈希不匹配。

## 7. Dify 文件上传和工作流

建议把 Dify 场景建模为可配置的多个普通 HTTP Step：

1. 使用文件上传端点发送真实附件并获取文件标识。
2. 把返回的文件标识和用户字段映射为后续工作流请求变量。
3. 调用工作流端点并传入文本、文件引用及其他数据集变量。
4. 对上传和工作流各自记录步骤结果，并按事务规则计算整体结果。

API 路径、认证头、文件类型、`user` 字段和返回 JSON 结构应由用户/API 配置决定，不硬编码为单一 Dify 版本。响应字段提取应支持有限、明确的 JSON Pointer 语义。不得在文档或测试中使用真实 Token。

## 8. cURL 导入

cURL 导入只是将命令文本解析为请求草稿，永不执行所导入命令。

- 不调用 shell、`cmd.exe`、PowerShell 或 `bash` 来解析。
- 拒绝或提示 `--config`、`--next`、`--proxy-command`、命令替换、管道、重定向和无法安全解释的扩展。
- 解析支持的 URL、方法、header、data、form/file 参数，展示解析结果并要求用户复核。
- cURL 中疑似 Token/密码的字段导入为秘密引用占位符或脱敏文本，不能默认为可导出普通请求字段。
- 不支持的选项逐项列出；不可静默忽略影响请求语义的参数。
- shell 转义语义复杂时，宁可拒绝导入并要求手动配置，不能执行原文求值。

首期解析器只接受以下参数，并将命令转换为单个 HTTP 请求草稿：

| 用途 | 支持写法 |
|---|---|
| 请求方法 | `-X METHOD`、`--request METHOD`、`--request=METHOD` |
| 请求头 | `-H 'Name: value'`、`--header 'Name: value'`、`--header='Name: value'`；重复头按原顺序保留 |
| URL | 第一个位置 URL，或 `--url URL` / `--url=URL`；仅接受 HTTP/HTTPS 绝对 URL |
| 请求体 | `-d`、`--data`、`--data-raw`、`--data-binary`；参数和值可分开，长参数也支持 `--data=value` 形式 |
| multipart | `-F`、`--form`，支持文本字段及 `name=@path` 文件字段 |

未指定方法时，无请求体默认为 GET，有 data/form 请求体默认为 POST。URL 查询参数和重复字段按顺序保留；多个 data 参数按 cURL 语义以 `&` 拼接。表单 Content-Type 将 data 解析为有序键值对，JSON Content-Type 将合法 JSON 解析为 JSON 值。无 Content-Type 的 data 按文本处理。每个 cURL 输入只允许一个 URL 和一个请求，不支持 `--next` 或隐式多请求。

导入器仅使用命令文本解析，不启动 Shell/子进程、不访问网络，也不打开本地文件。`-F 'name=@path'` 中的路径只作为导入提示保存，提示用户在执行前选择受管理的文件；导入阶段绝不会读取该路径。cURL 会自行读取文件的 `-d @path`、`--data @path`、`--data-binary @path`、`-F 'name=<path'` 和带 MIME 参数的 multipart 文件写法不在支持范围内，会被拒绝。敏感头、查询/表单字段以及 JSON 对象中名称疑似凭据的值替换为 `{{secrets.NAME}}` 引用，并在结果中列出需绑定的凭据名称。无法识别的参数、Shell 管道/重定向/命令替换和格式错误输入将安全拒绝，诊断不回显命令内容或值。

## 9. 业务规则和响应体处理

校验规则参见 `03_EXECUTION_ENGINE.md`。响应正文只为规则评估在受限内存中读取；默认不完整持久化。若业务需要保存命中样本，应配置最大字节数、字段白名单和脱敏规则，并说明保留时间。超大或流式响应的默认策略待确认。

## 10. 校验阶段

1. 导入校验：文件格式、编码、sheet、列名、空行和类型。
2. 映射校验：RequestSpec 所需变量是否存在；变量类型是否可编码。
3. 文件校验：引用存在、大小/哈希匹配、位于存储根目录。
4. 导出校验：目标、数据集版本、附件和 Linux 凭据引用齐备。
5. 执行时校验：模板渲染完成、秘密可用、请求大小和超时符合限制。

错误应包含来源文件、行号、字段或 step ID，但不包含凭据值。

## 11. 待确认

1. CSV/XLSX/JSON/JSONL 首期正式支持清单和最大数据规模；组件清单工作簿与可执行用例工作簿是否都要导入。
2. Excel 多 Sheet、公式单元格、合并单元格和隐藏行的处理规则。
3. 是否需要数组/嵌套对象的字段映射界面。
4. 插值语法、JSON Pointer 提取和失败时后续步骤策略。
5. 上传大小、附件数量、允许的文件后缀和 MIME 策略。
6. cURL 导入支持的确切选项集和格式版本。
7. 是否支持响应体样本保留，以及脱敏规则和留存周期。
