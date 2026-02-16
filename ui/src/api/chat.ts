/**
 * 聊天消息 API
 */
import apiClient from './client'
import type { ChatMessage } from '@/types/message'

/**
 * 发送聊天消息
 */
export async function sendChatMessage(content: string): Promise<ChatMessage> {
  const response = await apiClient.post<{ message: ChatMessage }>('/api/chat', {
    content
  })
  return response.message
}

/**
 * 获取聊天历史
 */
export async function getChatHistory(limit: number = 50): Promise<ChatMessage[]> {
  const response = await apiClient.get<{ messages: ChatMessage[] }>('/api/chat/history', {
    limit
  })
  return response.messages
}

/**
 * 清除聊天历史
 */
export async function clearChatHistory(): Promise<void> {
  await apiClient.delete('/api/chat/history')
}

/**
 * 批准工具调用
 */
export async function approveToolCall(messageId: string): Promise<void> {
  await apiClient.post(`/api/chat/tool-approval/${messageId}`, {
    approved: true
  })
}

/**
 * 拒绝工具调用
 */
export async function denyToolCall(messageId: string): Promise<void> {
  await apiClient.post(`/api/chat/tool-approval/${messageId}`, {
    approved: false
  })
}
