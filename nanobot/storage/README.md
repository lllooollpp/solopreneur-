# Storage 模块说明

该目录负责 Nanobot 的数据持久化能力，当前提供 SQLite 后端。

## 设计原则

1. **单一职责**：业务层（session/projects/subagent）只调用存储接口，不关心 SQL 细节。
2. **失败隔离**：存储异常不应中断主流程（调用方统一做 `try/except` 降级）。
3. **可迁移**：通过统一的 `SQLiteStore` 方法，后续可替换为其他后端（PostgreSQL、MySQL）。
4. **向后兼容**：session/projects 支持从旧文件格式懒迁移到 SQLite。

## 当前数据域

- `sessions` / `messages`: 会话与消息历史
- `projects`: 项目元数据
- `llm_usage`: LLM 调用 Token 与耗时统计
- `subagent_tasks`: 子任务状态跟踪

## 扩展建议

- 将 `SQLiteStore` 抽象为接口（如 `StorageBackend`），实现多后端插件化。
- 将 `llm_usage` 聚合统计封装到独立 repository/service。
- 引入 schema migration（如 Alembic 或轻量版本号迁移脚本）。
