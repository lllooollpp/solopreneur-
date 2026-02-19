# GitHub Copilot 与其他 Provider 的区分方案

## 🎯 设计目标

清晰地区分 GitHub Copilot 和其他 LLM Provider（本地模型、火山引擎等），让用户能够：
1. 明确知道当前使用哪个 Provider
2. 自由选择优先使用 Copilot 还是其他 Provider
3. 在配置界面中一目了然地管理所有 Provider

---

## 📊 界面布局

### 配置管理页面

```
┌─────────────────────────────────────────────────────────────┐
│ ⚙️ 配置管理                                                │
├─────────────────────────────────────────────────────────────┤
│ 🔧 技能列表                                                │
│ 🤖 Agents 管理                                              │
│ 🌐 LLM Providers                                          │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ 🐙 GitHub Copilot                                     │  │
│   │   [☑️ 优先使用]  [前往账号池管理 →]                   │  │
│   │   已启用：将优先使用 GitHub Copilot（需要先登录账号）   │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
│   ─────── 或配置其他 Provider ──────                      │
│                                                             │
│   选择其他 Provider:                                         │
│   [🏠 本地接口] [🌋 火山引擎] [🌐 OpenRouter] ...          │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ 🏠 本地 OpenAI 标准接口                             │  │
│   │   本地部署的 OpenAI 兼容接口 (vLLM, Ollama 等)        │  │
│   │                                                       │  │
│   │   API Key: [dummy               👁️]                  │  │
│   │   API Base: [http://localhost:8000/v1            ]  │  │
│   │   默认模型: [llama-3-8b               ▼]             │  │
│   │   Max Tokens: [8192                              ]  │  │
│   │   Temperature: [██████████░░░░░░░] 0.7              │  │
│   │                                                       │  │
│   │   [🔍 测试连接]  [💾 保存配置]                         │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
│   💡 Provider 选择逻辑                                       │
│   • 优先使用 Copilot: 如果勾选"优先使用"，系统将优先使用     │
│     GitHub Copilot                                          │
│   • 其他 Provider: Copilot 未启用或不可用时，按以下优先级    │
│     使用: 本地 → 火山引擎 → OpenRouter → Anthropic → ...  │
└─────────────────────────────────────────────────────────────┘
```

### 聊天界面

```
┌─────────────────────────────────────────────────────────────┐
│ 💬 聊天                                                    │
├─────────────────────────────────────────────────────────────┤
│ ChatView - 项目: solopreneur                                    │
│   [🏠 本地接口] [🟢 已连接]     [模型: llama-3-8b ▼]       │
│                                                             │
│ ┌─────────────────────────────────────────────────────┐    │
│ │                                                     │    │
│ │  你好                                               │    │
│ │                                                     │    │
│ └─────────────────────────────────────────────────────┘    │
│                                                             │
│ ┌─────────────────────────────────────────────────────┐    │
│ │  你好！我是 solopreneur，很高兴为您服务。                   │    │
│ └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Provider 选择逻辑

### 前端配置界面

```
用户操作:
1. 勾选 [☑️ 优先使用] → 设置 copilot_priority = true
2. 取消勾选 [☐ 优先使用] → 设置 copilot_priority = false
3. 配置其他 Provider (如本地 vLLM) → 保存到 config.json
```

### 后端 Provider 工厂

```python
# solopreneur/core/dependencies.py

def get_llm_provider(self, force_copilot: bool = False):
    """
    获取 LLM Provider

    优先级:
    1. force_copilot=True → 强制使用 Copilot
    2. copilot_priority=True → 优先使用 Copilot（需要已登录）
    3. 其他 Provider → 按工厂优先级选择
    """

    # 1. 强制使用 Copilot
    if force_copilot:
        copilot = self.get_copilot_provider()
        if copilot.session:
            return copilot

    # 2. 检查配置的 copilot_priority
    config = self.get_config()
    if config.providers.copilot_priority:
        copilot = self.get_copilot_provider()
        if copilot.session:
            logger.info("使用 GitHub Copilot Provider (配置优先)")
            return copilot

    # 3. 使用其他 Provider
    if self._llm_provider is None:
        from solopreneur.providers.factory import create_llm_provider
        self._llm_provider = create_llm_provider(config)

        # 如果没有配置其他 Provider，回退到 Copilot
        if self._llm_provider is None:
            copilot = self.get_copilot_provider()
            if copilot.session:
                self._llm_provider = copilot

    return self._llm_provider
