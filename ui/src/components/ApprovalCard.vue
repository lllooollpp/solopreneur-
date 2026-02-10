<template>
  <div v-if="show" class="approval-overlay" @click.self="deny">
    <div class="approval-card">
      <div class="card-header">
        <h3>⚠️ 工具调用审批</h3>
        <button class="btn-close" @click="deny">✕</button>
      </div>
      
      <div class="card-body">
        <div class="tool-info">
          <div class="info-row">
            <span class="label">工具名称:</span>
            <span class="value">{{ toolName }}</span>
          </div>
          <div class="info-row">
            <span class="label">调用原因:</span>
            <span class="value">{{ reason }}</span>
          </div>
        </div>
        
        <div class="arguments-section">
          <h4>参数详情</h4>
          <pre class="arguments-code">{{ formattedArguments }}</pre>
        </div>
        
        <div class="warning-box">
          <strong>🔒 安全提示:</strong> 此工具具有敏感权限，请仔细检查参数后决定是否执行。
        </div>
      </div>
      
      <div class="card-actions">
        <button class="btn-deny" @click="deny">拒绝</button>
        <button class="btn-approve" @click="approve">批准执行</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  show: boolean
  toolName: string
  arguments: Record<string, any>
  reason: string
}>()

const emit = defineEmits<{
  approve: []
  deny: []
}>()

const formattedArguments = computed(() => {
  return JSON.stringify(props.arguments, null, 2)
})

function approve() {
  emit('approve')
}

function deny() {
  emit('deny')
}
</script>

<style scoped>
.approval-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: fadeIn 0.2s;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.approval-card {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.3s;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e0e0e0;
}

.card-header h3 {
  margin: 0;
  color: #ff6f00;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #616161;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background 0.2s;
}

.btn-close:hover {
  background: #f5f5f5;
}

.card-body {
  padding: 1.5rem;
  max-height: 60vh;
  overflow-y: auto;
}

.tool-info {
  margin-bottom: 1.5rem;
}

.info-row {
  display: flex;
  margin-bottom: 0.8rem;
  gap: 1rem;
}

.info-row .label {
  font-weight: 600;
  color: #616161;
  min-width: 80px;
}

.info-row .value {
  color: #2c3e50;
  flex: 1;
}

.arguments-section {
  margin-bottom: 1.5rem;
}

.arguments-section h4 {
  margin: 0 0 0.5rem 0;
  color: #2c3e50;
  font-size: 1rem;
}

.arguments-code {
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 1rem;
  overflow-x: auto;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.9rem;
  line-height: 1.5;
  color: #2c3e50;
}

.warning-box {
  background: #fff3e0;
  border-left: 4px solid #ff9800;
  padding: 1rem;
  border-radius: 4px;
  color: #f57c00;
  font-size: 0.9rem;
  line-height: 1.5;
}

.warning-box strong {
  display: block;
  margin-bottom: 0.3rem;
}

.card-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e0e0e0;
}

.btn-deny,
.btn-approve {
  padding: 0.7rem 1.8rem;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-deny {
  background: #f5f5f5;
  color: #616161;
}

.btn-deny:hover {
  background: #e0e0e0;
}

.btn-approve {
  background: #4caf50;
  color: white;
}

.btn-approve:hover {
  background: #43a047;
}
</style>
