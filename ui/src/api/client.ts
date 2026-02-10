import axios, { type AxiosInstance } from 'axios'

/**
 * API 客户端基类
 * 所有 API 调用应使用此客户端
 */
class ApiClient {
  private client: AxiosInstance

  constructor(baseURL: string = 'http://localhost:8000') {
    this.client = axios.create({
      baseURL,
      timeout: 30000, // 30 秒超时（GitHub OAuth 轮询需要更长时间）
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // 请求拦截器
    this.client.interceptors.request.use(
      (config) => {
        // 可以在此添加认证 token
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response.data,
      (error) => {
        console.error('API 请求失败:', error)
        return Promise.reject(error)
      }
    )
  }

  /**
   * GET 请求
   */
  async get<T = any>(url: string, params?: any): Promise<T> {
    return this.client.get(url, { params })
  }

  /**
   * POST 请求
   */
  async post<T = any>(url: string, data?: any): Promise<T> {
    return this.client.post(url, data)
  }

  /**
   * PUT 请求
   */
  async put<T = any>(url: string, data?: any): Promise<T> {
    return this.client.put(url, data)
  }

  /**
   * DELETE 请求
   */
  async delete<T = any>(url: string): Promise<T> {
    return this.client.delete(url)
  }
}

export const apiClient = new ApiClient()
export default apiClient
