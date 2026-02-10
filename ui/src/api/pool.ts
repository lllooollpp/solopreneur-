/**
 * Token 池管理 API
 * 多账号登录、状态查询、刷新、移除
 */
import apiClient from './client'

// ========================================================================
// 类型定义
// ========================================================================

export interface PoolSlot {
  slot_id: number
  label: string
  state: 'active' | 'cooling' | 'expired' | 'dead'
  cooling_remaining: string
  total_requests: number
  total_429s: number
  token_expires: string
}

export interface PoolStatus {
  authenticated: boolean
  slots: PoolSlot[]
  active_count: number
  total_count: number
}

export interface DeviceFlowInfo {
  device_code: string
  user_code: string
  verification_uri: string
  expires_in: number
  interval: number
}

export interface PoolPollResult {
  status: 'success' | 'pending' | 'slow_down' | 'error'
  slot_id?: number
  label?: string
  expires_at?: string
  error?: string
}

// ========================================================================
// API 函数
// ========================================================================

/**
 * 获取 Token 池状态
 */
export async function getPoolStatus(): Promise<PoolStatus> {
  return apiClient.get<PoolStatus>('/api/auth/pool/status')
}

/**
 * 启动新账号的设备流登录
 */
export async function startPoolLogin(label: string = ''): Promise<DeviceFlowInfo> {
  const response = await apiClient.post<any>('/api/auth/pool/login', { label })
  return {
    device_code: response.device_code,
    user_code: response.user_code,
    verification_uri: response.verification_uri,
    expires_in: response.expires_in,
    interval: response.interval,
  }
}

/**
 * 轮询登录结果
 */
export async function pollPoolLogin(
  deviceCode: string,
  slotId: number = 0,
  label: string = ''
): Promise<PoolPollResult> {
  return apiClient.post<PoolPollResult>('/api/auth/pool/poll', {
    device_code: deviceCode,
    slot_id: slotId,
    label,
  })
}

/**
 * 移除指定 slot
 */
export async function removePoolSlot(slotId: number): Promise<{ success: boolean; message: string }> {
  return apiClient.delete(`/api/auth/pool/${slotId}`)
}

/**
 * 刷新指定 slot 的 Token
 */
export async function refreshPoolSlot(slotId: number): Promise<{ success: boolean; message: string; slot?: PoolSlot }> {
  return apiClient.post(`/api/auth/pool/${slotId}/refresh`)
}

/**
 * 更新指定 slot 的标签
 */
export async function updateSlotLabel(slotId: number, label: string): Promise<{ success: boolean; label: string }> {
  return apiClient.put(`/api/auth/pool/${slotId}/label`, { label })
}

/**
 * 退出所有账号
 */
export async function logoutAll(): Promise<{ success: boolean; message: string }> {
  return apiClient.post('/api/auth/github/logout')
}
