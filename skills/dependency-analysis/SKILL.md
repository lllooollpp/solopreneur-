---
name: dependency-analysis
description: 自动识别任务依赖并选择串行/并行编排策略
always: true
---

# Dependency Analysis Skill

目标：在多 Agent 协作前，先判断任务依赖，避免盲目串行或盲目并行。

## 执行原则

1. **优先自动调度**：默认使用 `delegate_auto`。
2. **显式依赖优先**：如果用户已给出 `depends_on`，严格遵守。
3. **无依赖时自动推断**：
   - 同文件/同模块改动 → 串行（避免冲突）
   - 前后端独立模块、文档/脚本互不覆盖 → 并行
   - 集成测试/发布/评审 → 依赖实现任务
4. **高风险任务保守串行**：数据库迁移、核心鉴权、跨模块重构。
5. **并行后必须汇总校验**：接口契约、编译、关键路径测试。

## 建议流程

1. 拆分任务为 jobs
2. 使用 `delegate_auto(jobs=..., max_parallel=...)`
3. 对失败分支定向重试（`delegate` 或二次 `delegate_auto`）
4. 最终由主控 Agent 汇总并给出交付结论
