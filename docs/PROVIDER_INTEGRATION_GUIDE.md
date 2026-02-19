# Provider 配置系统集成指南

本文档说明如何配置和使用不同的 LLM Provider，以及它们如何与系统各部分集成。

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     前端 UI                              │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 聊天界面    │  │ 配置管理      │  │ Agent管理     │     │
│  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘     │
└────────┼─────────────────┼──────────────────┼───────────┘
         │                 │                  │
         ▼                 ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                      后端 API                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐   │
│  │ /api/chat    │  │ /api/config  │  │ WebSocket   │   │
│  │ (聊天API)     │  │ (配置管理)    │  │ (AgentLoop) │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘   │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│              组件管理器 (ComponentManager)                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  get_llm_provider()  ← 核心方法                  │   │
│  │                                                   │   │
│  │  1. 检查是否强制 Copilot                           │   │
│  │  2. 使用工厂创建 Provider                          │   │
│  │  3. 缓存 Provider 实例                            │   │
│  └──────────────────────────────────────────────────┘   │
│          │                                                │
│          ▼                                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Provider Factory (providers/factory.py)  │   │
│  │                                                   │   │
│  │  优先级检查顺序:                                   │   │
│  │  1. vLLM (本地)    ← api_base 存在                │   │
│  │  2. 火山引擎       ← api_key 存在                 │   │
│  │  3. OpenRouter    ← api_key 存在                 │   │
│  │  4. Anthropic     ← api_key 存在                 │   │
│  │  5. OpenAI        ← api_key 存在                 │   │
│  │  6. Groq          ← api_key 存在                 │   │
│  │  7. Gemini        ← api_key 存在                 │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────┐
│              Provider 实现层                               │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │ GitHubCopilot│  │ LiteLLM      │                    │
│  │ Provider     │  │ Provider     │                    │
│  └──────────────┘  └──────────────┘                    │
│       │                    │                             │
│       ▼                    ▼                             │
│  ┌────────────────────────────────────┐                 │
│  │      Base LLM Provider API         │                 │
│  │  - chat()                          │                 │
│  │  - chat_stream()                   │                 │
│  │  - get_default_model()             │                 │
│  └────────────────────────────────────┘                 │
└──────────────────────────────────────────────────────────┘
```

## 🔄 配置流程

### 1. 用户配置 Provider

**方式 A: Web UI**
```
1. 访问 http://localhost:18790
2. 进入「配置管理」
3. 选择「LLM Providers」标签
4. 选择 Provider 类型（如：本地 OpenAI 标准接口）
5. 填写配置:
   - API Base: http://localhost:8000/v1
   - API Key: dummy
   - 默认模型: llama-3-8b
6. 点击「保存配置」
```

**方式 B: 手动编辑配置文件**
```json
// ~/.solopreneur/config.json
{
  "providers": {
    "vllm": {
      "api_base": "http://localhost:8000/v1",
      "api_key": "dummy"
    }
  },
  "agents": {
    "defaults": {
      "model": "llama-3-8b"
    }
  }
}
```

### 2. 系统加载配置

启动服务时：
```python
# solopreneur/core/dependencies.py
manager = get_component_manager()
config = manager.get_config()  # 加载 ~/.solopreneur/config.json
```

### 3. 创建 Provider

首次调用 `get_llm_provider()` 时：
```python
# 1. 检查缓存
if self._llm_provider is None:
    # 2. 加载配置
    config = self.get_config()

    # 3. 调用工厂创建
    from solopreneur.providers.factory import create_llm_provider
    self._llm_provider = create_llm_provider(
        config,
        default_model=config.agents.defaults.model
    )
```

工厂检查配置优先级：
```python
# solopreneur/providers/factory.py
providers_config = config.providers

# 优先级 1: 本地 vLLM
if providers_config.vllm.api_base:
    return LiteLLMProvider(
        api_key=providers_config.vllm.api_key,
        api_base=providers_config.vllm.api_base,
        default_model=default_model
    )

# 优先级 2: 火山引擎
if providers_config.zhipu.api_key:
    return LiteLLMProvider(...)

# ... 其他 Provider
```

### 4. 使用 Provider

**聊天 API** (`/api/chat`):
```python
# solopreneur/api/routes/chat.py
provider = manager.get_llm_provider()
result = await provider.chat(
    messages=messages,
    model=request.model,
    ...
)
```

**Agent Loop** (WebSocket 聊天):
```python
# solopreneur/core/dependencies.py
async def get_agent_loop(self):
    provider = self.get_llm_provider()
    self._agent_loop = AgentLoop(
        bus=self.get_message_bus(),
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        ...
    )
