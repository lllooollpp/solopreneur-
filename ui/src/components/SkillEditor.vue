<template>
  <div class="skill-editor-modal" @click.self="close">
    <div class="modal-content">
      <div class="modal-header">
        <h3>{{ isCreate ? '✨ 新建技能' : `📝 编辑技能 — ${skillName}` }}</h3>
        <button class="btn-close" @click="close">✕</button>
      </div>

      <div class="modal-body">
        <!-- 新建模式：名称和描述 -->
        <div v-if="isCreate" class="form-fields">
          <div class="form-group">
            <label>技能名称 <span class="required">*</span></label>
            <input
              v-model="name"
              type="text"
              placeholder="my-skill（只允许字母、数字、连字符、下划线）"
              class="input"
              :class="{ 'input-error': nameError }"
              @input="validateName"
            />
            <p v-if="nameError" class="field-error">{{ nameError }}</p>
          </div>
          <div class="form-group">
            <label>描述 <span class="required">*</span></label>
            <input
              v-model="description"
              type="text"
              placeholder="简要描述这个技能的作用"
              class="input"
            />
          </div>
        </div>

        <!-- 编辑器 -->
        <div class="editor-toolbar">
          <span class="file-label">SKILL.md</span>
          <button class="btn-preview" @click="togglePreview">
            {{ showPreview ? '编辑' : '预览' }}
          </button>
        </div>

        <div class="editor-container">
          <codemirror
            v-if="!showPreview"
            v-model="content"
            :extensions="extensions"
            :style="{ height: '400px', fontSize: '14px' }"
            @update="onContentChange"
          />
          <div v-else class="markdown-preview" v-html="renderedMarkdown"></div>
        </div>

        <div class="editor-footer">
          <div class="stats">
            <span>{{ lineCount }} 行</span>
            <span>{{ charCount }} 字符</span>
            <span v-if="isDirty" class="dirty-indicator">● 已修改</span>
          </div>
        </div>
      </div>

      <div class="modal-actions">
        <button class="btn-secondary" @click="close">取消</button>
        <button class="btn-primary" @click="save" :disabled="saving || !canSave">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>

      <div v-if="error" class="error-toast">
        ⚠️ {{ error }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'

const props = defineProps<{
  isCreate: boolean
  skillName?: string
  initialContent?: string
}>()

const emit = defineEmits<{
  close: []
  save: [payload: { name: string; description: string; content: string }]
}>()

const name = ref('')
const description = ref('')
const content = ref(props.initialContent || (props.isCreate ? '# 技能说明\n\n在此编写技能的详细说明...\n' : ''))
const isDirty = ref(false)
const saving = ref(false)
const showPreview = ref(false)
const error = ref('')
const nameError = ref('')

const extensions = [
  markdown(),
  EditorView.lineWrapping,
  EditorView.theme({
    '&': {
      fontSize: '14px',
      fontFamily: 'Monaco, Menlo, Consolas, monospace'
    }
  })
]

const lineCount = computed(() => content.value.split('\n').length)
const charCount = computed(() => content.value.length)

const canSave = computed(() => {
  if (props.isCreate) {
    return name.value.trim() && description.value.trim() && content.value.trim() && !nameError.value
  }
  return content.value.trim()
})

const renderedMarkdown = computed(() => {
  return content.value
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^- (.+$)/gim, '<li>$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
})

watch(() => props.initialContent, (newVal) => {
  if (newVal !== undefined) {
    content.value = newVal
    isDirty.value = false
  }
})

function validateName() {
  if (!name.value) {
    nameError.value = ''
    return
  }
  if (!/^[a-zA-Z0-9\-_]+$/.test(name.value)) {
    nameError.value = '只允许字母、数字、连字符和下划线'
  } else {
    nameError.value = ''
  }
}

function onContentChange() {
  isDirty.value = true
  error.value = ''
}

function togglePreview() {
  showPreview.value = !showPreview.value
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = ''

  try {
    emit('save', {
      name: props.isCreate ? name.value.trim() : (props.skillName || ''),
      description: description.value.trim(),
      content: content.value,
    })
    setTimeout(() => {
      saving.value = false
      isDirty.value = false
    }, 500)
  } catch (e: any) {
    error.value = e.message || '保存失败'
    saving.value = false
  }
}

function close() {
  if (isDirty.value) {
    const confirmed = confirm('有未保存的更改，确定要关闭吗？')
    if (!confirmed) return
  }
  emit('close')
}
</script>

<style scoped>
.skill-editor-modal {
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
  max-width: 1000px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
  position: relative;
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

.form-fields {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.form-group label {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.9rem;
}

.required {
  color: #f44336;
}

.input {
  padding: 0.6rem 0.8rem;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 0.95rem;
  transition: border-color 0.2s;
}

.input:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.1);
}

.input-error {
  border-color: #f44336 !important;
}

.field-error {
  color: #f44336;
  font-size: 0.8rem;
  margin: 0;
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

.btn-preview {
  padding: 0.4rem 1rem;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-preview:hover {
  background: #f5f5f5;
  border-color: #1976d2;
  color: #1976d2;
}

.editor-container {
  flex: 1;
  overflow: auto;
}

.markdown-preview {
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.8;
  color: #2c3e50;
  max-width: 800px;
  margin: 0 auto;
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

.dirty-indicator {
  color: #f39c12;
  font-weight: 600;
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

.btn-primary:hover:not(:disabled) {
  background: #1565c0;
}

.btn-primary:disabled {
  background: #90caf9;
  cursor: not-allowed;
}

.btn-secondary {
  background: white;
  color: #616161;
  border: 1px solid #e0e0e0;
}

.btn-secondary:hover {
  background: #f5f5f5;
}

.error-toast {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: #f44336;
  color: white;
  padding: 1rem 1.5rem;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
