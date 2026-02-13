# Persistence 改造阶段进度（核心回归）

## 阶段 1：持久化分层与核心落库（已完成）

目标：建立清晰存储分层，核心数据改为 SQLite。

修改内容：
- 新增存储引擎与服务层
  - nanobot/storage/sqlite_store.py
  - nanobot/storage/services.py
  - nanobot/storage/__init__.py
  - nanobot/storage/README.md
- 会话改造
  - nanobot/session/manager.py（SQLite 主读写 + JSONL 懒迁移）
- 项目改造
  - nanobot/projects/manager.py（SQLite 主读写 + projects.json 迁移）
- 可观测性接入
  - nanobot/agent/core/loop.py（llm_usage 记录）
  - nanobot/agent/core/subagent.py（subagent_tasks 状态记录）

提交：
- c1ea286 feat: add sqlite persistence services, usage telemetry and subagent task tracking

---

## 阶段 2：P0 清单与执行标准（已完成）

目标：固定核心回归标准，确保可复验。

修改内容：
- docs/PERSISTENCE_P0_CHECKLIST.md（P0-1 到 P0-5 检查项 + 执行结果）

提交：
- （待本次阶段提交一起记录）

---

## 阶段 3：核心回归自动化脚本（已完成）

目标：将 P0 核心验证脚本化，便于后续重复执行。

修改内容：
- scripts/p0_core_regression.py
  - 校验会话链路
  - 校验项目链路
  - 校验 usage 与子任务状态链路

执行结果：
- PASS（session_flow / project_flow / usage_task_flow 全通过）

提交：
- （待本次阶段提交一起记录）

---

## 当前结论

核心回归阶段已达成（P0 主链路通过）。
后续可进入 P1（查询接口与可视化看板能力）。