```

**子 Agent 调用**:
```python
# solopreneur/agent/core/subagent.py
# SubagentManager 使用相同的 Provider
self.subagents = SubagentManager(
    provider=provider,
    workspace=workspace,
    model=self.model,
    ...
)
```

## 🎯 Provider 选择逻辑

### 当前行为

```python
def get_llm_provider(self, force_copilot: bool = False):
    """
    获取 LLM Provider

    优先级（默认 force_copilot=False）:
    1. 配置的 Provider (vLLM, 火山引擎等)
       - 如果配置了多个，按工厂优先级选择
    2. Copilot（回退）
       - 仅当没有配置任何 Provider 且 Copilot 已认证

    优先级（force_copilot=True）:
    1. Copilot（强制）
       - 仅当 Copilot 已认证
    2. None（返回 None）
    """
```

### 配置示例

#### 场景 1: 使用本地 vLLM

```json
{
  "providers": {
    "vllm": {
      "api_base": "http://localhost:8000/v1",
      "api_key": "dummy"
    }
  },
  "agents": {
    "defaults": {
      "model": "llama-3-8b"
    }
  }
}
```

**结果**:
- 聊天界面 → 使用本地模型
- Agent Loop → 使用本地模型
- 子 Agent → 使用本地模型

#### 场景 2: 使用火山引擎

```json
{
  "providers": {
    "zhipu": {
      "api_key": "your-zhipu-api-key",
      "api_base": "https://open.bigmodel.cn/api/paas/v4/"
    }
  },
  "agents": {
    "defaults": {
      "model": "glm-4"
    }
  }
}
```

**结果**:
- 聊天界面 → 使用火山引擎
- Agent Loop → 使用火山引擎
- 子 Agent → 使用火山引擎

#### 场景 3: 同时配置多个

```json
{
  "providers": {
    "vllm": {
      "api_base": "http://localhost:8000/v1",
      "api_key": "dummy"
    },
    "openai": {
      "api_key": "sk-..."
    }
  }
}
```

**结果**:
- 优先使用 vLLM（工厂优先级 1）
- OpenAI 被忽略

## 🔧 调试

### 查看当前使用的 Provider

```python
# 测试脚本
from solopreneur.core.dependencies import get_component_manager

manager = get_component_manager()
provider = manager.get_llm_provider()

print(f"Provider 类型: {type(provider).__name__}")
print(f"默认模型: {provider.get_default_model()}")
```

### 查看日志

启动服务时查看日志：
```
[INFO] 使用 vLLM Provider (本地 OpenAI 标准接口)
[INFO] 使用配置的 LLM Provider
```

### 测试连接

在配置管理界面点击「测试连接」按钮，或使用 API：
```bash
curl -X POST http://localhost:8000/api/config/providers/test \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "vllm",
    "config": {
      "api_key": "dummy",
      "api_base": "http://localhost:8000/v1"
    }
  }'
```

## 📝 注意事项

1. **配置修改后需要重启服务**
   - 后端在启动时加载配置
   - 前端修改配置后，后端不会自动重新加载

2. **Provider 实例是缓存的**
   - 首次调用 `get_llm_provider()` 后实例被缓存
   - 修改配置后需要重启服务使新配置生效

3. **模型名称必须匹配**
   - 前端选择模型 → 后端使用相同的模型名
   - 确保配置的模型在 Provider 中可用

4. **Copilot 认证与 Provider 配置**
   - Copilot 认证在「账号池管理」页面
   - 其他 Provider 在「配置管理 - LLM Providers」页面
   - 配置了其他 Provider 后，Copilot 仍可用作备用

## 🚀 快速开始

```bash
# 1. 启动本地 vLLM
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3-8B-Instruct \
  --port 8000

# 2. 配置 solopreneur
# 访问 http://localhost:18790
# 进入「配置管理」→「LLM Providers」
# 选择「本地 OpenAI 标准接口」
# 填写 API Base: http://localhost:8000/v1
# 点击「保存配置」

# 3. 重启 solopreneur
python start.py

# 4. 开始聊天
# 聊天界面会显示「🏠 本地接口」徽章
# 模型下拉框会显示本地模型列表
```
