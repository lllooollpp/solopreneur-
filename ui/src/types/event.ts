/**
 * 总线事件类型定义
 */

export interface BusEvent {
  event_type: 'message.received' | 'agent.thinking' | 'tool.invoked' | 'task.completed'
  payload: Record<string, any>
  trace_id: string
  timestamp: string
}

export interface WebSocketMessage {
  type: 'ping' | 'pong' | 'subscribe' | 'unsubscribe' | 'event'
  data?: any
}
