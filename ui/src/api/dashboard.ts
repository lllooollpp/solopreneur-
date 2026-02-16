/**
 * 仪表盘 API 客户端
 */
import type {
  DashboardStats,
  HealthCheck,
  MetricsSnapshot,
  TaskDailyResponse,
  UsageDailyResponse
} from '@/types/dashboard'

const API_BASE = 'http://localhost:8000/api/v1'

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const response = await fetch(`${API_BASE}/dashboard/stats`)
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard stats: ${response.status}`)
  }
  return response.json()
}

export async function fetchHealthCheck(): Promise<HealthCheck> {
  const response = await fetch(`${API_BASE}/dashboard/health`)
  if (!response.ok) {
    throw new Error(`Failed to fetch health check: ${response.status}`)
  }
  return response.json()
}

export async function fetchMetricsSnapshot(days: number = 7): Promise<MetricsSnapshot> {
  const response = await fetch(`${API_BASE}/metrics/snapshot?days=${days}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch metrics snapshot: ${response.status}`)
  }
  return response.json()
}

export async function fetchUsageDaily(days: number = 7, limit: number = 14): Promise<UsageDailyResponse> {
  const response = await fetch(`${API_BASE}/metrics/usage/daily?days=${days}&limit=${limit}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch usage daily: ${response.status}`)
  }
  return response.json()
}

export async function fetchTaskDaily(days: number = 7, limit: number = 50): Promise<TaskDailyResponse> {
  const response = await fetch(`${API_BASE}/metrics/tasks/daily?days=${days}&limit=${limit}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch task daily: ${response.status}`)
  }
  return response.json()
}
