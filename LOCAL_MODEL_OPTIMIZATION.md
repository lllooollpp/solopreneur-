# 本地模型配置优化方案

## 🎯 问题

之前的实现中，聊天界面每次都从后端 API `/api/auth/models` 获取可用模型列表。对于本地模型（如 vLLM），这不合理，因为：

1. 本地模型的列表应该由用户在配置管理中设置
2. 不应该每次都向后端请求
3. 用户不应该能够随意修改本地模型名称

## ✅ 解决方案

### 核心思路

**前端从 localStorage 读取 Provider 配置，不再依赖后端 API**

```
配置管理 (ProviderConfig.vue)
    ↓ 保存配置
    ↓ 写入 localStorage
    ↓
ChatView.vue
    ↓ 从 localStorage 读取
    ↓ 显示对应的模型列表
```

---

## 📊 实现细节

### 1. ProviderConfig.vue - 保存配置

**保存时同时写入 localStorage**:

```javascript
async function saveConfig() {
  saving.value = true
  try {
    // 保存到后端
    await updateProvidersConfig(providersConfig)
    await updateAgentDefaults(agentDefaults)

    // 同时保存到 localStorage（用于前端快速读取）
    const configToSave = {
      providers: {
        copilot_priority: providersConfig.copilot_priority,
        anthropic: providersConfig.anthropic,
        openai: providersConfig.openai,
        openrouter: providersConfig.openrouter,
        groq: providersConfig.groq,
        zhipu: providersConfig.zhipu,
        vllm: providersConfig.vllm,
        gemini: providersConfig.gemini
      },
      agents: {
        defaults: agentDefaults
      }
    }
    localStorage.setItem('provider_config', JSON.stringify(configToSave))

    alert('✅ 配置已保存，请重启服务使配置生效！')
  } catch (e: any) {
    alert(`❌ 保存失败: ${e.response?.data?.detail || e.message || '未知错误'}`)
  } finally {
    saving.value = false
  }
}
```

**加载时也写入 localStorage**:

```javascript
async function loadConfig() {
  try {
    const [providers, defaults] = await Promise.all([
      getProvidersConfig(),
      getAgentDefaults()
    ])
    Object.assign(providersConfig, providers)
    Object.assign(agentDefaults, defaults)

    // 同时保存到 localStorage（供 ChatView 使用）
    const configToSave = {
      providers: { ... },
      agents: { defaults: defaults }
    }
    localStorage.setItem('provider_config', JSON.stringify(configToSave))
  } catch (e: any) {
    console.error('加载配置失败:', e)
  }
}
```

---

### 2. ChatView.vue - 从 localStorage 读取

**优先从 localStorage 读取 Provider 配置**:

```javascript
async function loadModels() {
  // 优先从 localStorage 读取 Provider 配置
  try {
    const providerConfigStr = localStorage.getItem('provider_config')
    if (providerConfigStr) {
      const providerConfig = JSON.parse(providerConfigStr)

      if (providerConfig && providerConfig.providers) {
        const providers = providerConfig.providers
        const activeModel = providerConfig.agents?.defaults?.model || ''

        // 检查 Copilot 优先级
        if (providers.copilot_priority) {
          availableModels.value = ['gpt-5-mini', 'gpt-4o', ...]
          selectedModel.value = activeModel || 'gpt-5-mini'
        }
        // 检查 vLLM (本地)
        else if (providers.vllm && providers.vllm.api_base) {
          availableModels.value = [activeModel || 'llama-3-8b']
          selectedModel.value = activeModel || 'llama-3-8b'
          // 锁定模型，不允许用户修改
          lockedModel.value = true
        }
        // 检查火山引擎
        else if (providers.zhipu && providers.zhipu.api_key) {
          availableModels.value = ['glm-4', 'glm-4-plus', ...]
          selectedModel.value = activeModel || 'glm-4'
        }
        // ... 其他 Provider

        const providerNames = {
          'copilot': '🐙 Copilot',
          'vllm': '🏠 本地接口',
          'zhipu': '🌋 火山引擎',
          // ...
        }
        currentProvider.value = providerNames[activeProvider] || activeProvider

        return
      }
    }
  } catch (e) {
    console.debug('Failed to load provider config from localStorage:', e)
  }

  // 回退：如果 localStorage 没有配置，从后端加载
  try {
    const response = await fetch('http://localhost:8000/api/auth/models')
    // ... 后端逻辑
  } catch (error) {
    console.error('Failed to load models from backend:', error)
  }
}
```

---

## 🎨 用户体验

### 配置本地 vLLM

1. 打开配置管理 → LLM Providers
2. 选择「本地 OpenAI 标准接口」
3. 填写配置:
   - API Base: `http://localhost:8000/v1`
   - API Key: `dummy`
   - **默认模型: `Qwen3-32B`** ← 用户在这里设置
4. 保存配置

### 聊天界面

- **模型下拉框**: 只显示 `Qwen3-32B`（一个选项）
- **模型锁定**: 用户无法修改（因为是本地模型）
- **Provider 徽章**: 显示 `🏠 本地接口`

