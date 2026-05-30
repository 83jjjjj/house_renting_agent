# House Renting Agent

一个基于 LangGraph 的租房助手。项目把一次租房对话拆成主图和三个子图：意图识别、房源推荐、预订下单、个人历史查询/普通问答，并通过 LangGraph `interrupt()` 支持多轮补充信息。

## 核心能力

- **意图路由**：LLM 结构化识别用户请求，路由到推荐、预订、查询我的、普通问答。
- **房源推荐**：抽取预算、城市、区域、朝向、房型等偏好，必要时中断补充信息；读取 MySQL schema 后生成 SQL 查询并总结推荐结果。
- **预订下单**：逐步收集房源名、姓名、电话、身份证号，调用工具生成订单并写入 LangGraph store。
- **长期记忆**：以 `context.user_id` 作为 namespace，保存用户预算偏好和历史订单。
- **可视化调试**：支持 LangGraph Studio 链路追踪，也提供 `static/house.html` 作为简单聊天前端。

## 图结构

`langgraph.json` 暴露了四个图：

- `house_renting_agent`: 主图入口，定义在 `src/agent/main.py`
- `recommend_graph`: 推荐子图，定义在 `src/agent/recommend.py`
- `reserve_graph`: 预订子图，定义在 `src/agent/reserve.py`
- `normal_graph`: 普通问答子图，定义在 `src/agent/normal.py`

主图流程：

```text
START
  -> determine_user_intent
  -> recommend | reserve | mine | normal
```

推荐流程结束后会进入 `reserve_or_not` 中断节点，询问用户是否继续预订。

## 环境变量

复制 `.env.example`：

```bash
cp .env.example .env
```

需要配置：

```text
DEEPSEEK_API_KEY=...

DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=3306
DB_NAME=...

LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=house-renting-agent
```

## 运行

```bash
uv sync --group dev
uv run langgraph dev
```

启动后可以用 LangGraph Studio 调试，也可以打开 `static/house.html`。前端默认请求 `http://127.0.0.1:8524`，并传入固定测试用户 `context.user_id = "159"`。

## 测试

普通单元测试不依赖真实 LLM 和数据库，使用 fake model、fake store、monkeypatch 隔离外部依赖：

```bash
uv run pytest tests/unit_tests
```

当前覆盖重点：

- 图对象是否可以成功编译
- 意图识别节点的结构化路由
- 普通问答节点是否正确包装 system message
- 推荐节点的偏好合并、预算扩展、订单历史保留
- 预订节点在工具返回后的总结分支

实时 LLM 冒烟测试默认跳过，避免 CI 消耗外部额度和受网络波动影响。需要手动验证时开启：

```bash
RUN_LIVE_LLM_TESTS=1 uv run pytest tests/integration_tests
```

静态检查：

```bash
uv run ruff check src tests
```

测试集评估需要真实 LLM，因此需要先在 `.env` 中配置 `DEEPSEEK_API_KEY`。意图识别和槽位抽取评估不依赖数据库：

```bash
uv run python -m tests.eval_scripts.run_intent_eval
uv run python -m tests.eval_scripts.run_slot_eval
uv run python -m tests.eval_scripts.run_sql_eval
uv run python -m tests.eval_scripts.run_e2e_eval
```

评估结果会写入 `reports/eval/<时间>_<commit>_<评估名>/`，包括 `summary.json`、`cases.jsonl` 和 `failures.jsonl`。槽位抽取还会额外输出 `required_failures.jsonl`，用于区分关键字段漏抽/错抽和仅多抽字段。SQL 评估当前做静态检查，验证只读、危险关键字、LIMIT 和约束包含情况，不连接真实数据库。E2E 评估当前验证图级多轮链路，会模拟推荐数据库结果和预订工具调用，但保留真实 LLM 意图/槽位抽取、真实 interrupt/resume 和 store 写入。报告用于保存每次模型/Prompt/代码调整后的指标和失败样本分析，不提交到 Git。

如果要验证生成 SQL 在真实 MySQL 上是否可执行，先准备一个可连接的测试库或只读账号；本机不需要安装 `mysql` 命令行客户端，项目通过 `pymysql` 连接：

```bash
uv run python -m tests.eval_scripts.run_sql_exec_eval --max-cases 3
uv run python -m tests.eval_scripts.run_sql_exec_eval
```

SQL Exec runner 会先做静态安全检查，只有只读 SELECT 且包含 LIMIT 的 SQL 才会执行。它统计 SQL 可执行率、DB 错误率、空结果率、结果约束命中率和查询延迟。

## 测试分层

这个项目的测试策略分三层：

1. **确定性单元测试**：节点函数级测试，mock LLM、interrupt、store 和工具调用，验证状态转换和边界条件。
2. **图级集成测试**：用 LangGraph 的 invoke/resume 机制跑关键链路，验证节点连接、中断恢复、store 写入和最终输出。
3. **人工可观测测试**：用 LangGraph Studio + LangSmith trace 检查 LLM 推理、工具调用参数、SQL 查询、异常路径。

对于 LLM 应用，单元测试不直接断言长文本完全相等，而是断言结构化输出、工具调用、状态变化和关键字段；质量评估再用测试集和人工/LLM-as-judge 分开做。
