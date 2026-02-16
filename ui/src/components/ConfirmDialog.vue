<template>
  <div v-if="visible" class="dialog-overlay" @click="handleClose">
    <div class="dialog" @click.stop>
      <div class="dialog-header">
        <h3>{{ title }}</h3>
        <button class="btn-close" @click="handleClose">×</button>
      </div>
      
      <div class="dialog-body">
        <p class="message">{{ message }}</p>
      </div>
      
      <div class="dialog-footer">
        <button class="btn-cancel" @click="handleClose">取消</button>
        <button class="btn-confirm" @click="handleConfirm">确定</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  title: string
  message: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: []
}>()

function handleClose() {
  emit('update:visible', false)
}

function handleConfirm() {
  emit('confirm')
  emit('update:visible', false)
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: white;
  border-radius: 8px;
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.dialog-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  cursor: pointer;
  border-radius: 4px;
  color: #666;
}

.btn-close:hover {
  background: #f5f5f5;
}

.dialog-body {
  padding: 20px;
}

.message {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  white-space: pre-line;
}

.dialog-footer {
  padding: 16px 20px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel,
.btn-confirm {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  border: 1px solid #ddd;
  background: white;
  color: #666;
}

.btn-cancel:hover {
  background: #f5f5f5;
}

.btn-confirm {
  border: none;
  background: #f44336;
  color: white;
}

.btn-confirm:hover {
  background: #d32f2f;
}
</style>
