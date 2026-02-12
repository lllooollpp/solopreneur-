/**
 * 仪表盘 Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DashboardStats, HealthCheck } from '@/types/dashboard'
import { fetchDashboardStats, fetchHealthCheck } from '@/api/dashboard'

export const useDashboardStore = defineStore('dashboard', () => {
  // 状态
  const stats = ref<DashboardStats | null>(null)
  const health = ref<HealthCheck | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdate = ref<Date | null>(null)

  // 计算属性
  const isHealthy = computed(() => health.value?.status === 'healthy')
  
  const agentStatusClass = computed(() => {
    if (!stats.value) return 'unknown'
    switch (stats.value.agent.status) {
      case 'IDLE': return 'idle'
      case 'THINKING': return 'thinking'
      case 'ERROR': return 'error'
      case 'OFFLINE': return 'offline'
      default: return 'unknown'
    }
  })

  const agentStatusText = computed(() => {
    if (!stats.value) return '未知'
    switch (stats.value.agent.status) {
      case 'IDLE': return '待命中'
      case 'THINKING': return '思考中'
      case 'ERROR': return '错误'
      case 'OFFLINE': return '离线'
      default: return '未知'
    }
  })

  const healthStatusText = computed(() => {
    if (!health.value) return '检测中'
    switch (health.value.status) {
      case 'healthy': return '健康'
      case 'degraded': return '降级'
      case 'unhealthy': return '异常'
      default: return '未知'
    }
  })

  const healthStatusClass = computed(() => {
    if (!health.value) return 'unknown'
    return health.value.status
  })

  // 方法
  async function loadStats() {
    loading.value = true
    error.value = null
    
    try {
      stats.value = await fetchDashboardStats()
      lastUpdate.value = new Date()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
      console.error('Failed to load dashboard stats:', e)
    } finally {
      loading.value = false
    }
  }

  async function loadHealth() {
    try {
      health.value = await fetchHealthCheck()
    } catch (e) {
      console.error('Failed to load health check:', e)
    }
  }

  async function refresh() {
    await Promise.all([loadStats(), loadHealth()])
  }

  return {
    // 状态
    stats,
    health,
    loading,
    error,
    lastUpdate,
    // 计算属性
    isHealthy,
    agentStatusClass,
    agentStatusText,
    healthStatusText,
    healthStatusClass,
    // 方法
    loadStats,
    loadHealth,
    refresh
  }
})
