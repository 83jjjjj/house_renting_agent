# 测试方案

## 分层

1. 单元测试：隔离 LLM、数据库、LangGraph store 和 interrupt，验证节点函数的确定性状态变化。
2. 图级集成测试：用 LangGraph invoke/resume 跑主图关键链路，验证条件边、中断恢复、跨节点状态传递。
3. 测试集评估：用 JSONL 样本评估意图识别、槽位抽取、SQL 安全性和端到端任务完成率。
4. 压测：先压同步实现的基线，再根据瓶颈决定是否异步化或调整并发。

## 覆盖率目标

当前单元测试使用 `coverage.py` + `pytest-cov` 统计覆盖率。

```bash
uv run pytest tests/unit_tests --cov=agent --cov-report=term-missing
```

阶段目标：

- 基线：总覆盖率不低于 75%。
- 下一阶段：核心节点模块不低于 80%。
- 不用单元测试强行覆盖真实 LLM、真实数据库和 ToolNode 外部调用，这部分放到集成测试和测试集评估。

## 压测策略

先保留同步节点实现，压出基线指标：

- 平均延迟、p95、p99
- 失败率
- 并发 run 数
- LLM 调用次数
- 数据库查询耗时

如果瓶颈主要来自同步 LLM/数据库 I/O，再考虑把高耗时节点改为 async，或对同步数据库调用加线程池/连接池。LangGraph Server 提供 run 级调度能力，但业务代码里的阻塞 I/O、共享状态写入和外部服务限流仍需要单独设计。

## 测试集评估

第一阶段先跑不依赖数据库的两类评估：

```bash
uv run python -m tests.eval_scripts.run_intent_eval
uv run python -m tests.eval_scripts.run_slot_eval
uv run python -m tests.eval_scripts.run_sql_eval
uv run python -m tests.eval_scripts.run_e2e_eval
```

SQL Exec 评估需要真实 MySQL 连接，用于验证生成 SQL 在库表上是否可执行、是否返回结果以及基础结果约束是否成立：

```bash
uv run python -m tests.eval_scripts.run_sql_exec_eval --max-cases 3
uv run python -m tests.eval_scripts.run_sql_exec_eval
```

依赖和环境：

- 依赖项：使用项目已有依赖，不额外引入第三方包。
- 必要环境变量：`DEEPSEEK_API_KEY`。
- 数据库变量：`DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`、`DB_NAME` 只在 SQL Exec 和 E2E 真实数据库链路评估时需要。静态 SQL runner 不连接数据库。
- 本机不需要安装 `mysql` 命令行客户端；SQL Exec runner 通过项目依赖 `pymysql` 连接 MySQL 服务。
- 建议使用只读数据库账号和脱敏数据。至少需要有 `houses` 表和与生产一致的字段；如果要评估空结果率、结果约束命中率，数据分布应覆盖北京/上海、朝阳/海淀/浦东、预算区间、整租/合租、朝向、设施等测试集条件。

本项目提供一份本地 SQL Exec fixture：

```bash
mysql -u <user> -p < tests/fixtures/mysql_houses_seed.sql
```

如果使用数据库 GUI 或容器内 MySQL，也可以直接执行 `tests/fixtures/mysql_houses_seed.sql`。它会创建生产同构的 `houses` 表，并插入 30 条脱敏样本数据。数据 ID 固定在 `99000000001` 到 `99000000030`，重复导入会先删除这一段 fixture 数据，不影响其他 ID。

fixture 数据按生产样例对齐枚举值：

- `rent_type` 使用 `whole_rent`、`worry_free_rental`，不使用中文“整租/合租”。
- `rooms` 使用 `one`、`two`、`three`，不使用数字 `1/2/3`。
- `position` 使用 `south`、`north`、`east`、`west`，不使用中文“朝南/朝北”。
- `devices` 使用 `toilet`、`cook`、`gas`、`balcony`、`icebox`、`washer`、`aircondition` 等英文设备码。

输出目录：

```text
reports/eval/<timestamp>_<commit>_<eval-name>/
  summary.json    # 总指标
  cases.jsonl     # 每条样本预测结果
  failures.jsonl  # 失败样本，便于回归分析
```

意图识别使用 `accuracy` 和 `macro_f1`。如果只用 `--max-cases` 做 smoke 测试，样本可能只覆盖部分类别，此时主要看 `accuracy` 和脚本是否能连通；正式记录指标时应跑完整测试集，并参考 `per_label` 和混淆矩阵。

槽位抽取使用 `field_precision`、`field_recall`、`field_f1`、整条样本 `exact_match_rate` 和 `required_fields_match_rate`。`exact_match_rate` 会惩罚多抽字段，`required_fields_match_rate` 更关注 expected 里的关键字段是否全部抽对。覆盖率不用于评估模型效果，只用于评估单元测试对代码路径的覆盖程度。

