import axios from 'axios'

const API_BASE = 'http://localhost:8000/api'

export interface ProvidersConfig {
  anthropic: { api_key: string; api_base?: string | null }
  openai: { api_key: string; api_base?: string | null }
  openrouter: { api_key: string; api_base?: string | null }
  groq: { api_key: string; api_base?: string | null }
  zhipu: { api_key: string; api_base?: string | null }
  vllm: { api_key: string; api_base?: string | null }
  gemini: { api_key: string; api_base?: string | null }
  copilot_priority: boolean
}

export interface AgentDefaults {
  model: string
  max_tokens: number
  temperature: number
  review_mode: 'auto' | 'manual'
}

export async function getProvidersConfig(): Promise<ProvidersConfig> {
  const response = await axios.get(`${API_BASE}/config/providers`)
  return response.data
}

export async function updateProvidersConfig(config: ProvidersConfig): Promise<void> {
  await axios.post(`${API_BASE}/config/providers`, config)
}

export async function getAgentDefaults(): Promise<AgentDefaults> {
  const response = await axios.get(`${API_BASE}/config/agent-defaults`)
  return response.data
}

export async function updateAgentDefaults(config: Partial<AgentDefaults>): Promise<void> {
  await axios.post(`${API_BASE}/config/agent-defaults`, config)
}

export async function testProviderConnection(provider: string, config: { api_key: string; api_base?: string | null }): Promise<{ success: boolean; error?: string }> {
  const response = await axios.post(`${API_BASE}/config/providers/test`, { provider, config })
  return response.data
}
