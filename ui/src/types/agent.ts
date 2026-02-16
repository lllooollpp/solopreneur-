/**
 * Agent 状态类型定义
 */

export enum AgentStatus {
  IDLE = 'IDLE',
  THINKING = 'THINKING',
  ERROR = 'ERROR',
  OFFLINE = 'OFFLINE'
}

export interface AgentState {
  status: AgentStatus
  currentTask: string | null
  errorMessage: string | null
  uptimeSeconds: number
  totalMessages: number
}
