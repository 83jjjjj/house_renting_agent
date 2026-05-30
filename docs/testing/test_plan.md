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

依赖和环境：

- 依赖项：使用项目已有依赖，不额外引入第三方包。
- 必要环境变量：`DEEPSEEK_API_KEY`。
- 数据库变量：`DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`、`DB_NAME` 只在后续 SQL 执行率和 E2E 真实链路评估时需要。当前 SQL runner 只做静态安全和约束检查，不连接数据库。

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

E2E 评估当前使用 `task_success_rate`、`route_success_rate`、`must_visit_success_rate`、`order_check_success_rate` 和 `store_check_success_rate`。它验证图级业务链路，包括意图路由、补充信息中断、推荐后预约选择、预订信息收集、订单写入 store、查询历史和普通问答。当前 E2E runner 会模拟推荐数据库结果和预订工具调用，不验证真实 SQL 执行；真实数据库可执行率由后续 SQL Exec runner 单独负责。
