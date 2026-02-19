# Token 控制参数指南

## 概述

solopreneur 提供了多层次的 Token 控制机制，可以通过配置文件、API 参数等多种方式控制 Token 消耗。

---

## Token 控制参数层级

```
配置文件 (config.json)
    ↓
AgentDefaults (默认配置)
    ↓
会话级 Token 限制
    ↓
单次请求 Token 限制
```

---

## 1. 配置文件控制

### 1.1 配置文件位置
```bash
~/.solopreneur/config.json
```

### 1.2 Token 相关配置项

```json
{
  "agents": {
    "defaults": {
      // 每次对话的默认最大输出 Token 数
      "max_tokens": 8192,

      // 每个会话累计最大 Token 消耗（超限后自动压缩上下文）
      "max_tokens_per_session": 500000,

      // 最大工具调用迭代次数（间接控制 Token 消耗）
      "max_tool_iterations": 20,

      // Agent 执行总超时时间（秒）
      "agent_timeout": 1800
    }
  }
}
```

### 1.3 配置说明

| 参数 | 默认值 | 说明 | 建议范围 |
|------|--------|------|----------|
| `max_tokens` | 8192 | 单次 LLM 调用的最大输出 Token 数 | 1024 - 16384 |
| `max_tokens_per_session` | 500000 | 单个会话累计 Token 消耗上限 | 100000 - 1000000 |
| `max_tool_iterations` | 20 | 最大工具调用迭代次数 | 5 - 50 |
| `agent_timeout` | 1800 | Agent 执行总超时（秒） | 600 - 3600 |

---

## 2. API 请求参数控制

### 2.1 REST API 聊天 (`POST /api/chat`)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "content": "帮我写一个 Python 函数",
    "session_id": "my_session",
    "model": "gpt-4o",
    "max_tokens": 2048,
    "temperature": 0.7
  }'
```

**请求参数说明**：
- `max_tokens`: 单次请求的最大输出 Token 数（覆盖配置默认值）
- `temperature`: 温度参数（影响输出多样性，间接影响 Token 消耗）

### 2.2 WebSocket 聊天 (`/ws/chat`)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.send(JSON.stringify({
  type: "message",
  content: "帮我写一个 Python 函数",
  session_id: "my_session",
  model: "gpt-4o",
  max_tokens: 2048  // 控制单次响应长度
}));
```

---

## 3. Agent 定义中的 Token 控制

### 3.1 Agent 定义文件 (`.yaml`)

```yaml
name: code_assistant
title: 代码助手
system_prompt: |
  你是一个专业的代码助手...

# Token 控制参数
max_iterations: 15        # 最大迭代次数（减少工具调用次数）
temperature: 0.3          # 低温度减少输出长度
max_tokens: 4096          # 单次最大输出 Token
output_format: |
  请保持回答简洁，不超过500字
```

### 3.2 AgentDefinition 模型

```python
from solopreneur.agent.definitions.definition import AgentDefinition

agent = AgentDefinition(
    name="my_agent",
    system_prompt="...",
    max_iterations=10,      # 控制最大迭代次数
    temperature=0.5,       # 控制输出长度
    max_tokens=2048,        # 控制单次输出
    output_format="..."      # 指定输出格式限制长度
)
```

---

## 4. 代码级控制

### 4.1 创建 AgentLoop 时指定

```python
from solopreneur.agent.core.loop import AgentLoop

agent_loop = AgentLoop(
    bus=bus,
    provider=provider,
    workspace=workspace,
    model="gpt-4o",
    max_iterations=15,              # 最大迭代次数
    max_session_tokens=200000,     # 会话 Token 限制
    max_total_time=1200,           # 总时间限制（秒）
)
```

### 4.2 子 Agent Token 控制

```python
from solopreneur.agent.core.subagent import SubagentManager

subagent_manager = SubagentManager(
    provider=provider,
    workspace=workspace,
    bus=bus,
    model="gpt-4o-mini",          # 使用更便宜的模型
)
```

---

## 5. 自动上下文压缩机制

当会话 Token 累计超过 `max_tokens_per_session` 时，AgentLoop 会自动触发三层压缩：

```python
# solopreneur/agent/core/loop.py
if self.compaction.should_compact(messages, self.max_session_tokens):
    logger.info(
        f"Token累计 {total_tokens}/{self.max_session_tokens} 超限，"
        "正在压缩上下文..."
    )
    messages = await self._compact_context(messages)
```

