# solopreneur 开发指南（面向一人软件公司）

## 1. 项目定位

solopreneur 是一个面向“一人软件公司”的 AI 执行平台。

目标是把个人开发者的核心流程串起来：

1. 需求澄清
2. 架构设计
3. 编码实现
4. 测试验证
5. 发布与文档

它不是单纯对话助手，而是以项目交付为中心的工程执行系统。

## 2. 推荐开发原则

- **Project-Centric**：所有能力优先围绕真实项目目录和代码仓库展开。
- **Config-Driven**：行为尽量可配置，避免硬编码策略。
- **Safe-by-Default**：默认开启路径沙箱、命令限制、输入校验。
- **Execution First**：优先支持“可执行动作”，不仅是文字回答。
- **Small but Complete**：保持轻量，同时保证从输入到交付的闭环能力。

## 3. 代码结构（当前项目）

```
solopreneur/
├── agent/          # Agent 核心（loop/context/memory/subagent/tools）
├── api/            # FastAPI API 与 WebSocket
├── channels/       # 通道层（当前重点: WeCom，可扩展）
├── providers/      # 模型 Provider 与 Token 池
├── projects/       # 项目管理与项目环境变量
├── workflow/       # 多 Agent 工作流
├── cron/           # 定时任务
├── heartbeat/      # 心跳任务
├── session/        # 会话管理
└── config/         # 配置 schema 与加载
```

## 4. 变更优先级建议

### P0（必须）
- 安全边界：鉴权、签名校验、限流、工具沙箱。
- 模型一致性：对话、子任务、Wiki、定时任务统一模型路由。
- 可观测性：调用链、错误、token 成本可追踪。

### P1（建议）
- 通用 webhook 接入层。
- 简化版初始化向导（聚焦 workspace/provider/channel 三步）。

### P2（长期）
- 更多通道和生态集成。
- 更强的记忆检索与自动化能力。

## 5. 提交前检查清单

- 是否符合“一人软件公司交付场景”？
- 是否影响模型选择一致性？
- 是否引入新的安全风险？
- 是否补充了必要文档与示例配置？
- 是否可在本地快速回归验证？