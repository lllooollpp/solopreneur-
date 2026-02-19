# SDLC Agent / Skill 评估与补强（CR）

## 一、当前能力覆盖（原有）

- 需求：`product_manager` + `requirements`
- 架构：`architect` + `architecture`
- 开发：`developer` + `github`
- 质量：`code_reviewer` + `tester` + `testing`
- 运维：`devops` + `devops`
- 文档：`wiki_writer` + `wiki`

## 二、缺口分析

对照标准软件生命周期（需求→设计→开发→测试→发布→运维→复盘），主要缺口：

1. **安全左移不足**：缺少独立安全角色与技能
2. **发布治理不足**：缺少 Go/No-Go、回滚与变更窗口管理
3. **可观测性不足**：缺少发布后 SLO/告警验证

## 三、本次补强内容

### 新增 Agents

- `security_engineer`（安全工程师）
- `release_manager`（发布经理）
- `sre_engineer`（SRE 工程师）

### 新增 Skills

- `security`（安全审查与加固）
- `release`（发布计划与回滚）
- `observability`（可观测性与可靠性）

### 工作流增强

- `feature` 流程新增 **安全审查** 步骤
- `deploy` 流程扩展为：测试 → 发布准备 → 部署执行 → 发布后验证

## 四、后续建议（可选）

1. 增加 `compliance_auditor`（合规审计）Agent
2. 增加 `cost_optimizer`（成本优化）Agent
3. 将工作流指标（成功率、失败原因、耗时）写入 SQLite 统一看板
