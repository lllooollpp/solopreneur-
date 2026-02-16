/**
 * GitHub Copilot 认证 API
 */
import apiClient from './client'

export interface DeviceFlowResponse {
  deviceCode: string
  userCode: string
  verificationUri: string
  expiresIn: number
  interval: number
}

export interface TokenResponse {
  status: 'success' | 'pending' | 'error'
  githubToken?: string
  copilotToken?: string
  expiresAt?: string
  error?: string
}

export interface AuthStatus {
  authenticated: boolean
  expiresAt: string | null
}

/**
 * 启动 GitHub Copilot OAuth 设备流
 */
export async function startDeviceFlow(): Promise<DeviceFlowResponse> {
  const response = await apiClient.post<any>('/api/auth/github/device')
  return {
    deviceCode: response.device_code,
    userCode: response.user_code,
    verificationUri: response.verification_uri,
    expiresIn: response.expires_in,
    interval: response.interval
  }
}

/**
 * 轮询 GitHub Token（非阻塞）
 */
export async function pollToken(deviceCode: string): Promise<TokenResponse> {
  try {
    const response = await apiClient.post<any>('/api/auth/github/token', {
      device_code: deviceCode
    })
    
    // 后端成功返回 {github_token, copilot_token, expires_at}
    if (response.github_token && response.copilot_token) {
      return {
        status: 'success',
        githubToken: response.github_token,
        copilotToken: response.copilot_token,
        expiresAt: response.expires_at
      }
    } else {
      return { status: 'pending' }
    }
  } catch (error: any) {
    // 处理不同的 HTTP 状态码
    if (error.response?.status === 202) {
      // 202: authorization_pending - 继续等待
      return { status: 'pending' }
    } else if (error.response?.status === 429) {
      // 429: slow_down - 请求过快
      throw error // 让调用方处理 429
    } else if (error.response?.status === 403) {
      // 403: expired_token 或 access_denied
      return {
        status: 'error',
        error: error.response?.data?.detail || '授权已过期或被拒绝'
      }
    } else {
      return {
        status: 'error',
        error: error.message || '轮询失败'
      }
    }
  }
}

/**
 * 获取当前认证状态
 */
export async function getAuthStatus(): Promise<AuthStatus> {
  const response = await apiClient.get<any>('/api/auth/github/status')
  return {
    authenticated: response.authenticated,
    expiresAt: response.expires_at
  }
}
