# Agent 目录与映射

本文档列出当前项目内置 Agent，以及它们对应的 Skill 绑定关系。

## Agent 总览

| Agent 名称 | 标题 | 主要职责 | 绑定 Skills | 定义文件 |
|---|---|---|---|---|
| architect | 架构师 | 架构设计、技术选型、API/数据模型设计 | architecture | [agents/architect.yaml](../agents/architect.yaml) |
| assistant | 通用助手 | 通用问答与日常任务处理 | 无（按工具能力） | [agents/assistant.yaml](../agents/assistant.yaml) |
| code_reviewer | 代码审查员 | 代码质量/安全/可维护性审查 | code-review | [agents/code_reviewer.yaml](../agents/code_reviewer.yaml) |
| developer | 开发工程师 | 功能实现、修复、代码落盘 | github | [agents/developer.yaml](../agents/developer.yaml) |
| devops | DevOps 工程师 | CI/CD、容器化、部署与运维配置 | devops | [agents/devops.yaml](../agents/devops.yaml) |
| initializer | 需求分解师 | 将需求拆分为可执行 Feature 列表 | requirements | [agents/initializer.yaml](../agents/initializer.yaml) |
| product_manager | 产品经理 | 需求分析、用户故事、验收标准 | requirements | [agents/product_manager.yaml](../agents/product_manager.yaml) |
| release_manager | 发布经理 | 发布计划、上线检查、回滚策略 | release, requirements | [agents/release_manager.yaml](../agents/release_manager.yaml) |
| security_engineer | 安全工程师 | 安全审查、风险分级、修复建议 | security, code-review | [agents/security_engineer.yaml](../agents/security_engineer.yaml) |
| sre_engineer | SRE 工程师 | 可观测性、SLO、稳定性评估 | observability, devops | [agents/sre_engineer.yaml](../agents/sre_engineer.yaml) |
| tester | 测试工程师 | 测试设计、自动化测试、执行验证 | testing | [agents/tester.yaml](../agents/tester.yaml) |
| wiki_writer | Wiki 文档工程师 | 项目文档/Wiki 生成与补全 | wiki, requirements | [agents/wiki_writer.yaml](../agents/wiki_writer.yaml) |

## 按交付阶段查看 Agent

### 需求与规划
- initializer
- product_manager

### 设计与实现
- architect
- developer

### 质量与风险
- tester
- code_reviewer
- security_engineer

### 发布与稳定性
- release_manager
- sre_engineer
- devops

### 文档与通用支持
- wiki_writer
- assistant

## 相关链接

- [Skill 目录与映射](SKILL_CATALOG.md)
- [架构设计](ARCHITECTURE.md)
- [子 Agent 系统](SUBAGENT_SYSTEM.md)
- [文档索引](index.md)
