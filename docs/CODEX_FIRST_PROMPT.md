# Codex 启动提示词（可直接复制）

请先完整阅读仓库根目录 `README.md`、`AGENTS.md` 和 `docs/` 下全部 Markdown 文档。它们是 AI-PERF 项目的正式需求基线。

当前最终架构已经确定：
- Windows 是唯一 Web 管理端，Python 3.11 + Conda + FastAPI，Vue3 编译静态资源由 FastAPI 托管。
- Windows 同时支持本机压测。
- Linux 只运行 Docker Worker，不部署 Web 管理端。
- Linux 和 Windows 不假设网络互通；第一期通过堡垒机人工 SSH/SFTP 双向传输标准任务 ZIP 和结果 ZIP。
- 两端共用同一套 Python 核心压测引擎。
- Linux 任务开始后不依赖 Windows 在线。
- 第一阶段最大并发 100。
- 必须支持 JSON、multipart 图片、PDF、Excel、多文件、Dify 文件上传后调用工作流等场景。
- 不得执行导入 cURL 中的 Shell 命令；不得把密钥明文写入任务包、日志和报告。

第一步不要直接写代码。请先输出：
1. 逐文档阅读确认清单；
2. 需求理解和架构复述；
3. 关键模块依赖关系；
4. 数据库 ER 设计；
5. 任务包/结果包 JSON Schema 草案；
6. 项目目录树；
7. 每个里程碑的可交付内容与测试；
8. 文档中仍需确认的问题。

然后等待确认，或在无歧义的基础骨架上开始 M0。实现时严格遵循 AGENTS.md，不得擅自改成 Linux Web 中心架构、不得引入 Redis/Ray/Celery 作为第一期必需组件。
