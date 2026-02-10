<template>
  <div class="chat">
    <div class="chat-header">
      <h2>💬 对话界面</h2>
      <span :class="['connection-status', isConnected ? 'connected' : 'disconnected']">
        {{ isConnected ? '🟢 已连接' : '🔴 未连接' }}
      </span>
    </div>
    
    <div class="chat-main">
      <div class="chat-container">
        <!-- 消息列表 -->
        <div class="messages-area" ref="messagesArea">
          <div v-if="messages.length === 0" class="empty-messages">
            <p>开始与 Agent 对话吧！</p>
          </div>
          <div
            v-for="message in messages"
            :key="message.id"
            :class="['message-item', message.role]"
          >
            <div class="message-header">
              <span class="role-badge">{{ roleText(message.role) }}</span>
              <span class="timestamp">{{ formatTime(message.timestamp) }}</span>
            </div>

            <!-- 用户消息：纯文本 -->
            <div v-if="message.role === 'user'" class="message-content">{{ message.content }}</div>

            <!-- 助手/系统消息：Markdown 渲染 + 内联活动 -->
            <div v-else class="message-body">
              <!-- 内联活动区域（工具调用卡片等） -->
              <div v-if="message.activities && message.activities.length > 0" class="activities-area">
                <template v-for="act in message.activities" :key="act.id">
                  <!-- 工具调用卡片 -->
                  <div v-if="act.type === 'tool_start'" class="activity-card tool-card">
                    <div class="activity-icon">🔧</div>
                    <div class="activity-info">
                      <span class="activity-label">调用工具</span>
                      <span class="activity-name">{{ act.toolName }}</span>
                      <span v-if="getToolEndInfo(message, act.toolName)" class="activity-duration">
                        {{ getToolEndInfo(message, act.toolName)!.durationMs }}ms
                      </span>
                      <span v-else class="activity-running">执行中...</span>
                    </div>
                  </div>
                  <!-- LLM 思考中 -->
                  <div v-if="act.type === 'llm_start'" class="activity-card llm-card">
                    <div class="activity-icon">🧠</div>
                    <div class="activity-info">
                      <span class="activity-label">思考中</span>
                      <span class="activity-name">{{ act.model }} #{{ act.iteration }}</span>
                      <span v-if="getLLMEndInfo(message, act.iteration)" class="activity-duration">
                        {{ getLLMEndInfo(message, act.iteration)!.durationMs }}ms
                        · {{ getLLMEndInfo(message, act.iteration)!.tokens }} tokens
                      </span>
                      <span v-else class="activity-running">思考中...</span>
                    </div>
                  </div>
                </template>
              </div>

              <!-- Markdown 渲染的文本内容 -->
              <div
                v-if="message.content"
                class="message-content markdown-body"
                v-html="renderMd(message.content)"
              ></div>
            </div>

            <div v-if="message.toolCall" class="tool-call">
              <strong>🔧 调用工具:</strong> {{ message.toolCall.name }}
            </div>
          </div>

          <!-- 发送中的"正在思考"指示器 -->
          <div v-if="isSending && !currentHasContent" class="thinking-indicator">
            <span class="dot-animate">●</span>
            <span class="dot-animate delay-1">●</span>
            <span class="dot-animate delay-2">●</span>
            <span class="thinking-text">Agent 正在思考...</span>
          </div>
        </div>
        
        <!-- 输入框 -->
        <div class="input-area">
          <div class="input-controls">
            <select v-model="selectedModel" class="model-selector">
              <option v-for="model in availableModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <button class="btn-new" @click="startNewSession" title="新建会话">🧹 新建会话</button>
            <button class="btn-clear" @click="clearHistory" title="清空对话">🗑️</button>
          </div>
          <div class="input-row">
            <textarea
              v-model="inputMessage"
              placeholder="输入消息..."
              @keydown.enter.prevent="sendMessage"
              rows="3"
            ></textarea>
            <button
              class="btn-send"
              :disabled="!inputMessage.trim() || isSending"
              @click="sendMessage"
            >
              {{ isSending ? '发送中...' : '发送' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧监控面板 -->
      <TracePanel ref="tracePanelRef" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch, computed } from 'vue'
import type { ChatMessage, ToolActivity, LLMActivity } from '@/types/message'
import TracePanel from '@/components/TracePanel.vue'
import { renderMarkdown } from '@/utils/markdown'

// localStorage keys
const CHAT_SESSION_KEY = 'nanobot_chat_session_id'
const CHAT_STORAGE_PREFIX = 'nanobot_chat_messages_'

const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const messagesArea = ref<HTMLElement>()
const selectedModel = ref('claude-sonnet-4')
const isSending = ref(false)
const isConnected = ref(false)
const availableModels = ref<string[]>(['claude-sonnet-4', 'gpt-4o', 'gpt-5-mini'])
const sessionId = ref('')
const tracePanelRef = ref<InstanceType<typeof TracePanel>>()

let ws: WebSocket | null = null
let currentAssistantMessageId: string | null = null

/** 当前助手消息是否有内容 */
const currentHasContent = computed(() => {
  if (!currentAssistantMessageId) return false
  const msg = messages.value.find(m => m.id === currentAssistantMessageId)
  return msg ? msg.content.length > 0 : false
})

/** 渲染 Markdown（缓存友好） */
function renderMd(text: string): string {
  return renderMarkdown(text)
}

/** 获取工具结束信息 */
function getToolEndInfo(message: ChatMessage, toolName: string): { durationMs: number } | null {
  if (!message.activities) return null
  const end = message.activities.find(
    a => a.type === 'tool_end' && (a as ToolActivity).toolName === toolName
  ) as ToolActivity | undefined
  return end?.durationMs != null ? { durationMs: end.durationMs } : null
}

/** 获取 LLM 结束信息 */
function getLLMEndInfo(message: ChatMessage, iteration: number): { durationMs: number; tokens: number } | null {
  if (!message.activities) return null
  const end = message.activities.find(
    a => a.type === 'llm_end' && (a as LLMActivity).iteration === iteration
  ) as LLMActivity | undefined
  return end?.durationMs != null ? { durationMs: end.durationMs, tokens: end.tokens || 0 } : null
}

// 连接 WebSocket
function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return
  
  ws = new WebSocket('ws://localhost:8000/ws/chat')
  
  ws.onopen = () => {
    isConnected.value = true
    console.log('Chat WebSocket connected')
  }
  
  ws.onclose = () => {
    isConnected.value = false
    console.log('Chat WebSocket disconnected')
    // 3秒后自动重连
    setTimeout(connectWebSocket, 3000)
  }
  
  ws.onerror = (error) => {
    console.error('Chat WebSocket error:', error)
  }
  
  ws.onmessage = async (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'trace') {
      // 转发到监控面板
      if (tracePanelRef.value) {
        const { type, ...traceData } = data
        tracePanelRef.value.handleTraceEvent(traceData)
      }
    } else if (data.type === 'activity') {
      // 内联活动事件 → 附加到当前助手消息
      if (currentAssistantMessageId) {
        const msg = messages.value.find(m => m.id === currentAssistantMessageId)
        if (msg) {
          if (!msg.activities) msg.activities = []
          const actType = data.activity_type as string
          if (actType === 'tool_start' || actType === 'tool_end') {
            msg.activities.push({
              id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              type: actType,
              toolName: data.tool_name || '',
              toolArgs: data.tool_args,
              durationMs: data.duration_ms,
              resultLength: data.result_length,
              timestamp: data.timestamp || Date.now() / 1000,
            } as ToolActivity)
          } else if (actType === 'llm_start' || actType === 'llm_end') {
            msg.activities.push({
              id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              type: actType,
              iteration: data.iteration || 0,
              model: data.model,
              durationMs: data.duration_ms,
              tokens: data.total_tokens,
              timestamp: data.timestamp || Date.now() / 1000,
            } as LLMActivity)
          }
        }
      }
      scrollToBottom()
    } else if (data.type === 'chunk') {
      // 流式输出片段
      if (currentAssistantMessageId) {
        const msg = messages.value.find(m => m.id === currentAssistantMessageId)
        if (msg) {
          msg.content += data.content
        }
      }
      scrollToBottom()
    } else if (data.type === 'done') {
      // 响应完成
      isSending.value = false
      currentAssistantMessageId = null
      scrollToBottom()
    } else if (data.type === 'error') {
      // 错误
      isSending.value = false
      currentAssistantMessageId = null
      const errorMessage: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ ${data.content}`,
        timestamp: new Date().toISOString()
      }
      messages.value.push(errorMessage)
      scrollToBottom()
    } else if (data.type === 'system') {
      // 系统消息
      messages.value = []
      console.log(data.content)
    }
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesArea.value) {
    messagesArea.value.scrollTop = messagesArea.value.scrollHeight
  }
}

function generateSessionId() {
  return `session-${Date.now()}`
}

function getStorageKey() {
  return `${CHAT_STORAGE_PREFIX}${sessionId.value}`
}

// 加载可用模型列表
async function loadModels() {
  try {
    const response = await fetch('http://localhost:8000/api/auth/models')
    if (response.ok) {
      const data = await response.json()
      availableModels.value = data.models
      console.log('Available models:', data.models)
    }
  } catch (error) {
    console.error('Failed to load models:', error)
  }
}

// 保存消息到 localStorage
function saveMessages() {
  try {
    localStorage.setItem(getStorageKey(), JSON.stringify(messages.value))
  } catch (e) {
    console.error('Failed to save messages:', e)
  }
}

// 加载保存的消息
function loadMessages() {
  try {
    const saved = localStorage.getItem(getStorageKey())
    if (saved) {
      messages.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('Failed to load messages:', e)
  }
}

// 监听消息变化保存到 localStorage
watch(messages, () => {
  saveMessages()
}, { deep: true })

onMounted(() => {
  const savedSessionId = localStorage.getItem(CHAT_SESSION_KEY)
  if (savedSessionId) {
    sessionId.value = savedSessionId
  } else {
    sessionId.value = generateSessionId()
    localStorage.setItem(CHAT_SESSION_KEY, sessionId.value)
  }
  loadMessages()  // 先加载保存的消息
  loadModels()
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
    ws = null
  }
})

function roleText(role: string): string {
  const roleMap: Record<string, string> = {
    user: '用户',
    assistant: 'Agent',
    system: '系统',
    tool: '工具'
  }
  return roleMap[role] || role
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN')
}

function clearHistory() {
  if (!confirm('确定要清空对话历史吗？')) return
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'clear', session_id: sessionId.value }))
  }
  messages.value = []
  localStorage.removeItem(getStorageKey())
}

function startNewSession() {
  if (!confirm('新建会话将清空当前聊天记录，是否继续？')) return
  const oldStorageKey = getStorageKey()
  const oldSessionId = sessionId.value
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'clear', session_id: oldSessionId }))
  }
  messages.value = []
  currentAssistantMessageId = null
  
  sessionId.value = generateSessionId()
  localStorage.setItem(CHAT_SESSION_KEY, sessionId.value)
  localStorage.removeItem(oldStorageKey)
}

function sendMessage() {
  if (!inputMessage.value.trim() || isSending.value) return
  
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    alert('WebSocket 未连接，请稍后重试')
    return
  }
  
  const userMessage: ChatMessage = {
    id: `msg-${Date.now()}`,
    role: 'user',
    content: inputMessage.value,
    timestamp: new Date().toISOString()
  }
  
  messages.value.push(userMessage)
  
  // 创建空的助手消息（流式填充）
  const assistantMessage: ChatMessage = {
    id: `msg-${Date.now() + 1}`,
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    activities: [],
  }
  messages.value.push(assistantMessage)
  currentAssistantMessageId = assistantMessage.id
  
  // 通过 WebSocket 发送
  ws.send(JSON.stringify({
    type: 'message',
    content: inputMessage.value,
    model: selectedModel.value,
    session_id: sessionId.value
  }))
  
  inputMessage.value = ''
  isSending.value = true
  scrollToBottom()
}
</script>

<style scoped>
.chat {
  padding: 1rem 2rem;
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

h2 {
  margin-bottom: 1rem;
  color: #2c3e50;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
}

.chat-header h2 {
  margin-bottom: 0;
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

.chat-main {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 0;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  overflow: hidden;
  min-width: 0;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.empty-messages {
  text-align: center;
  color: #9e9e9e;
  padding: 3rem;
}

.message-item {
  margin-bottom: 1.5rem;
  padding: 1rem;
  border-radius: 8px;
  max-width: 85%;
}

.message-item.user {
  background: #e3f2fd;
  margin-left: auto;
}

.message-item.assistant {
  background: #f5f5f5;
  margin-right: auto;
}

.message-item.system {
  background: #fff3e0;
  margin: 0 auto;
  text-align: center;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.role-badge {
  font-weight: 600;
  color: #2c3e50;
}

.timestamp {
  font-size: 0.8rem;
  color: #9e9e9e;
}

.message-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.message-content {
  color: #2c3e50;
  word-break: break-word;
}

/* 用户消息保持 pre-wrap */
.message-item.user .message-content {
  white-space: pre-wrap;
}

/* ── 活动卡片区域 ─────────────────────── */
.activities-area {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.activity-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.7rem;
  border-radius: 6px;
  font-size: 0.82rem;
  border-left: 3px solid;
  animation: slideIn 0.2s ease-out;
}

.tool-card {
  background: rgba(255, 152, 0, 0.08);
  border-left-color: #ff9800;
}

.llm-card {
  background: rgba(33, 150, 243, 0.08);
  border-left-color: #2196f3;
}

.activity-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.activity-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.activity-label {
  color: #757575;
  font-size: 0.78rem;
}

.activity-name {
  font-weight: 500;
  color: #2c3e50;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 0.82rem;
}

.activity-duration {
  color: #4caf50;
  font-size: 0.78rem;
  font-family: monospace;
}

.activity-running {
  color: #ff9800;
  font-size: 0.78rem;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ── 思考中指示器 ──────────────────────── */
.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.8rem 1rem;
  color: #757575;
  font-size: 0.9rem;
}

.dot-animate {
  animation: dotBounce 1.4s ease-in-out infinite;
  font-size: 0.6rem;
}

.dot-animate.delay-1 { animation-delay: 0.2s; }
.dot-animate.delay-2 { animation-delay: 0.4s; }

@keyframes dotBounce {
  0%, 80%, 100% { opacity: 0.3; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-4px); }
}

.thinking-text {
  margin-left: 0.4rem;
  font-style: italic;
}

/* ── Markdown 渲染样式 ──────────────────── */
.markdown-body :deep(h1) { font-size: 1.4rem; margin: 0.8rem 0 0.4rem; border-bottom: 1px solid #e0e0e0; padding-bottom: 0.3rem; }
.markdown-body :deep(h2) { font-size: 1.2rem; margin: 0.7rem 0 0.3rem; border-bottom: 1px solid #eee; padding-bottom: 0.2rem; }
.markdown-body :deep(h3) { font-size: 1.1rem; margin: 0.6rem 0 0.3rem; }
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) { font-size: 1rem; margin: 0.5rem 0 0.2rem; }

.markdown-body :deep(p) { margin: 0.4rem 0; line-height: 1.6; }
.markdown-body :deep(ul),
.markdown-body :deep(ol) { margin: 0.4rem 0; padding-left: 1.5rem; }
.markdown-body :deep(li) { margin: 0.2rem 0; line-height: 1.5; }

.markdown-body :deep(blockquote) {
  margin: 0.5rem 0;
  padding: 0.5rem 1rem;
  border-left: 4px solid #1976d2;
  background: rgba(25, 118, 210, 0.05);
  color: #37474f;
}

.markdown-body :deep(hr) { border: none; border-top: 1px solid #e0e0e0; margin: 0.8rem 0; }

.markdown-body :deep(a) { color: #1976d2; text-decoration: none; }
.markdown-body :deep(a:hover) { text-decoration: underline; }

.markdown-body :deep(strong) { font-weight: 600; }
.markdown-body :deep(em) { font-style: italic; }
.markdown-body :deep(del) { text-decoration: line-through; color: #9e9e9e; }

/* 内联代码 */
.markdown-body :deep(code:not(.hljs)) {
  background: rgba(27, 31, 35, 0.06);
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 0.88em;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  color: #d63384;
}

/* 代码块容器 */
.markdown-body :deep(.code-block) {
  margin: 0.6rem 0;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e0e0e0;
}

.markdown-body :deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.3rem 0.8rem;
  background: #f0f0f0;
  font-size: 0.78rem;
  color: #757575;
}

.markdown-body :deep(.code-lang) {
  text-transform: uppercase;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.markdown-body :deep(.copy-btn) {
  background: transparent;
  border: 1px solid #ccc;
  border-radius: 3px;
  padding: 0.15rem 0.5rem;
  font-size: 0.72rem;
  cursor: pointer;
  color: #757575;
  transition: all 0.2s;
}

.markdown-body :deep(.copy-btn:hover) {
  background: #e0e0e0;
  color: #333;
}

.markdown-body :deep(pre) {
  margin: 0;
  padding: 0.8rem 1rem;
  background: #1e1e1e;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  color: #d4d4d4;
}

/* 表格 */
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.6rem 0;
  font-size: 0.9rem;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e0e0e0;
  padding: 0.4rem 0.8rem;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.markdown-body :deep(tr:nth-child(even)) {
  background: #fafafa;
}

/* 图片 */
.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 4px;
  margin: 0.4rem 0;
}

.tool-call {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(255, 152, 0, 0.1);
  border-left: 3px solid #ff9800;
  font-size: 0.9rem;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  padding: 1rem;
  border-top: 1px solid #e0e0e0;
  background: #fafafa;
}

.input-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.model-selector {
  padding: 0.5rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
  font-size: 0.9rem;
  cursor: pointer;
}

.model-selector:focus {
  outline: none;
  border-color: #1976d2;
}

.btn-clear {
  padding: 0.5rem 0.8rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-clear:hover {
  background: #f5f5f5;
  border-color: #ff5722;
}

.btn-new {
  padding: 0.5rem 0.8rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-new:hover {
  background: #f5f5f5;
  border-color: #1976d2;
}

.input-row {
  display: flex;
  gap: 1rem;
}

textarea {
  flex: 1;
  padding: 0.8rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-family: inherit;
  font-size: 1rem;
  resize: none;
}

textarea:focus {
  outline: none;
  border-color: #1976d2;
}

.btn-send {
  background: #1976d2;
  color: white;
  border: none;
  padding: 0.8rem 2rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-send:hover:not(:disabled) {
  background: #1565c0;
}

.btn-send:disabled {
  background: #bdbdbd;
  cursor: not-allowed;
}
</style>
