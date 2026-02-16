<template>
  <div class="agent-editor-modal" @click.self="close">
    <div class="modal-content">
      <div class="modal-header">
        <h3>🤖 编辑 Agent 定义</h3>
        <button class="btn-close" @click="close">✕</button>
      </div>
      
      <div class="modal-body">
        <div class="editor-toolbar">
          <span class="file-label">SOUL.md</span>
          <span class="auto-save-hint">自动保存并热加载</span>
        </div>
        
        <textarea
          v-model="content"
          class="markdown-editor"
          placeholder="在此编写 Agent 的核心定义..."
          @input="onContentChange"
        ></textarea>
        
        <div class="editor-footer">
          <div class="stats">
            <span>{{ lineCount }} 行</span>
            <span>{{ charCount }} 字符</span>
          </div>
        </div>
      </div>
      
      <div class="modal-actions">
        <button class="btn-secondary" @click="close">关闭</button>
        <button class="btn-primary" @click="save">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const props = defineProps<{
  initialContent?: string
}>()

const emit = defineEmits<{
  close: []
  save: [content: string]
}>()

const content = ref(props.initialContent || '')
const isDirty = ref(false)

const lineCount = computed(() => content.value.split('\n').length)
const charCount = computed(() => content.value.length)

function onContentChange() {
  isDirty.value = true
}

function save() {
  emit('save', content.value)
  isDirty.value = false
}

function close() {
  if (isDirty.value) {
    const confirmed = confirm('有未保存的更改，确定要关闭吗？')
    if (!confirmed) return
  }
  emit('close')
}

onMounted(() => {
  // initialContent 由父组件通过 props 传入，已经从 API 加载
  // 这里不需要再次加载，直接使用 props.initialContent
})
</script>

<style scoped>
.agent-editor-modal {
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

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h3 {
  margin: 0;
  color: #2c3e50;
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

.modal-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.8rem 1.5rem;
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.file-label {
  font-weight: 600;
  color: #2c3e50;
}

.auto-save-hint {
  font-size: 0.85rem;
  color: #9e9e9e;
}

.markdown-editor {
  flex: 1;
  padding: 1.5rem;
  border: none;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.95rem;
  line-height: 1.6;
  resize: none;
  outline: none;
}

.editor-footer {
  padding: 0.8rem 1.5rem;
  background: #f5f5f5;
  border-top: 1px solid #e0e0e0;
}

.stats {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: #616161;
}

.modal-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e0e0e0;
}

.btn-primary,
.btn-secondary {
  padding: 0.6rem 1.5rem;
  border-radius: 4px;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: #1976d2;
  color: white;
  border: none;
}

.btn-primary:hover {
  background: #1565c0;
}

.btn-secondary {
  background: white;
  color: #616161;
  border: 1px solid #e0e0e0;
}

.btn-secondary:hover {
  background: #f5f5f5;
}
</style>
