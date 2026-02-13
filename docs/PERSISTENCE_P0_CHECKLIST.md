# Persistence P0-5 回归检查清单

目标：在“核心功能优先”的前提下，验证 SQLite 持久化改造不破坏主链路。

## 执行结果（2026-02-13）

已完成并通过：

- [x] 关键模块编译通过（session/project/storage/agent loop/subagent）
- [x] 会话写入与重读通过（`cli:p0-check`）
- [x] 旧 `projects.json` 迁移到 SQLite（日志显示迁移成功）
- [x] 子任务状态 upsert 正常（`p0task1: pending -> success`）
- [x] usage 记录写入正常（`llm_usage` 可查到记录）
- [x] 会话删除生效（`cli:p0-cascade` 删除后计数为 0）

待补充（不阻塞当前核心链路）：

- [ ] 通过 API 端点做一轮端到端回归（`/projects`、`/projects/{id}`）
- [ ] 在完整依赖环境下执行 `start.py` 全链路启动验证

## P0-1 会话链路（Session）

- [ ] 首次启动后可创建新会话
- [ ] 新消息可落库并按时间顺序读取
- [ ] 重启后会话历史可恢复
- [ ] 删除会话后，关联消息被级联删除
- [ ] 旧 JSONL 会话可被读取并懒迁移到 SQLite

验收标准：
- `SessionManager.get_or_create()` 与 `SessionManager.save()` 行为与旧版一致
- `SessionManager.list_sessions()` 返回最近更新排序

## P0-2 项目链路（Project）

- [ ] 项目创建成功并写入 `projects` 表
- [ ] 项目更新（名称/描述/状态）可持久化
- [ ] 项目删除后不可再查询到
- [ ] 旧 `projects.json` 可迁移到 SQLite

验收标准：
- API 层项目端点返回结构不变
- `ProjectManager` 对调用方保持兼容

## P0-3 存储分层与职责边界

- [ ] 业务层仅依赖服务层，不直接写 SQL
- [ ] SQLite 实现位于独立模块，接口语义稳定
- [ ] 存储失败不会中断主流程（有降级日志）

验收标准：
- 会话使用 `SessionPersistence`
- 项目使用 `ProjectPersistence`
- Usage 使用 `UsagePersistence`
- 子任务使用 `SubagentTaskPersistence`

## P0-4 稳定性参数

- [ ] 启用 WAL
- [ ] 启用 `busy_timeout`
- [ ] 启用 `foreign_keys`
- [ ] 保持 `synchronous=NORMAL`

验收标准：
- 并发读写无明显 `database is locked` 高频报错

## P0-5 核心回归执行项

### 启动与编译

- [ ] 关键模块编译通过
- [ ] 主流程可启动（CLI 或 API 至少一条链路）

### 关键场景

- [ ] 单轮对话保存会话
- [ ] 连续多轮对话可恢复历史
- [ ] 创建项目并读取项目列表
- [ ] 子任务执行后状态落库（pending/running/success/failed）
- [ ] LLM 调用后 usage 有记录

### 回滚策略检查

- [ ] 已有“改造前快照提交”
- [ ] 当前改造提交可独立回滚

---

## 建议执行顺序

1. 先验证 P0-1（会话）
2. 再验证 P0-2（项目）
3. 再验证 P0-3（边界）
4. 再做 P0-4（稳定性）
5. 最后执行 P0-5 完整回归

---

## 本轮实现映射（代码位置）

- 会话：nanobot/session/manager.py
- 项目：nanobot/projects/manager.py
- 存储服务层：nanobot/storage/services.py
- SQLite 引擎：nanobot/storage/sqlite_store.py
- Usage 记录：nanobot/agent/core/loop.py
- 子任务记录：nanobot/agent/core/subagent.py
