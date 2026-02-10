# 数据模型设计：前端、Copilot 与企业微信

**版本**：1.0  
**状态**：完成

## 1. 系统核心状态 (Frontend State)

### AgentStatus (枚举)
- `IDLE`: 待命状态，可以接受新指令。
- `THINKING`: 正在思考/调用工具，任务栈中存在活动任务。
- `ERROR`: 出现关键错误，需要用户干预。
- `OFFLINE`: 后端 Sidecar 未启动或连接断开。

### ChatMessage (对话条目)
- `id` (UUID): 唯一标识。
- `role` (string): `user`, `assistant`, `system`, `tool`.
- `content` (string): 文本内容。
- `tool_call` (optional): 触发的工具名称及参数。
- `timestamp` (ISO8601): 发送时间。

## 2. 认证模型 (Authentication)

### CopilotSession
- `github_access_token` (string): 获取到的长期 GitHub Token。
- `copilot_token` (string): 交换得到的短期运行 Token。
- `expires_at` (int): `copilot_token` 的过期时间戳。

## 3. 技能与配置模型 (Configuration)

### SkillItem
- `name` (string): 技能唯一名称。
- `source` (enum): `workspace`, `managed`, `bundled`。
- `enabled` (boolean): 是否启用。
- `description` (string): 描述。
- `variables` (dict): 技能需要的环境变量及其当前值。
- `overridden` (boolean): 是否在更高级别被重写。

## 4. 渠道模型 (Channel)

### WeComConfig
- `corp_id` (string): 企业 ID。
- `agent_id` (string): 系统生成的应用 ID。
- `secret` (string): 用于获取 Access Token（发送消息）。
- `token` (string): 接口验证 Token（接收消息）。
- `aes_key` (string): 消息加密解密 Key。

## 5. 总线事件负载 (Bus Event Payloads)

### BusEvent
- `event_type` (string): 例如 `message.received`, `agent.thought`, `tool.invoked`。
- `payload` (json): 对应事件的详细数据模型。
- `trace_id` (string): 用于跨组件追踪请求链路。