### 三层压缩策略

1. **第一层：删除旧消息**
   - 保留最近 N 条消息

2. **第二层：压缩工具调用**
   - 将工具调用结果摘要化

3. **第三层：语义压缩**
   - 使用 LLM 总结对话历史

---

## 6. Token 使用监控

### 6.1 查看当前配置

```bash
# 查看配置文件
cat ~/.solopreneur/config.json | jq '.agents.defaults'
```

### 6.2 日志输出

AgentLoop 会输出 Token 使用情况：

```log
2024-02-10 10:30:15 | INFO | Token累计 450000/500000 (90%)
2024-02-10 10:30:16 | INFO | Token累计 505000/500000 超限，正在压缩上下文...
```

---

## 7. 节省 Token 的最佳实践

### 7.1 使用系统提示词限制输出长度

```yaml
system_prompt: |
  你是一个精简的 AI 助手。
  请用最少的文字回答问题，每条回答不超过 200 字。
  避免使用重复、冗长的表述。
```

### 7.2 优化模型选择

```json
{
  "agents": {
    "defaults": {
      "model": "gpt-4o-mini"      // 比 gpt-4o 便宜 10 倍
    }
  }
}
```

### 7.3 限制工具调用

```json
{
  "agents": {
    "defaults": {
      "max_tool_iterations": 10,   // 减少工具调用次数
      "max_subagents": 3          // 限制并发子 Agent 数
    }
  }
}
```

### 7.4 使用 Stream 模式

Stream 模式可以更早获得响应，避免等待完整结果：

```python
result = await provider.chat(
    messages=messages,
    model="gpt-4o",
    max_tokens=2048,
    stream=True  # 流式输出
)
```

### 7.5 会话管理

及时清理不需要的会话历史：

```bash
# 清空特定会话
curl -X DELETE "http://localhost:8000/api/chat/history?session_id=old_session"

# 清空所有会话
curl -X DELETE "http://localhost:8000/api/chat/history?session_id=all"
```

---

## 8. 不同场景的 Token 控制建议

### 8.1 简单问答场景

```json
{
  "agents": {
    "defaults": {
      "max_tokens": 1024,
      "max_tokens_per_session": 50000,
      "max_tool_iterations": 5
    }
  }
}
```

### 8.2 代码生成场景

```json
{
  "agents": {
    "defaults": {
      "max_tokens": 4096,           // 代码需要更多输出
      "max_tokens_per_session": 200000,
      "max_tool_iterations": 15
    }
  }
}
```

### 8.3 复杂任务场景

```json
{
  "agents": {
    "defaults": {
      "max_tokens": 8192,
      "max_tokens_per_session": 1000000,
      "max_tool_iterations": 30,
      "agent_timeout": 3600
    }
  }
}
```

---

## 9. 故障排查

### 9.1 Token 超限错误

```log
ERROR | Token累计 505000/500000 超限，压缩失败
```

**解决方案**：
1. 增加 `max_tokens_per_session`
2. 减少单次 `max_tokens`
3. 及时清理会话历史
4. 优化系统提示词长度

### 9.2 响应被截断

**原因**：`max_tokens` 设置过小

**解决方案**：
1. 增加请求中的 `max_tokens` 参数
2. 或在配置文件中增大默认值

---

## 10. API 参考速查

| API | 参数 | 默认值 | 说明 |
|-----|------|--------|------|
| `POST /api/chat` | `max_tokens` | 4096 | 单次响应最大 Token |
| 配置文件 | `agents.defaults.max_tokens` | 8192 | 默认输出 Token |
| 配置文件 | `agents.defaults.max_tokens_per_session` | 500000 | 会话累计上限 |
| 配置文件 | `agents.defaults.max_tool_iterations` | 20 | 最大工具迭代次数 |
| Agent 定义 | `max_tokens` | - | 单次输出 Token |
| Agent 定义 | `max_iterations` | 15 | 最大迭代次数 |

---

## 总结

Token 控制参数优先级：

```
API 参数 > Agent 定义 > 配置文件 > 代码默认值
```

推荐使用方式：
1. 在配置文件中设置合理的默认值
2. 为不同场景创建专门的 Agent 定义
3. 关键请求时使用 API 参数覆盖
