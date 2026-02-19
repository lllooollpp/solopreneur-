# 文档索引（Docs Index）

本目录用于统一维护 solopreneur 文档导航。  
当前产品定位：**一人软件公司的 AI 执行平台**。

---

## 快速入口

- 总体架构： [架构设计](ARCHITECTURE.md)
- 开发规范： [开发指南](development-guide.md)
- Agent 总览： [Agent 目录与映射](AGENT_CATALOG.md)
- Skill 总览： [Skill 目录与映射](SKILL_CATALOG.md)
- **交流与社区**： [COMMUNICATION.md](COMMUNICATION.md)

---

## 0）启动与配置（Start）

适合刚接手项目或新环境初始化。

- [技能与配置](SKILLS_AND_CONFIG.md)
- [Providers 快速开始](providers_quickstart.md)
- [Provider 接入指南](PROVIDER_GUIDE.md)
- [Provider 集成指南](PROVIDER_INTEGRATION_GUIDE.md)
- [Token Pool 指南](TOKEN_POOL_GUIDE.md)
- [Token 控制指南](TOKEN_CONTROL_GUIDE.md)
- [本地模型优化](LOCAL_MODEL_OPTIMIZATION.md)
- [Copilot 版本区分指南](COPILOT_DISTINCTION_GUIDE.md)

---

## 1）需求与规划（Plan）

适合需求拆分、范围界定、路线规划。

- [开发指南](development-guide.md)
- [EFFC 说明](effc.md)
- [SDLC Agent/Skill 路线图](SDLC_AGENT_SKILL_ROADMAP.md)
- [API 规格草案](api-spec.md)
- **需求规格书模板**： [spec-template.md](spec-template.md)

建议优先 Agent：initializer、product_manager、architect  
相关映射： [Agent 目录与映射](AGENT_CATALOG.md) / [Skill 目录与映射](SKILL_CATALOG.md)

---

## 2）实现与协作（Build）

适合编码实现、多 Agent 协作、上下文管理。

- [架构设计](ARCHITECTURE.md)
- [子 Agent 系统](SUBAGENT_SYSTEM.md)
- [技能与配置](SKILLS_AND_CONFIG.md)
- [记忆系统](MEMORY_SYSTEM.md)

建议优先 Agent：developer、code_reviewer、tester、devops

---

## 3）测试与发布（Release）

适合上线前质量把关、发布窗口与回滚预案。

- [开发指南](development-guide.md)
- [测试指南](TEST_GUIDE.md)
- [安全审计报告](SECURITY_AUDIT_REPORT.md)
- [Token 控制指南](TOKEN_CONTROL_GUIDE.md)
- [Token Pool 指南](TOKEN_POOL_GUIDE.md)

建议优先 Agent：tester、security_engineer、release_manager、sre_engineer

---

## 4）运行与运维（Operate）

适合生产运行、通道接入、稳定性观察。

- [企业微信隧道指南](WECOM_TUNNEL_GUIDE.md)
- [Providers 快速开始](providers_quickstart.md)
- [长任务重构说明](LONG_RUNNING_AGENT_REFACTOR.md)

---

## 5）演进与治理（Evolve）

适合架构升级、持久化改造、规范沉淀。

- [持久化 P0 清单](PERSISTENCE_P0_CHECKLIST.md)
- [持久化阶段进展](PERSISTENCE_PHASE_PROGRESS.md)
- [SDLC Agent/Skill 路线图](SDLC_AGENT_SKILL_ROADMAP.md)
- [中等风险修复清单](MEDIUM_RISK_FIXES.md)
- [优化总结](OPTIMIZATION_SUMMARY.md)

---

## 附录

- [spec 目录](spec)
- [Agent 目录与映射](AGENT_CATALOG.md)
- [Skill 目录与映射](SKILL_CATALOG.md)

---

如果新增文档，请同步更新本索引。