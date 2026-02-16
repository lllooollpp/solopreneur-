<template>
  <div class="flow">
    <div class="flow-header">
      <h2>🔄 工作流展示</h2>
      <div class="flow-controls">
        <span :class="['connection-status', isConnected ? 'connected' : 'disconnected']">
          {{ isConnected ? '🟢 已连接' : '🔴 未连接' }}
        </span>
        <button @click="startTestFlow" class="btn-test" :disabled="!isConnected">
          ▶️ 测试工作流
        </button>
      </div>
    </div>
    
    <!-- 任务追踪面板 -->
    <div class="flow-section">
      <h3>📋 当前任务栈</h3>
      <div v-if="taskStack.length === 0" class="empty">
        <p>暂无活跃任务</p>
      </div>
      <div v-else class="task-list">
        <div
          v-for="(task, index) in taskStack"
          :key="index"
          class="task-item"
        >
          <div class="task-header">
            <span class="task-index">{{ index + 1 }}</span>
            <span class="task-name">{{ task.name }}</span>
            <span :class="['task-status', task.status]">
              {{ statusText(task.status) }}
            </span>
          </div>
          <div class="task-description">{{ task.description }}</div>
        </div>
      </div>
    </div>
    
    <!-- 历史快照 -->
    <div class="flow-section">
      <h3>📜 历史快照</h3>
      <div v-if="snapshots.length === 0" class="empty">
        <p>暂无历史记录</p>
      </div>
      <div v-else class="snapshot-list">
        <div
          v-for="snapshot in snapshots"
          :key="snapshot.id"
          class="snapshot-item"
        >
          <div class="snapshot-time">{{ formatTime(snapshot.timestamp) }}</div>
          <div class="snapshot-summary">{{ snapshot.summary }}</div>
        </div>
      </div>
    </div>
    
    <!-- 执行日志 -->
    <div class="flow-section" v-if="flowLogs.length > 0">
      <h3>📊 执行日志</h3>
      <div class="log-panel">
        <div v-for="(log, index) in flowLogs.slice(-20)" :key="index" class="log-line">
          {{ log }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Task {
  id: string
  name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

interface Snapshot {
  id: string
  timestamp: string
  summary: string
}

const taskStack = ref<Task[]>([])
const snapshots = ref<Snapshot[]>([])
const isConnected = ref(false)
const currentFlow = ref('')
const flowLogs = ref<string[]>([])

let ws: WebSocket | null = null

// 连接 WebSocket
function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return
  
  ws = new WebSocket('ws://localhost:8000/ws/flow')
  
  ws.onopen = () => {
    isConnected.value = true
    console.log('Flow WebSocket connected')
  }
  
  ws.onclose = () => {
    isConnected.value = false
    console.log('Flow WebSocket disconnected')
    // 3秒后自动重连
    setTimeout(connectWebSocket, 3000)
  }
  
  ws.onerror = (error) => {
    console.error('Flow WebSocket error:', error)
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    flowLogs.value.push(`[${new Date().toLocaleTimeString()}] ${data.type}: ${data.message || JSON.stringify(data)}`)
    
    switch (data.type) {
      case 'start':
        currentFlow.value = data.flow_id
        taskStack.value = []
        break
        
      case 'node_start':
        taskStack.value.push({
          id: data.node_id,
          name: data.node_id,
          description: data.message || '执行中...',
          status: 'running'
        })
        break
        
      case 'node_complete':
        const task = taskStack.value.find(t => t.id === data.node_id)
        if (task) {
          task.status = 'completed'
          task.description = data.message || '完成'
        }
        break
        
      case 'edge_active':
        // 边激活效果
        console.log(`Edge active: ${data.from_node} -> ${data.to_node}`)
        break
        
      case 'flow_complete':
        // 工作流完成，添加快照
        snapshots.value.unshift({
          id: data.flow_id,
          timestamp: new Date().toISOString(),
          summary: `工作流 ${data.flow_id} 执行完成，共 ${taskStack.value.length} 个任务`
        })
        break
        
      case 'error':
        const failedTask = taskStack.value.find(t => t.status === 'running')
        if (failedTask) {
          failedTask.status = 'failed'
          failedTask.description = data.message || '执行失败'
        }
        break
    }
  }
}

// 开始一个工作流（测试用）
function startTestFlow() {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    alert('WebSocket 未连接')
    return
  }
  
  ws.send(JSON.stringify({
    type: 'start',
    flow: {
      id: 'test-flow-' + Date.now(),
      nodes: ['分析输入', '生成计划', '执行任务', '输出结果'],
      edges: []
    }
  }))
}

onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
    ws = null
  }
})

function statusText(status: string): string {
  const statusMap: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[status] || status
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString('zh-CN')
}
</script>

<style scoped>
.flow {
  padding: 2rem;
  max-width: 1200px;
}

h2 {
  margin-bottom: 1.5rem;
  color: #2c3e50;
}

.flow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.flow-header h2 {
  margin: 0;
}

.flow-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.connection-status {
  font-size: 0.9rem;
  padding: 0.3rem 0.8rem;
  border-radius: 12px;
}

.connection-status.connected {
  background: #e8f5e9;
  color: #2e7d32;
}

.connection-status.disconnected {
  background: #ffebee;
  color: #c62828;
}

.btn-test {
  padding: 0.5rem 1rem;
  background: #1976d2;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.2s;
}

.btn-test:hover:not(:disabled) {
  background: #1565c0;
}

.btn-test:disabled {
  background: #bdbdbd;
  cursor: not-allowed;
}

.log-panel {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.85rem;
  padding: 1rem;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.log-line {
  padding: 0.2rem 0;
  border-bottom: 1px solid #333;
}

.log-line:last-child {
  border-bottom: none;
}

.flow-section {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.flow-section h3 {
  margin-bottom: 1rem;
  color: #2c3e50;
}

.empty {
  text-align: center;
  color: #9e9e9e;
  padding: 2rem;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.task-item {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 1rem;
  transition: box-shadow 0.2s;
}

.task-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.task-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.task-index {
  background: #2c3e50;
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
}

.task-name {
  flex: 1;
  font-weight: 600;
  color: #2c3e50;
}

.task-status {
  padding: 0.3rem 0.8rem;
  border-radius: 12px;
  font-size: 0.85rem;
  font-weight: 500;
}

.task-status.pending {
  background: #e0e0e0;
  color: #616161;
}

.task-status.running {
  background: #fff3e0;
  color: #ef6c00;
}

.task-status.completed {
  background: #e8f5e9;
  color: #2e7d32;
}

.task-status.failed {
  background: #ffebee;
  color: #c62828;
}

.task-description {
  color: #616161;
  font-size: 0.9rem;
  padding-left: 3rem;
}

.snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.snapshot-item {
  padding: 1rem;
  background: #f5f5f5;
  border-radius: 4px;
  border-left: 4px solid #1976d2;
}

.snapshot-time {
  font-size: 0.85rem;
  color: #9e9e9e;
  margin-bottom: 0.3rem;
}

.snapshot-summary {
  color: #2c3e50;
}
</style>
