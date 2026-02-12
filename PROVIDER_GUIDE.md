# LLM Provider 配置指南

Nanobot 现在支持多种 LLM Provider，包括 GitHub Copilot、OpenAI、火山引擎（智谱 AI）、本地 OpenAI 标准接口等。

## 支持的 Provider

| Provider | 说明 | API Key 来源 | 推荐模型 |
|---------|------|-------------|---------|
| GitHub Copilot | GitHub Copilot 账号，支持多账号负载均衡 | GitHub 设备流登录 | gpt-5-mini, gpt-4o |
| OpenAI | 官方 OpenAI API | [platform.openai.com](https://platform.openai.com) | gpt-4o, gpt-4o-mini |
| 本地 OpenAI 标准接口 | 本地部署的 OpenAI 兼容接口 (vLLM, Ollama 等) | 无需真实 Key | llama-3-8b, qwen-7b |
| 火山引擎 | 火山引擎 / 智谱 AI GLM 系列 | [open.bigmodel.cn](https://open.bigmodel.cn) | glm-4, glm-4-plus |
| OpenRouter | 统一访问多个 LLM 提供商 | [openrouter.ai](https://openrouter.ai) | anthropic/claude-3.5-sonnet |
| Groq | 超快推理 | [console.groq.com](https://console.groq.com) | llama-3.1-70b-versatile |
| Google Gemini | Google Gemini 模型 | [aistudio.google.com](https://aistudio.google.com) | gemini-1.5-pro |
| Anthropic Claude | Claude 模型 | [console.anthropic.com](https://console.anthropic.com) | claude-3-5-sonnet |

## 配置方式

### 方式 1: 通过 Web UI 配置

1. 启动 Nanobot 服务: `python start.py`
2. 打开浏览器访问: `http://localhost:18790`
3. 进入 **配置管理** → **LLM Providers**
4. 选择要配置的 Provider
5. 填写 API Key 和 API Base (可选)
6. 设置默认模型和其他参数
7. 点击 **测试连接** 验证配置
8. 点击 **保存配置**

### 方式 2: 手动编辑配置文件

配置文件位置: `~/.nanobot/config.json`

```json
{
  "providers": {
    "openai": {
      "api_key": "sk-...",
      "api_base": "https://api.openai.com/v1"
    },
    "vllm": {
      "api_key": "dummy",
      "api_base": "http://localhost:8000/v1"
    },
    "zhipu": {
      "api_key": "your-zhipu-api-key",
      "api_base": "https://open.bigmodel.cn/api/paas/v4/"
    }
  },
  "agents": {
    "defaults": {
      "model": "gpt-5-mini",
      "max_tokens": 8192,
      "temperature": 0.7
    }
  }
}
```

## Provider 选择优先级

系统按照以下优先级选择 Provider：

1. **vLLM** (本地部署) - 如果配置了 `api_base`
2. **火山引擎** (智谱 AI) - 如果配置了 `api_key`
3. **OpenRouter** - 如果配置了 `api_key`
4. **Anthropic Claude** - 如果配置了 `api_key`
5. **OpenAI** - 如果配置了 `api_key`
6. **Groq** - 如果配置了 `api_key`
7. **Google Gemini** - 如果配置了 `api_key`

如果配置了 GitHub Copilot 且有已认证的账号，将优先使用 Copilot。

## 本地 OpenAI 标准接口配置

如果你使用本地部署的 vLLM、Ollama 或其他 OpenAI 兼容接口：

### vLLM

```bash
# 启动 vLLM 服务
vllm serve meta-llama/Meta-Llama-3-8B-Instruct --host 0.0.0.0 --port 8000
```

配置:
```json
{
  "providers": {
    "vllm": {
      "api_key": "dummy",
      "api_base": "http://localhost:8000/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "meta-llama/Meta-Llama-3-8B-Instruct"
    }
  }
}
```

### Ollama

```bash
# 启动 Ollama
ollama serve
```

配置:
```json
{
  "providers": {
    "vllm": {
      "api_key": "dummy",
      "api_base": "http://localhost:11434/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "llama3"
    }
  }
}
```

## 火山引擎 (智谱 AI) 配置

1. 注册账号: [https://open.bigmodel.cn](https://open.bigmodel.cn)
2. 获取 API Key
3. 配置:
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

## 测试连接

配置完成后，可以通过 Web UI 的 **测试连接** 按钮验证配置是否正确。测试会发送一个简单的请求来验证 API Key 和 API Base 是否有效。

## 常见问题

### Q: 如何切换 Provider?

A: 修改配置文件中对应 Provider 的 `api_key`，或者在其他 Provider 中设置 `api_key` 并清空当前 Provider。系统会自动选择优先级最高的可用 Provider。

### Q: 同时配置了多个 Provider 会用哪个?

A: 按照优先级顺序选择，优先使用本地 vLLM，然后依次是火山引擎、OpenRouter、Anthropic、OpenAI 等。

### Q: GitHub Copilot 和其他 Provider 可以同时使用吗?

A: 可以。GitHub Copilot 优先于其他 Provider，如果 Copilot 有已认证的账号将优先使用。

### Q: 配置修改后需要重启服务吗?

A: 通过 Web UI 修改配置会自动热加载。手动修改配置文件后需要重启服务。
