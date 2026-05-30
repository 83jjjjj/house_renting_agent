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
