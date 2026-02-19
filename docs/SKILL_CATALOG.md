# Skill 目录与映射

本文档列出当前项目技能清单、用途与关联 Agent。

## Skill 总览

| Skill 名称 | 主要用途 | 被哪些 Agent 使用 | 文件 |
|---|---|---|---|
| architecture | 系统架构、模块设计、API 设计 | architect | [skills/architecture/SKILL.md](../skills/architecture/SKILL.md) |
| code-review | 代码审查、质量分级、改进建议 | code_reviewer, security_engineer | [skills/code-review/SKILL.md](../skills/code-review/SKILL.md) |
| config-extract | 提取项目配置并写回项目环境变量 | （工具型，按需调用） | [skills/config-extract/SKILL.md](../skills/config-extract/SKILL.md) |
| dependency-analysis | 多任务依赖分析与串并行编排 | （调度辅助） | [skills/dependency-analysis/SKILL.md](../skills/dependency-analysis/SKILL.md) |
| devops | CI/CD、容器化、部署配置 | devops, sre_engineer | [skills/devops/SKILL.md](../skills/devops/SKILL.md) |
| github | 使用 gh CLI 进行 PR/Issue/CI 操作 | developer | [skills/github/SKILL.md](../skills/github/SKILL.md) |
| observability | SLI/SLO、发布后健康度与告警策略 | sre_engineer | [skills/observability/SKILL.md](../skills/observability/SKILL.md) |
| release | 发布清单、上线与回滚 Runbook | release_manager | [skills/release/SKILL.md](../skills/release/SKILL.md) |
| requirements | 需求分析、用户故事、验收标准 | initializer, product_manager, release_manager, wiki_writer | [skills/requirements/SKILL.md](../skills/requirements/SKILL.md) |
| security | 应用安全审查与加固建议 | security_engineer | [skills/security/SKILL.md](../skills/security/SKILL.md) |
| skill-creator | 设计与创建新 Skill 的方法论 | （元技能） | [skills/skill-creator/SKILL.md](../skills/skill-creator/SKILL.md) |
| summarize | URL/文件/视频摘要提取 | （工具型，按需调用） | [skills/summarize/SKILL.md](../skills/summarize/SKILL.md) |
| testing | 测试策略、单元/集成/E2E 自动化 | tester | [skills/testing/SKILL.md](../skills/testing/SKILL.md) |
| tmux | 通过 tmux 远程控制交互式会话 | （工具型，按需调用） | [skills/tmux/SKILL.md](../skills/tmux/SKILL.md) |
| weather | 天气查询（无 API Key） | （工具型，按需调用） | [skills/weather/SKILL.md](../skills/weather/SKILL.md) |
| wiki | 项目 Wiki/文档体系生成 | wiki_writer | [skills/wiki/SKILL.md](../skills/wiki/SKILL.md) |

## 与 Agent 的关系说明

- Agent 在其 YAML 定义中通过 `skills:` 字段绑定技能。
- Skill 是“知识/流程模板”，Agent 是“执行角色”；两者组合构成具体执行能力。

## 相关链接

- [Agent 目录与映射](AGENT_CATALOG.md)
- [技能与配置](SKILLS_AND_CONFIG.md)
- [文档索引](index.md)
