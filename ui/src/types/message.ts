/**
 * 消息相关类型定义
 */

/** 工具调用活动（嵌入在消息流中） */
export interface ToolActivity {
  id: string
  type: 'tool_start' | 'tool_end'
  toolName: string
  delegateAgent?: string
  toolArgs?: Record<string, any>
  durationMs?: number
  resultLength?: number
  resultPreview?: string
  timestamp: number
}

/** 技能活动 */
export interface SkillActivity {
  id: string
  type: 'skill_start' | 'skill_end'
  skillName: string
  toolName?: string
  toolArgs?: Record<string, any>
  durationMs?: number
  resultLength?: number
  resultPreview?: string
  timestamp: number
}

/** 角色委派活动 */
export interface DelegateActivity {
  id: string
  type: 'delegate'
  role: string
  task: string
  timestamp: number
}

/** LLM 调用活动 */
export interface LLMActivity {
  id: string
  type: 'llm_start' | 'llm_end'
  iteration: number
  agentName?: string
  model?: string
  durationMs?: number
  tokens?: number
  timestamp: number
}

/** 内联活动事件联合类型 */
export type InlineActivity = ToolActivity | SkillActivity | DelegateActivity | LLMActivity

/** 消息块：文本块或活动块 */
export interface TextBlock {
  kind: 'text'
  content: string
}

export interface ActivityBlock {
  kind: 'activity'
  activity: InlineActivity
}

export type MessageBlock = TextBlock | ActivityBlock

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  agentName?: string
  content: string
  toolCall?: {
    name: string
    arguments: Record<string, any>
  }
  /** 内联活动事件（工具调用、角色委派等），按时间顺序 */
  activities?: InlineActivity[]
  timestamp: string
}

export interface MessageHistory {
  messages: ChatMessage[]
  totalCount: number
}
