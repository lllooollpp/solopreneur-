import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { client } from '@/api/client'

/**
 * Agent 类型
 */
export interface Agent {
  name: string
  title: string
  emoji: string
  description: string
  type: string
  domain: string
  source: 'preset' | 'custom'
  metadata: Record<string, any>
}

/**
 * Agent 详情
 */
export interface AgentDetail extends Agent {
  system_prompt: string
  skills: string[]
  tools: string[] | null
  max_iterations: number
  temperature: number | null
  output_format: string
}

/**
 * 创建 Agent 请求
 */
export interface CreateAgentRequest {
  name: string
  title: string
  emoji?: string
  description?: string
  system_prompt: string
  type?: string
  skills?: string[]
  tools?: string[]
  max_iterations?: number
  temperature?: number
  output_format?: string
  metadata?: Record<string, any>
}

/**
 * Agents Store
 * 管理可配置的 Agents
 */
export const useAgentsStore = defineStore('agents', () => {
  // State
  const agents = ref<Agent[]>([])
  const currentAgent = ref<AgentDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const agentsByDomain = computed(() => {
    const grouped: Record<string, Agent[]> = {}
    for (const agent of agents.value) {
      const domain = agent.domain || 'general'
      if (!grouped[domain]) {
        grouped[domain] = []
      }
      grouped[domain].push(agent)
    }
    return grouped
  })

  const customAgents = computed(() => 
    agents.value.filter(a => a.source === 'custom')
  )

  const presetAgents = computed(() => 
    agents.value.filter(a => a.source === 'preset')
  )

  // Actions
  /**
   * 加载所有 Agents
   */
  async function loadAgents(filters?: { domain?: string; source?: string }) {
    loading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      if (filters?.domain) params.append('domain', filters.domain)
      if (filters?.source) params.append('source', filters.source)
      
      const response = await client.get(`/api/v1/agents?${params}`)
      agents.value = response.data.agents || []
    } catch (err: any) {
      error.value = err.response?.data?.detail || '加载 Agents 失败'
      console.error('Failed to load agents:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载单个 Agent 详情
   */
  async function loadAgentDetail(name: string) {
    loading.value = true
    error.value = null
    
    try {
      const response = await client.get(`/api/v1/agents/${name}`)
      currentAgent.value = response.data
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || '加载 Agent 详情失败'
      console.error('Failed to load agent detail:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建 Agent
   */
  async function createAgent(request: CreateAgentRequest) {
    loading.value = true
    error.value = null
    
    try {
      const response = await client.post('/api/v1/agents', request)
      await loadAgents() // 刷新列表
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || '创建 Agent 失败'
      console.error('Failed to create agent:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新 Agent
   */
  async function updateAgent(name: string, updates: Partial<CreateAgentRequest>) {
    loading.value = true
    error.value = null
    
    try {
      const response = await client.put(`/api/v1/agents/${name}`, updates)
      await loadAgents() // 刷新列表
      if (currentAgent.value?.name === name) {
        await loadAgentDetail(name) // 刷新当前详情
      }
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || '更新 Agent 失败'
      console.error('Failed to update agent:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除 Agent
   */
  async function deleteAgent(name: string) {
    loading.value = true
    error.value = null
    
    try {
      await client.delete(`/api/v1/agents/${name}`)
      agents.value = agents.value.filter(a => a.name !== name)
      if (currentAgent.value?.name === name) {
        currentAgent.value = null
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || '删除 Agent 失败'
      console.error('Failed to delete agent:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 重新加载 Agents
   */
  async function reloadAgents() {
    loading.value = true
    error.value = null
    
    try {
      await client.post('/api/v1/agents/reload')
      await loadAgents()
    } catch (err: any) {
      error.value = err.response?.data?.detail || '重载 Agents 失败'
      console.error('Failed to reload agents:', err)
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    agents,
    currentAgent,
    loading,
    error,
    // Getters
    agentsByDomain,
    customAgents,
    presetAgents,
    // Actions
    loadAgents,
    loadAgentDetail,
    createAgent,
    updateAgent,
    deleteAgent,
    reloadAgents,
  }
})
