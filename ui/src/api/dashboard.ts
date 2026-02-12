/**
 * 仪表盘 API 客户端
 */
import type { DashboardStats, HealthCheck } from '@/types/dashboard'

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
