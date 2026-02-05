---
description: 按计划模板推进设计产出，生成设计文档。
scripts:
  sh: scripts/bash/setup-plan.sh --json
  ps: scripts/powershell/setup-plan.ps1 -Json
agent_scripts:
  sh: scripts/bash/update-agent-context.sh __AGENT__
  ps: scripts/powershell/update-agent-context.ps1 -AgentType __AGENT__
---

## 用户输入

```text
$ARGUMENTS
```

请务必在分析前充分考虑用户输入（如有）。

## 执行步骤

1. **初始化**：从仓库根目录运行 `{SCRIPT}`，解析 FEATURE_SPEC、IMPL_PLAN、SPECS_DIR、BRANCH 的 JSON 输出。对于参数中的单引号（如 "I'm Groot"），使用转义语法：如 'I'\''m Groot'（或尽可能使用双引号："I'm Groot"）。

2. **加载上下文**：读取 FEATURE_SPEC 和 `/memory/constitution.md`。加载 IMPL_PLAN 模板（已复制）。

3. **执行计划工作流**：按照 IMPL_PLAN 模板中的结构：
   - 填充技术上下文（将未知项标记为"需要澄清"）
   - 从组织法则中填充组织法则检查部分
   - 评估关键点（如果违反未经证实则ERROR）
   - 第 0 阶段：生成 research.md（解决所有需要澄清项）
   - 第 1 阶段：生成 data-model.md、contracts/、quickstart.md
   - 第 1 阶段：通过运行代理脚本更新代理上下文
   - 重新评估设计后的组织法则检查

4. **停止并报告**：命令在第 2 阶段计划后结束。报告分支、IMPL_PLAN 路径和生成的工件。

## 阶段

### 第 0 阶段：大纲与研究

1. **从上述技术上下文中提取未知项**：
   - 对于每个需要澄清项 → 研究任务
   - 对于每个依赖项 → 最佳实践任务
   - 对于每个集成项 → 模式任务

2. **生成并派发研究代理**：

   ```text
   对于技术上下文中的每个未知项：
     任务："为 {功能上下文} 研究 {未知项}"
   对于每个技术选择：
     任务："在 {领域} 中查找 {技术} 的最佳实践"
   ```

3. **在 `research.md` 中整合发现**，使用格式：
   - 决策：[选择了什么]
   - 理由：[为什么选择]
   - 考虑的备选方案：[评估了什么其他选项]

**输出**：research.md，解决所有需要澄清项

### 第 1 阶段：设计与合约

**先决条件**：`research.md` 完成

1. **从功能规范中提取实体** → `data-model.md`：
   - 实体名称、字段、关系
   - 来自需求的验证规则
   - 如果适用的状态转换

2. **从功能需求生成 API 合约**：
   - 对于每个用户动作 → 端点
   - 使用标准的 REST/GraphQL 模式
   - 将 OpenAPI/GraphQL 模式输出到 `/contracts/`

3. **代理上下文更新**：
   - 运行 `{AGENT_SCRIPT}`
   - 这些脚本检测正在使用的 AI 代理
   - 更新相应的代理特定上下文文件
   - 仅添加当前计划中的新技术
   - 保留标记之间的手动添加

**输出**：data-model.md、/contracts/*、quickstart.md、代理特定文件

## 关键规则

- 使用绝对路径
- 关键点失败或未解决的澄清上出错