```

### Provider 工厂优先级

```python
# solopreneur/providers/factory.py

def create_llm_provider(config, default_model=None):
    """
    按优先级创建 Provider

    优先级:
    1. vLLM (本地)     ← api_base 存在
    2. 火山引擎        ← api_key 存在
    3. OpenRouter     ← api_key 存在
    4. Anthropic      ← api_key 存在
    5. OpenAI         ← api_key 存在
    6. Groq           ← api_key 存在
    7. Gemini         ← api_key 存在
    """

    providers_config = config.providers

    # 1. 本地 vLLM
    if providers_config.vllm.api_base:
        return LiteLLMProvider(...)

    # 2. 火山引擎
    if providers_config.zhipu.api_key:
        return LiteLLMProvider(...)

    # ... 其他 Provider

    # 没有配置任何 Provider
    return None
```

---

## 📋 配置示例

### 场景 1: 优先使用 Copilot

```json
{
  "providers": {
    "copilot_priority": true,
    "openai": {
      "api_key": "sk-..."
    }
  },
  "agents": {
    "defaults": {
      "model": "gpt-5-mini"
    }
  }
}
```

**结果**:
- 前端显示: ☑️ 优先使用 Copilot
- 后端日志: `使用 GitHub Copilot Provider (配置优先)`
- 聊天界面: 🐙 Copilot

### 场景 2: 使用本地模型

```json
{
  "providers": {
    "copilot_priority": false,
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
- 前端显示: ☐ 优先使用 Copilot
- 后端日志: `使用 vLLM Provider (本地 OpenAI 标准接口)`
- 聊天界面: 🏠 本地接口

### 场景 3: Copilot 回退

```json
{
  "providers": {
    "copilot_priority": true
  }
}
```

**Copilot 未登录**:

**结果**:
- 后端尝试使用 Copilot → 失败
- 回退到其他 Provider → 无配置
- 错误提示: 请先配置 LLM Provider

---

## 🎨 前端实现

### ProviderConfig.vue 关键部分

```vue
<template>
  <!-- GitHub Copilot 独立区域 -->
  <div class="copilot-section">
    <div class="section-header">
      <div class="section-title">
        <span class="title-icon">🐙</span>
        <h4>GitHub Copilot</h4>
      </div>
      <div class="priority-toggle">
        <label class="toggle-switch">
          <input type="checkbox" v-model="copilotPriority"
            @change="toggleCopilotPriority" />
          <span class="slider"></span>
        </label>
        <span class="toggle-label">
          {{ copilotPriority ? '优先使用' : '不优先' }}
        </span>
      </div>
    </div>
    <router-link to="/accounts">前往账号池管理 →</router-link>
  </div>

  <div class="divider">
    <span>或配置其他 Provider</span>
  </div>

  <!-- 其他 Provider 选择器（不含 Copilot） -->
  <div class="provider-tabs">
    <button v-for="opt in otherProviderOptions"
      :key="opt.value"
      @click="selectProvider(opt.value)">
      {{ opt.icon }} {{ opt.label }}
    </button>
  </div>
</template>

<script setup>
const copilotPriority = ref(false)

const otherProviderOptions = computed(() => {
  // 过滤掉 copilot，只显示其他 Provider
  return PROVIDER_OPTIONS.filter(opt => opt.value !== 'copilot')
})

function toggleCopilotPriority() {
  providersConfig.copilot_priority = copilotPriority.value
}
</script>
```

### ChatView.vue - Provider 徽章

```vue
<template>
  <div class="header-right">
    <span v-if="currentProvider" class="provider-badge">
      {{ currentProvider }}
    </span>
    <span :class="['connection-status', isConnected ? 'connected' : 'disconnected']">
      {{ isConnected ? '🟢 已连接' : '🔴 未连接' }}
    </span>
  </div>
</template>

<script setup>
const providerNames: Record<string, string> = {
  'copilot': '🐙 Copilot',
  'vllm': '🏠 本地接口',
  'zhipu': '🌋 火山引擎',
  'openrouter': '🌐 OpenRouter',
  'anthropic': '🧠 Anthropic',
  'openai': '🤖 OpenAI',
  'groq': '⚡ Groq',
  'gemini': '💎 Gemini',
  'none': '❌ 未配置'
}

async function loadModels() {
  const response = await fetch('http://localhost:8000/api/auth/models')
  const data = await response.json()

  currentProvider.value = providerNames[data.provider] || data.provider
  // ...
}
</script>
```

---

## 🔧 后端实现

### 配置 Schema

```python
# solopreneur/config/schema.py

class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    copilot_priority: bool = False  # 是否优先使用 Copilot
```

### /api/auth/models - 返回 Provider 信息

```python
# solopreneur/api/routes/auth.py

@router.get("/auth/models")
async def get_models():
    manager = get_component_manager()
    config = manager.get_config()

    # 检查 Copilot 优先级
    if config.providers.copilot_priority:
        copilot = manager.get_copilot_provider()
        if copilot.session:
            return {
                "models": ["gpt-5-mini", "gpt-4o", "claude-sonnet-4"],
                "authenticated": True,
                "provider": "copilot"
            }

    # 检查其他 Provider
    if config.providers.vllm.api_base:
        return {
            "models": ["llama-3-8b", "llama-3-70b"],
            "authenticated": True,
            "provider": "vllm"
        }

    # ...
```

---

## ✅ 用户体验流程

### 配置 Copilot

1. 打开配置管理 → LLM Providers
2. 勾选 [☑️ 优先使用 Copilot]
3. 点击 [前往账号池管理] → 添加 Copilot 账号
4. 保存配置
5. 重启服务

### 配置本地模型

1. 打开配置管理 → LLM Providers
2. 取消勾选 [☐ 优先使用 Copilot]
3. 选择 [🏠 本地 OpenAI 标准接口]
4. 填写:
   - API Base: `http://localhost:8000/v1`
   - API Key: `dummy`
   - 默认模型: `llama-3-8b`
5. 点击 [🔍 测试连接]
6. 点击 [💾 保存配置]
7. 重启服务

### 切换 Provider

**Copilot → 本地**:
1. 配置管理 → LLM Providers
2. 取消勾选 [☐ 优先使用 Copilot]
3. 配置本地 Provider
4. 保存并重启服务

**本地 → Copilot**:
1. 配置管理 → LLM Providers
2. 勾选 [☑️ 优先使用 Copilot]
3. 保存并重启服务

---

## 📝 关键改动总结

### 前端

1. **ProviderConfig.vue**:
   - 独立的 Copilot 区域（带优先级开关）
   - 分隔符清晰区分 Copilot 和其他 Provider
   - 其他 Provider 列表不包含 Copilot

2. **types/provider.ts**:
   - 添加 `copilot_priority: boolean` 到 `ProvidersConfig`

3. **ChatView.vue**:
   - Provider 徽章显示当前使用的 Provider
   - 模型列表根据 Provider 动态更新

### 后端

1. **config/schema.py**:
   - 添加 `copilot_priority: bool` 到 `ProvidersConfig`

2. **core/dependencies.py**:
   - `get_llm_provider()` 支持 `copilot_priority` 配置
   - 优先级: 强制 Copilot > 配置优先 > 其他 Provider > 回退 Copilot

3. **api/routes/auth.py**:
   - `/api/auth/models` 返回 `provider` 字段
   - 根据优先级逻辑返回对应的模型列表

---

## 🚀 使用建议

### 日常使用场景

1. **在线工作**: 勾选优先使用 Copilot，享受高质量回复
2. **离线开发**: 配置本地 vLLM，完全本地运行
3. **成本控制**: 使用火山引擎、Groq 等低成本 Provider
4. **混合使用**: 不同项目使用不同 Provider，通过配置切换

### 最佳实践

1. **配置文件管理**: 为不同项目创建不同的配置文件
2. **热切换**: 修改配置后只需重启服务，无需重新编译
3. **监控日志**: 启动服务时查看日志确认使用的 Provider
4. **测试连接**: 配置新 Provider 前先测试连接