SQL 评估当前使用 `safety_rate`、`constraint_rate` 和 `full_pass_rate`：

- `safety_rate`：SQL 必须是只读 SELECT，不包含 DROP/DELETE/UPDATE/INSERT/TRUNCATE/ALTER，并且包含 LIMIT。
- `constraint_rate`：在安全通过基础上，必须包含测试集定义的关键约束，例如城市、区域、预算。
- `full_pass_rate`：在关键约束通过基础上，进一步检查 should include，例如朝向、整租、主卧等软约束。

SQL Exec 评估在静态 SQL 评估之后运行，使用 `exec_rate`、`db_error_rate`、`empty_result_rate`、`result_constraint_rate`、`latency_avg_ms`、`latency_p95_ms` 和 `latency_p99_ms`：

- `exec_rate`：通过静态安全检查后，真实数据库执行成功的比例。
- `db_error_rate`：执行阶段出现 SQL 语法、未知列、连接、超时等错误的比例。
- `empty_result_rate`：SQL 成功执行但返回 0 行的比例，用于发现测试数据缺失或查询条件过严。
- `result_constraint_rate`：返回行满足基础结果约束的比例，当前检查 LIMIT、价格边界，以及简单 `LIKE` / `=` 文本谓词。复杂 OR 条件会记录为 `unchecked_constraints`，不强行判错。
- `latency_p95_ms` / `latency_p99_ms`：真实查询延迟分位数，样本少时只作为冒烟指标，正式压测要用 Locust。

E2E 评估当前使用 `task_success_rate`、`route_success_rate`、`must_visit_success_rate`、`order_check_success_rate` 和 `store_check_success_rate`。它验证图级业务链路，包括意图路由、补充信息中断、推荐后预约选择、预订信息收集、订单写入 store、查询历史和普通问答。当前 E2E runner 会模拟推荐数据库结果和预订工具调用，不验证真实 SQL 执行；真实数据库可执行率由后续 SQL Exec runner 单独负责。

## 阶段总结

当前测试体系已经覆盖代码确定性、图级链路、LLM 语义能力和真实 SQL 执行四个层面：

- 单元测试：43/43 通过，覆盖率 81.02%，超过当前 75% 门槛。
- 集成测试：4/4 通过，覆盖主图路由、中断恢复、预订下单和 store 写入。
- 测试集评估：共 50 条样本，覆盖意图识别、槽位抽取、SQL 约束和 E2E 流程。
- 意图识别：15/15 通过，Accuracy 100%，Macro F1 100%。
- 槽位抽取：Field F1 92.93%，Required Match 86.67%，Exact Match 66.67%。
- SQL 静态评估：10/10 通过，Safety、Constraint、Full Pass 均为 100%。
- SQL Exec：10/10 通过，Exec Rate 100%，DB Error Rate 0%，Empty Result Rate 0%，Result Constraint Rate 100%，p95 约 2.07ms。
- E2E：10/10 通过，任务完成、路由、关键节点访问、订单检查和 store 检查均为 100%。

本阶段最有价值的发现是 SQL 评测必须对齐生产数据语义。早期测试数据使用中文枚举，无法暴露 `rooms=1`、`position LIKE '%南%'`、`rent_type='整租'` 这类在生产库中可能查不到结果的问题。对齐生产样例后，prompt、fixture、静态验收和执行验收都改为生产枚举口径，例如 `rooms=one/two/three`、`position=south/north/east/west`、`rent_type=whole_rent`、`devices=toilet/cook/gas`。

## 下一步计划

1. 建立 Locust 压测基线：先保持当前同步实现不变，压测 LangGraph Server 的推荐、预约、查询和普通问答入口，记录 RPS、平均延迟、p95/p99、失败率、LLM 调用耗时和数据库查询耗时。
2. 明确压测场景配比：建议先使用轻量读场景为主，例如普通问答 30%、推荐 40%、推荐后预约 20%、查询我的 10%；再单独做推荐链路高压测试，因为推荐会触发 LLM 和 SQL。
3. 增加性能报告目录：建议使用 `reports/load/<timestamp>_<commit>_<scenario>/` 保存 Locust HTML/CSV、压测配置、样本请求和结论摘要，避免只截图无法复现。
4. 根据压测结果再决定是否异步化：如果瓶颈在 LLM/API 等待，优先评估 async 节点、连接池和限流；如果瓶颈在 MySQL，优先看索引、SQL 查询形态和连接池；如果瓶颈在 LangGraph Server 并发配置，再调整 worker/并发参数。
5. 准备面试口径：把测试分成单元测试、集成测试、测试集评估、SQL Exec、压测五层，说明每一层解决的问题不同，覆盖率只用于代码路径质量，不用于评价 LLM 语义效果。