---

## 🔄 配置流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 配置管理 - 保存配置                                 │
│    ↓                                                     │
│ 2. 写入 localStorage (provider_config)                   │
│    {                                                    │
│      providers: {                                         │
│        copilot_priority: false,                            │
│        vllm: {                                         │
│          api_base: 'http://localhost:8000/v1',          │
│          api_key: 'dummy'                                 │
│        }                                                   │
│      },                                                   │
│      agents: {                                            │
│        defaults: {                                          │
│          model: 'Qwen3-32B'  ← 本地模型名称              │
│        }                                                     │
│      }                                                       │
│    }                                                          │
│    ↓                                                          │
│ 3. ChatView - 从 localStorage 读取                        │
│    ↓                                                          │
│ 4. 显示模型列表 [Qwen3-32B]                           │
│    ↓                                                          │
│ 5. 锁定模型选择（lockedModel = true）                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 不同 Provider 的模型列表

### Copilot (copilot_priority = true)

```javascript
availableModels = [
  'gpt-5-mini',
  'gpt-4o',
  'gpt-4o-mini',
  'claude-sonnet-4'
]
```

### 本地 vLLM

```javascript
// 从配置读取的模型名称
const activeModel = providerConfig.agents?.defaults?.model
availableModels = [activeModel || 'llama-3-8b']
lockedModel = true  // 锁定，不允许用户修改
```

### 火山引擎

```javascript
availableModels = [
  'glm-4',
  'glm-4-plus',
  'glm-3-turbo',
  'glm-4-flash'
]
```

### OpenRouter

```javascript
availableModels = [
  'anthropic/claude-3.5-sonnet',
  'openai/gpt-4o',
  'google/gemini-pro-1.5',
  'meta-llama/llama-3.1-70b-instruct'
]
```

### Anthropic

```javascript
availableModels = [
  'claude-3-5-sonnet',
  'claude-3-5-haiku',
  'claude-3-opus'
]
```

### OpenAI

```javascript
availableModels = [
  'gpt-4o',
  'gpt-4o-mini',
  'gpt-4-turbo',
  'gpt-3.5-turbo'
]
```

### Groq

```javascript
availableModels = [
  'llama-3.1-70b-versatile',
  'llama-3.1-8b-instant',
  'mixtral-8x7b-32768'
]
```

### Gemini

```javascript
availableModels = [
  'gemini-1.5-pro',
  'gemini-1.5-flash',
  'gemini-1.0-pro'
]
```

---

## 🔑 关键优势

### 1. 前端自主控制

- ✅ 不依赖后端 API 响应
- ✅ 响应更快（从 localStorage 读取）
- ✅ 减少网络请求

### 2. 本地模型锁定

- ✅ 用户无法随意修改本地模型名称
- ✅ 避免输入错误导致调用失败
- ✅ 统一在配置管理中设置

### 3. 配置同步

- ✅ 配置管理保存后，立即在聊天界面生效
- ✅ 不需要刷新页面
- ✅ localStorage 缓存，避免重复请求

---

## 🛠️ 调试

### 检查 localStorage

打开浏览器控制台：

```javascript
// 查看当前配置
console.log(JSON.parse(localStorage.getItem('provider_config')))

// 清除配置
localStorage.removeItem('provider_config')
```

### 检查 ChatView 日志

```javascript
console.log('Loaded from localStorage:', {
  provider: activeProvider,
  models: availableModels.value,
  selected: selectedModel.value,
  locked: lockedModel.value
})
```

---

## 📝 配置示例

### 本地 Qwen3-32B 模型

```json
{
  "providers": {
    "copilot_priority": false,
    "vllm": {
      "api_base": "http://10.104.6.197:38099/v1",
      "api_key": "dummy"
    }
  },
  "agents": {
    "defaults": {
      "model": "Qwen3-32B"
    }
  }
}
```

**效果**:
- 配置管理: API Base = `http://10.104.6.197:38099/v1`
- 聊天界面: 模型下拉框只有 `Qwen3-32B`，且锁定

---

## ⚠️ 注意事项

1. **配置修改后需要刷新聊天页面**
   - 修改 Provider 配置后，刷新聊天界面
   - 或点击页面重新加载

2. **后端仍然需要配置**
   - localStorage 只用于前端显示
   - 后端仍需要从 `~/.nanobot/config.json` 读取
   - 重启服务使后端配置生效

3. **localStorage 与后端配置可能不同步**
   - 如果直接修改后端配置文件
   - 前端 localStorage 不会自动更新
   - 需要重新在配置管理中保存一次

---

## 🚀 使用流程

### 首次配置

1. 打开配置管理 → LLM Providers
2. 选择「本地 OpenAI 标准接口」
3. 填写 API Base 和模型名称
4. 保存配置
5. 刷新聊天界面
6. 模型下拉框自动显示配置的模型

### 切换 Provider

1. 配置管理 → 修改 Provider
2. 保存配置
3. 刷新聊天界面
4. 模型列表自动更新
