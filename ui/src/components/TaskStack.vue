<template>
  <div class="task-stack-panel">
    <div class="panel-header">
      <h4>📋 任务栈</h4>
      <button class="btn-collapse" @click="collapsed = !collapsed">
        {{ collapsed ? '▶' : '▼' }}
      </button>
    </div>
    
    <div v-if="!collapsed" class="panel-body">
      <div v-if="tasks.length === 0" class="empty-state">
        <p>暂无活跃任务</p>
      </div>
      
      <div v-else class="tasks-list">
        <div
          v-for="(task, index) in tasks"
          :key="index"
          :class="['task-item', task.status]"
        >
          <div class="task-index">{{ index + 1 }}</div>
          <div class="task-content">
            <div class="task-name">{{ task.name }}</div>
            <div class="task-progress">
              <div
                class="progress-bar"
                :style="{ width: `${task.progress}%` }"
              ></div>
            </div>
          </div>
          <div :class="['status-dot', task.status]"></div>
        </div>
      </div>
      
      <!-- 压缩快照预览 -->
      <div v-if="latestSnapshot" class="snapshot-preview">
        <div class="snapshot-header">
          <span>🗜️ 最近压缩</span>
          <span class="snapshot-time">{{ formatTime(latestSnapshot.timestamp) }}</span>
        </div>
        <div class="snapshot-summary">{{ latestSnapshot.summary }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Task {
  name: string
  status: 'pending' | 'running' | 'completed'
  progress: number
}

interface Snapshot {
  timestamp: string
  summary: string
}

const props = defineProps<{
  tasks: Task[]
  snapshots?: Snapshot[]
}>()

const collapsed = ref(false)

const latestSnapshot = computed(() => {
  if (!props.snapshots || props.snapshots.length === 0) return null
  return props.snapshots[props.snapshots.length - 1]
})

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.task-stack-panel {
  position: fixed;
  right: 2rem;
  top: 120px;
  width: 320px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  z-index: 100;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #e0e0e0;
}

.panel-header h4 {
  margin: 0;
  color: #2c3e50;
  font-size: 1rem;
}

.btn-collapse {
  background: none;
  border: none;
  font-size: 1rem;
  color: #616161;
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  transition: background 0.2s;
}

.btn-collapse:hover {
  background: #f5f5f5;
}

.panel-body {
  max-height: 500px;
  overflow-y: auto;
}

.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: #9e9e9e;
}

.tasks-list {
  padding: 0.5rem;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.8rem;
  margin-bottom: 0.5rem;
  border-radius: 6px;
  background: #f5f5f5;
  transition: all 0.2s;
}

.task-item:hover {
  background: #e8e8e8;
}

.task-item.running {
  background: #fff3e0;
  border-left: 3px solid #ff9800;
}

.task-item.completed {
  background: #e8f5e9;
  border-left: 3px solid #4caf50;
}

.task-index {
  background: #2c3e50;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 600;
  flex-shrink: 0;
}

.task-content {
  flex: 1;
  min-width: 0;
}

.task-name {
  font-size: 0.9rem;
  color: #2c3e50;
  margin-bottom: 0.3rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-progress {
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: #1976d2;
  transition: width 0.3s;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.pending {
  background: #9e9e9e;
}

.status-dot.running {
  background: #ff9800;
  animation: pulse 1.5s infinite;
}

.status-dot.completed {
  background: #4caf50;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.snapshot-preview {
  margin: 0.5rem;
  padding: 0.8rem;
  background: #f5f5f5;
  border-radius: 6px;
  border-left: 3px solid #1976d2;
}

.snapshot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
  font-size: 0.85rem;
  color: #616161;
}

.snapshot-time {
  font-weight: 500;
}

.snapshot-summary {
  font-size: 0.9rem;
  color: #2c3e50;
  line-height: 1.4;
}
</style>
