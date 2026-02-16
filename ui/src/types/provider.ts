export interface ProviderConfig {
  api_key: string
  api_base?: string | null
  enabled?: boolean
}

export interface ProvidersConfig {
  anthropic: ProviderConfig
  openai: ProviderConfig
  openrouter: ProviderConfig
  groq: ProviderConfig
  zhipu: ProviderConfig
  vllm: ProviderConfig
  gemini: ProviderConfig
  // Copilot 配置
  copilot_priority: boolean  // 是否优先使用 Copilot
}

export interface ProviderOption {
  value: ProviderType
  label: string
  description: string
  icon: string
}

export type ProviderType = 'copilot' | 'openai' | 'vllm' | 'zhipu' | 'openrouter' | 'groq' | 'gemini' | 'anthropic'

export const PROVIDER_OPTIONS: ProviderOption[] = [
  {
    value: 'copilot',
    label: 'GitHub Copilot',
    description: '使用 GitHub Copilot 账号，支持多账号负载均衡',
    icon: '🐙'
  },
  {
    value: 'openai',
    label: 'OpenAI',
    description: '官方 OpenAI API',
    icon: '🤖'
  },
  {
    value: 'vllm',
    label: '本地 OpenAI 标准接口',
    description: '本地部署的 OpenAI 兼容接口 (vLLM, Ollama 等)',
    icon: '🏠'
  },
  {
    value: 'zhipu',
    label: '火山引擎',
    description: '火山引擎 / 智谱 AI GLM 系列',
    icon: '🌋'
  },
  {
    value: 'openrouter',
    label: 'OpenRouter',
    description: '统一访问多个 LLM 提供商',
    icon: '🌐'
  },
  {
    value: 'groq',
    label: 'Groq',
    description: 'Groq 超快推理',
    icon: '⚡'
  },
  {
    value: 'gemini',
    label: 'Google Gemini',
    description: 'Google Gemini 模型',
    icon: '💎'
  },
  {
    value: 'anthropic',
    label: 'Anthropic Claude',
    description: 'Anthropic Claude 模型',
    icon: '🧠'
  }
]

export const MODEL_SUGGESTIONS: Record<ProviderType, string[]> = {
  copilot: ['gpt-5-mini', 'gpt-4o', 'gpt-4o-mini', 'claude-opus-4.5'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  vllm: ['llama-3-8b', 'llama-3-70b', 'qwen-7b', 'qwen-14b', 'yi-34b'],
  zhipu: ['glm-4', 'glm-4-plus', 'glm-3-turbo', 'glm-4-flash'],
  openrouter: ['anthropic/claude-3.5-sonnet', 'openai/gpt-4o', 'google/gemini-pro-1.5'],
  groq: ['llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
  gemini: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.0-pro'],
  anthropic: ['claude-3-5-sonnet', 'claude-3-5-haiku', 'claude-3-opus']
}
