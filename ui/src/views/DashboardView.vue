<template>
  <div class="dashboard">
    <h2>📊 仪表盘</h2>
    
    <!-- Agent 状态卡片 -->
    <div class="status-card">
      <div class="status-header">
        <span class="status-label">Agent 状态</span>
        <span :class="['status-badge', statusClass]">
          {{ statusText }}
        </span>
      </div>
      
      <div class="status-details">
        <div class="detail-item">
          <span class="label">运行时长:</span>
          <span class="value">{{ uptimeFormatted }}</span>
        </div>
        <div class="detail-item">
          <span class="label">处理消息数:</span>
          <span class="value">{{ agentStore.totalMessages }}</span>
        </div>
        <div v-if="agentStore.currentTask" class="detail-item">
          <span class="label">当前任务:</span>
          <span class="value">{{ agentStore.currentTask }}</span>
        </div>
        <div v-if="agentStore.errorMessage" class="detail-item error">
          <span class="label">错误信息:</span>
          <span class="value">{{ agentStore.errorMessage }}</span>
        </div>
      </div>
    </div>
    
    <!-- 统计数据 -->
    <div class="charts-section">
      <h3>统计数据</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ agentStore.totalMessages }}</div>
          <div class="stat-label">总消息数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ agentStore.uptimeSeconds || 0 }}</div>
          <div class="stat-label">运行秒数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ statusText }}</div>
          <div class="stat-label">当前状态</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ agentStore.currentTask ? '1' : '0' }}</div>
          <div class="stat-label">活动任务</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { AgentStatus } from '@/types/agent'

const agentStore = useAgentStore()

const statusClass = computed(() => {
  switch (agentStore.status) {
    case AgentStatus.IDLE: return 'idle'
    case AgentStatus.THINKING: return 'thinking'
    case AgentStatus.ERROR: return 'error'
    case AgentStatus.OFFLINE: return 'offline'
    default: return ''
  }
})

const statusText = computed(() => {
  switch (agentStore.status) {
    case AgentStatus.IDLE: return '待命中'
    case AgentStatus.THINKING: return '思考中'
    case AgentStatus.ERROR: return '错误'
    case AgentStatus.OFFLINE: return '离线'
    default: return '未知'
  }
})

const uptimeFormatted = computed(() => {
  const seconds = agentStore.uptimeSeconds || 0
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  return `${hours}h ${minutes}m ${secs}s`
})

onMounted(async () => {
  try {
    const response = await fetch('http://localhost:8000/api/status')
    if (response.ok) {
      const data = await response.json()
      agentStore.status = data.status || AgentStatus.OFFLINE
      agentStore.uptimeSeconds = data.uptime_seconds || 0
      agentStore.totalMessages = data.total_messages || 0
    }
  } catch (error) {
    console.error('加载 Agent 状态失败:', error)
    agentStore.status = AgentStatus.OFFLINE
  }
})
</script>

<style scoped>
.dashboard {
  padding: 2rem;
  max-width: 1200px;
}

h2 {
  margin-bottom: 1.5rem;
  color: #2c3e50;
}

.status-card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e0e0e0;
}

.status-label {
  font-size: 1.1rem;
  font-weight: 600;
  color: #2c3e50;
}

.status-badge {
  padding: 0.4rem 1rem;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 600;
}

.status-badge.idle {
  background: #e8f5e9;
  color: #2e7d32;
}

.status-badge.thinking {
  background: #fff3e0;
  color: #ef6c00;
}

.status-badge.error {
  background: #ffebee;
  color: #c62828;
}

.status-badge.offline {
  background: #e0e0e0;
  color: #616161;
}

.status-details {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem;
  border-radius: 4px;
  background: #f5f5f5;
}

.detail-item.error {
  background: #ffebee;
}

.detail-item .label {
  font-weight: 500;
  color: #616161;
}

.detail-item .value {
  color: #2c3e50;
  font-weight: 600;
}

.charts-section {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.charts-section h3 {
  margin-bottom: 1rem;
  color: #2c3e50;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.stat-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1.5rem;
  border-radius: 8px;
  text-align: center;
}

.stat-card:nth-child(2) {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.stat-card:nth-child(3) {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.stat-card:nth-child(4) {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.stat-label {
  font-size: 0.9rem;
  opacity: 0.9;
}
</style>
