import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Agent 状态枚举
 */
export enum AgentStatus {
  IDLE = 'IDLE',
  THINKING = 'THINKING',
  ERROR = 'ERROR',
  OFFLINE = 'OFFLINE'
}

/**
 * Agent Store
 * 管理 Agent 的运行状态
 */
export const useAgentStore = defineStore('agent', () => {
  const status = ref<AgentStatus>(AgentStatus.OFFLINE)
  const currentTask = ref<string | null>(null)
  const errorMessage = ref<string | null>(null)
  const uptimeSeconds = ref<number>(0)
  const totalMessages = ref<number>(0)

  /**
   * 设置 Agent 状态
   */
  function setStatus(newStatus: AgentStatus) {
    status.value = newStatus
  }

  /**
   * 设置当前任务
   */
  function setCurrentTask(task: string | null) {
    currentTask.value = task
  }

  /**
   * 设置错误信息
   */
  function setError(message: string | null) {
    errorMessage.value = message
    if (message) {
      status.value = AgentStatus.ERROR
    }
  }

  /**
   * 清除错误
   */
  function clearError() {
    errorMessage.value = null
    if (status.value === AgentStatus.ERROR) {
      status.value = AgentStatus.IDLE
    }
  }

  /**
   * 更新统计数据
   */
  function updateStats(uptime: number, messages: number) {
    uptimeSeconds.value = uptime
    totalMessages.value = messages
  }

  return {
    status,
    currentTask,
    errorMessage,
    uptimeSeconds,
    totalMessages,
    setStatus,
    setCurrentTask,
    setError,
    clearError,
    updateStats
  }
})
