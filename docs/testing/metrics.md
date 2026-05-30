# 测试指标记录

## 指标说明

- Unit Coverage：单元测试覆盖率，使用 `coverage.py` + `pytest-cov`。
- Unit Pass：单元测试通过数。
- Intent Acc：意图识别准确率。
- Slot F1：槽位抽取 F1。
- SQL Safe：SQL 安全率，只允许只读 SELECT，并要求 LIMIT。
- SQL Exec：SQL 可执行率。
- E2E Success：端到端任务完成率。
- p95 Latency：压测 p95 延迟。

## 基线

| Date | Commit | Unit Coverage | Unit Pass | Intent Acc | Slot F1 | SQL Safe | SQL Exec | E2E Success | p95 Latency | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-05-30 | 658887e | 71% | 5/5 | - | - | - | - | - | - | 初始单元测试基线 |
| 2026-05-30 | working tree | 81.49% | 12/12 | - | - | - | - | - | - | 补充主图路由、查询历史、推荐默认值和预订分支测试 |

## 目标

| Stage | Unit Coverage | Intent Acc | Slot F1 | SQL Safe | SQL Exec | E2E Success |
|---|---:|---:|---:|---:|---:|---:|
| v1 | >=75% | >=90% | >=85% | 100% | >=90% | >=80% |
| v2 | >=80% | >=93% | >=88% | 100% | >=95% | >=85% |
