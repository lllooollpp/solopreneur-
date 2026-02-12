<template>
  <div class="chat-layout">
    <!-- 左侧项目列表 -->
    <ProjectSidebar
      ref="projectSidebarRef"
      :current-project-id="currentProject?.id"
      @select="handleProjectSelect"
    />
    
    <!-- 中间主区域 -->
    <div class="chat-main-area">
      <!-- 顶部 Header -->
      <div class="chat-header">
        <div class="header-left">
          <h2>{{ currentProject?.name || '未选择项目' }}</h2>
          <span v-if="currentProject?.description" class="project-desc">
            {{ currentProject.description }}
          </span>
        </div>
        <div class="header-right">
          <span v-if="currentProvider" class="provider-badge">
            {{ currentProvider }}
          </span>
          <span :class="['connection-status', isConnected ? 'connected' : 'disconnected']">
            {{ isConnected ? '🟢 已连接' : '🔴 未连接' }}
          </span>
        </div>
      </div>
      
      <!-- Tab 切换栏 -->
      <div class="tab-bar" v-if="currentProject">
        <button 
          :class="['tab-btn', { active: activeTab === 'chat' }]"
          @click="activeTab = 'chat'"
        >
          💬 对话
        </button>
        <button 
          :class="['tab-btn', { active: activeTab === 'wiki' }]"
          @click="activeTab = 'wiki'"
        >
          📚 Wiki
        </button>
      </div>
      
      <!-- 内容区域 -->
      <div class="content-area">
        <!-- ===== 对话 Tab ===== -->
        <div v-show="activeTab === 'chat'" class="chat-container">
          <div class="messages-area" ref="messagesArea">
            <div v-if="messages.length === 0" class="empty-messages">
              <p v-if="currentProject">
                与项目 <strong>{{ currentProject.name }}</strong> 开始对话<br>
                <small>项目路径: {{ currentProject.path }}</small>
              </p>
              <p v-else>请从左侧选择一个项目开始对话</p>
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

              <!-- 助手/系统消息 -->
              <div v-else class="message-body">
                <div v-if="message.activities && message.activities.length > 0" class="activities-area">
                  <template v-for="act in message.activities" :key="act.id">
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
              <select v-model="selectedModel" class="model-selector" :disabled="lockedModel">
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
                :placeholder="currentProject ? '输入消息...' : '请先从左侧选择项目'"
                :disabled="!currentProject"
                @keydown.enter.prevent="sendMessage"
                rows="3"
              ></textarea>
              <button
                class="btn-send"
                :disabled="!inputMessage.trim() || isSending || !currentProject"
                @click="sendMessage"
              >
                {{ isSending ? '发送中...' : '发送' }}
              </button>
            </div>
          </div>
        </div>

        <!-- ===== Wiki Tab ===== -->
        <div v-show="activeTab === 'wiki'" class="wiki-container">
          <div v-if="!currentProject" class="wiki-empty">
            <div class="empty-state">
              <div class="empty-icon">📁</div>
              <h3>选择项目查看 Wiki</h3>
              <p>请从左侧列表选择一个项目</p>
            </div>
          </div>
          
          <div v-else class="wiki-layout-inner">
            <!-- Wiki 左侧目录 -->
            <div class="wiki-sidebar">
              <div class="wiki-sidebar-header">
                <h4>📑 文档目录</h4>
                <button class="btn-refresh" @click="loadWikiDocs" title="刷新">🔄</button>
              </div>
              <div class="wiki-doc-list">
                <div v-if="wikiDocs.length === 0" class="wiki-empty-tip">
                  暂无 Wiki 文档
                </div>
                <div
                  v-for="doc in wikiDocs"
                  :key="doc.path"
                  :class="['wiki-doc-item', { active: currentWikiDoc?.path === doc.path }]"
                  @click="selectWikiDoc(doc)"
                >
                  <span class="doc-icon">{{ getDocIcon(doc.name) }}</span>
                  <span class="doc-name">{{ formatDocName(doc.name) }}</span>
                </div>
              </div>
              <div class="wiki-actions">
                <button class="btn-generate" @click="showGenerateWikiDialog = true">
                  📝 生成 Wiki
                </button>
              </div>
            </div>
            
            <!-- Wiki 右侧内容 -->
            <div class="wiki-content">
              <div v-if="!currentWikiDoc" class="wiki-empty-content">
                <div class="empty-state">
                  <div class="empty-icon">📚</div>
                  <h3>{{ currentProject?.name }} Wiki</h3>
                  <p v-if="wikiDocs.length === 0">
                    该项目还没有 Wiki 文档<br>
                    点击"生成 Wiki"创建完整文档
                  </p>
                  <p v-else>请从左侧选择要查看的文档</p>
                  <button v-if="wikiDocs.length === 0" class="btn-generate-large" @click="showGenerateWikiDialog = true">
                    📝 生成 Wiki 文档
                  </button>
                </div>
              </div>
              
              <div v-else class="wiki-doc-viewer">
                <div class="wiki-doc-header">
                  <h2>{{ formatDocName(currentWikiDoc.name) }}</h2>
                  <div class="doc-actions">
                    <button class="btn-action" @click="refreshWikiDoc" title="刷新">🔄</button>
                    <button class="btn-action" @click="editWikiDoc" title="编辑">✏️</button>
                  </div>
                </div>
                <div class="wiki-doc-body markdown-body" v-html="renderedWikiContent"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 右侧监控面板 -->
    <TracePanel ref="tracePanelRef" />
    
    <!-- 生成 Wiki 对话框 -->
    <div v-if="showGenerateWikiDialog" class="dialog-overlay" @click="showGenerateWikiDialog = false">
      <div class="dialog" @click.stop>
        <div class="dialog-header">
          <h3>📝 生成 Wiki 文档</h3>
          <button class="btn-close" @click="showGenerateWikiDialog = false">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-group">
            <label>目标项目</label>
            <div class="project-display">{{ currentProject?.name }}</div>
          </div>
          <div class="form-group">
            <label>文档范围</label>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="wikiGenOptions.readme" />
                <span>📄 项目概述 (README)</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="wikiGenOptions.installation" />
                <span>⚙️ 安装指南</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="wikiGenOptions.architecture" />
                <span>🏗️ 架构设计</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="wikiGenOptions.api" />
                <span>🔌 API 文档</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="wikiGenOptions.deployment" />
                <span>📦 部署指南</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="wikiGenOptions.contributing" />
                <span>🤝 贡献指南</span>
              </label>
            </div>
          </div>
          <div class="form-group">
            <label>生成模型</label>
            <select v-model="wikiGenOptions.model" class="model-selector-dialog" :disabled="lockedModel">
              <option v-for="model in availableModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <span class="hint">选择用于生成 Wiki 的 AI 模型</span>
          </div>
          <div class="form-group">
            <label>额外要求（可选）</label>
            <textarea
              v-model="wikiGenOptions.requirements"
              placeholder="描述你对 Wiki 的特殊要求，如文档风格、技术栈细节等..."
              rows="3"
            ></textarea>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn-cancel" @click="showGenerateWikiDialog = false">取消</button>
          <button class="btn-primary" :disabled="isGeneratingWiki" @click="generateWiki">
            {{ isGeneratingWiki ? '生成中...' : '开始生成' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch, computed } from 'vue'
import type { ChatMessage, ToolActivity, LLMActivity } from '@/types/message'
import type { Project } from '@/types/project'
import ProjectSidebar from '@/components/ProjectSidebar.vue'
import TracePanel from '@/components/TracePanel.vue'
import { renderMarkdown } from '@/utils/markdown'
import { generateWiki as generateWikiApi, getProjectDocs } from '@/services/projectApi'

// localStorage keys
const CHAT_STORAGE_PREFIX = 'nanobot_chat_messages_'
const CURRENT_PROJECT_KEY = 'nanobot_current_project'

// Refs
const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const messagesArea = ref<HTMLElement>()
const selectedModel = ref('gpt-5-mini')
const lockedModel = ref(false)
const isSending = ref(false)
const isConnected = ref(false)
const availableModels = ref<string[]>(['gpt-5-mini', 'gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4'])
const currentProvider = ref<string | null>(null)
const sessionId = ref('')
const projectSidebarRef = ref<InstanceType<typeof ProjectSidebar>>()
const tracePanelRef = ref<InstanceType<typeof TracePanel>>()
const currentProject = ref<Project | null>(null)

// Tab 切换
const activeTab = ref<'chat' | 'wiki'>('chat')

// Wiki 相关
const wikiDocs = ref<Array<{name: string, path: string, content: string}>>([])
const currentWikiDoc = ref<{name: string, path: string, content: string} | null>(null)
const showGenerateWikiDialog = ref(false)
const isGeneratingWiki = ref(false)
const wikiGenOptions = ref({
  readme: true,
  installation: true,
  architecture: true,
  api: true,
  deployment: true,
  contributing: false,
  requirements: '',
  model: 'gpt-5-mini'
})

const renderedWikiContent = computed(() => {
  if (!currentWikiDoc.value) return ''
  return renderMarkdown(currentWikiDoc.value.content)
})

let ws: WebSocket | null = null
let currentAssistantMessageId: string | null = null

/** 当前助手消息是否有内容 */
const currentHasContent = computed(() => {
  if (!currentAssistantMessageId) return false
  const msg = messages.value.find(m => m.id === currentAssistantMessageId)
  return msg ? msg.content.length > 0 : false
})

/** 渲染 Markdown */
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

/** 获取 localStorage key */
function getStorageKey(): string {
  const projectId = currentProject.value?.id || 'default'
  return `${CHAT_STORAGE_PREFIX}${projectId}_${sessionId.value}`
}

/** 获取项目级别的 session key */
function getProjectSessionKey(projectId: string): string {
  return `${CHAT_STORAGE_PREFIX}${projectId}_current_session`
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
    setTimeout(connectWebSocket, 3000)
  }
  
  ws.onerror = (error) => {
    console.error('Chat WebSocket error:', error)
  }
  
  ws.onmessage = async (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'chunk') {
      if (currentAssistantMessageId) {
        const msg = messages.value.find(m => m.id === currentAssistantMessageId)
        if (msg) {
          msg.content += data.content
        }
      }
      scrollToBottom()
    } else if (data.type === 'done') {
      isSending.value = false
      currentAssistantMessageId = null
      scrollToBottom()
    } else if (data.type === 'error') {
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
      messages.value = []
    } else if (data.type === 'activity') {
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

// 加载可用模型列表
async function loadModels() {
  // 优先从 localStorage 读取 Provider 配置
  try {
    const providerConfigStr = localStorage.getItem('provider_config')
    if (providerConfigStr) {
      const providerConfig = JSON.parse(providerConfigStr)

      // 检查是否有配置的 Provider
      if (providerConfig && providerConfig.providers) {
        const providers = providerConfig.providers

        // 获取当前使用的 Provider
        let activeProvider = null
        let activeModel = providerConfig.agents?.defaults?.model || ''

        // 检查 Copilot 优先级
        if (providers.copilot_priority) {
          activeProvider = 'copilot'
          // Copilot 的模型列表（固定）
          availableModels.value = ['gpt-5-mini', 'gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4']
          selectedModel.value = activeModel || 'gpt-5-mini'
        }
        // 检查 vLLM (本地)
        else if (providers.vllm && providers.vllm.api_base) {
          activeProvider = 'vllm'
          // 从配置读取的本地模型（用户在配置管理中设置的）
          const vllmModel = activeModel || 'llama-3-8b'
          availableModels.value = [vllmModel]
          selectedModel.value = vllmModel
          // 锁定模型，不允许用户修改
          lockedModel.value = true
        }
        // 检查火山引擎
        else if (providers.zhipu && providers.zhipu.api_key) {
          activeProvider = 'zhipu'
          availableModels.value = ['glm-4', 'glm-4-plus', 'glm-3-turbo', 'glm-4-flash']
          selectedModel.value = activeModel || 'glm-4'
        }
        // 检查 OpenRouter
        else if (providers.openrouter && providers.openrouter.api_key) {
          activeProvider = 'openrouter'
          availableModels.value = ['anthropic/claude-3.5-sonnet', 'openai/gpt-4o', 'google/gemini-pro-1.5', 'meta-llama/llama-3.1-70b-instruct']
          selectedModel.value = activeModel || 'anthropic/claude-3.5-sonnet'
        }
        // 检查 Anthropic
        else if (providers.anthropic && providers.anthropic.api_key) {
          activeProvider = 'anthropic'
          availableModels.value = ['claude-3-5-sonnet', 'claude-3-5-haiku', 'claude-3-opus']
          selectedModel.value = activeModel || 'claude-3-5-sonnet'
        }
        // 检查 OpenAI
        else if (providers.openai && providers.openai.api_key) {
          activeProvider = 'openai'
          availableModels.value = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']
          selectedModel.value = activeModel || 'gpt-4o'
        }
        // 检查 Groq
        else if (providers.groq && providers.groq.api_key) {
          activeProvider = 'groq'
          availableModels.value = ['llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768']
          selectedModel.value = activeModel || 'llama-3.1-70b-versatile'
        }
        // 检查 Gemini
        else if (providers.gemini && providers.gemini.api_key) {
          activeProvider = 'gemini'
          availableModels.value = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.0-pro']
          selectedModel.value = activeModel || 'gemini-1.5-pro'
        }

        // 设置 Provider 显示名称
        const providerNames: Record<string, string> = {
          'copilot': '🐙 Copilot',
          'vllm': '🏠 本地接口',
          'zhipu': '🌋 火山引擎',
          'openrouter': '🌐 OpenRouter',
          'anthropic': '🧠 Anthropic',
          'openai': '🤖 OpenAI',
          'groq': '⚡ Groq',
          'gemini': '💎 Gemini',
          'none': '❌ 未配置'
        }

        if (activeProvider) {
          currentProvider.value = providerNames[activeProvider] || activeProvider
          console.log('Loaded from localStorage:', {
            provider: activeProvider,
            models: availableModels.value,
            selected: selectedModel.value,
            locked: lockedModel.value
          })
          return
        }
      }
    }
  } catch (e) {
    console.debug('Failed to load provider config from localStorage:', e)
  }

  // 回退：如果 localStorage 没有配置，从后端加载
  try {
    const response = await fetch('http://localhost:8000/api/auth/models')
    if (response.ok) {
      const data = await response.json()
      availableModels.value = data.models

      const providerNames: Record<string, string> = {
        'copilot': '🐙 Copilot',
        'vllm': '🏠 本地接口',
        'zhipu': '🌋 火山引擎',
        'openrouter': '🌐 OpenRouter',
        'anthropic': '🧠 Anthropic',
        'openai': '🤖 OpenAI',
        'groq': '⚡ Groq',
        'gemini': '💎 Gemini',
        'none': '❌ 未配置'
      }
      currentProvider.value = providerNames[data.provider] || data.provider

      if (data.models.includes(selectedModel.value)) {
        // 保持当前选中的模型
      } else if (data.models.length > 0) {
        selectedModel.value = data.models[0]
      }

      console.log('Fallback to backend API:', {
        provider: data.provider,
        models: data.models,
        selected: selectedModel.value
      })
    }
  } catch (error) {
    console.error('Failed to load models from backend:', error)
  }
}

// 保存消息到 localStorage
function saveMessages() {
  try {
    if (!currentProject.value) return
    localStorage.setItem(getStorageKey(), JSON.stringify(messages.value))
  } catch (e) {
    console.error('Failed to save messages:', e)
  }
}

// 加载保存的消息
function loadMessages() {
  try {
    if (!currentProject.value) {
      messages.value = []
      return
    }
    const saved = localStorage.getItem(getStorageKey())
    if (saved) {
      messages.value = JSON.parse(saved)
    } else {
      messages.value = []
    }
  } catch (e) {
    console.error('Failed to load messages:', e)
    messages.value = []
  }
}

// 监听消息变化保存到 localStorage
watch(messages, () => {
  saveMessages()
}, { deep: true })

// 处理项目选择
function handleProjectSelect(project: Project) {
  // 保存当前项目的消息
  if (currentProject.value && messages.value.length > 0) {
    saveMessages()
  }
  
  // 切换到新项目
  currentProject.value = project
  localStorage.setItem(CURRENT_PROJECT_KEY, project.id)
  
  // 加载该项目的 session
  const savedSession = localStorage.getItem(getProjectSessionKey(project.id))
  if (savedSession) {
    sessionId.value = savedSession
  } else {
    sessionId.value = generateSessionId()
    localStorage.setItem(getProjectSessionKey(project.id), sessionId.value)
  }
  
  // 加载消息
  loadMessages()
  
  // 重置 Tab
  activeTab.value = 'chat'
  
  // 加载 Wiki 文档列表
  loadWikiDocs()
  
  console.log('Switched to project:', project.name, 'session:', sessionId.value)
}

// Wiki 相关函数
async function loadWikiDocs() {
  if (!currentProject.value) {
    wikiDocs.value = []
    return
  }
  
  // 尝试从后端获取项目下的 docs 列表（如果后端尚未提供，则保持空）
  try {
    const json = await getProjectDocs(currentProject.value.id)
    // 期望格式：{ files: [{ name, path, content? }] }
    wikiDocs.value = (json.files || []).map((f: any) => ({ name: f.name, path: f.path, content: f.content || '' }))
    currentWikiDoc.value = wikiDocs.value.length > 0 ? wikiDocs.value[0] : null
    return
  } catch (e) {
    // 如果后端不存在该接口，保持兼容性并继续使用空列表
    console.debug('loadWikiDocs: docs API not available or failed', e)
  }

  wikiDocs.value = []
  currentWikiDoc.value = null
}

function selectWikiDoc(doc: {name: string, path: string, content: string}) {
  currentWikiDoc.value = doc
}

function getDocIcon(name: string): string {
  if (name.includes('README') || name.includes('index')) return '🏠'
  if (name.includes('install')) return '⚙️'
  if (name.includes('quick')) return '🚀'
  if (name.includes('arch')) return '🏗️'
  if (name.includes('api')) return '🔌'
  if (name.includes('deploy')) return '📦'
  if (name.includes('test')) return '🧪'
  if (name.includes('contrib')) return '🤝'
  if (name.includes('faq')) return '❓'
  return '📄'
}

function formatDocName(name: string): string {
  return name.replace('.md', '').replace(/-/g, ' ').replace(/_/g, ' ')
}

function refreshWikiDoc() {
  // TODO: 刷新文档内容
}

function editWikiDoc() {
  // TODO: 打开编辑模式
}

async function generateWiki() {
  if (!currentProject.value) return

  isGeneratingWiki.value = true
  try {
    const options = {
      readme: !!wikiGenOptions.value.readme,
      installation: !!wikiGenOptions.value.installation,
      architecture: !!wikiGenOptions.value.architecture,
      api: !!wikiGenOptions.value.api,
      deployment: !!wikiGenOptions.value.deployment,
      contributing: !!wikiGenOptions.value.contributing,
    }
    const model = wikiGenOptions.value.model || selectedModel.value
    const note = wikiGenOptions.value.requirements || ''

    const data = await generateWikiApi(currentProject.value.id, options, model, note)
    // 显示任务已接受的消息到对话区
    const notice: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'assistant',
      content: `已接受 Wiki 生成任务 (id: ${data.task_id || 'unknown'})，完成后会通知您。`,
      timestamp: new Date().toISOString()
    }
    messages.value.push(notice)

    showGenerateWikiDialog.value = false
    // 轻微延迟以确保 UI 更新
    await nextTick()
    isGeneratingWiki.value = false
    // 尝试刷新文档列表（如果后端提供）
    loadWikiDocs()
  } catch (error) {
    console.error('Failed to generate wiki:', error)
    isGeneratingWiki.value = false
  }
}

onMounted(() => {
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
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'clear', session_id: sessionId.value }))
  }
  messages.value = []
  currentAssistantMessageId = null
  
  sessionId.value = generateSessionId()
  if (currentProject.value) {
    localStorage.setItem(getProjectSessionKey(currentProject.value.id), sessionId.value)
  }
  localStorage.removeItem(oldStorageKey)
}

function sendMessage() {
  if (!inputMessage.value.trim() || isSending.value) return
  if (!currentProject.value) {
    alert('请先从左侧选择一个项目')
    return
  }
  
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
  
  const assistantMessage: ChatMessage = {
    id: `msg-${Date.now() + 1}`,
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    activities: [],
  }
  messages.value.push(assistantMessage)
  currentAssistantMessageId = assistantMessage.id
  
  ws.send(JSON.stringify({
    type: 'message',
    content: inputMessage.value,
    model: selectedModel.value,
    session_id: sessionId.value,
    project_id: currentProject.value?.id,
    project_path: currentProject.value?.path
  }))
  
  inputMessage.value = ''
  isSending.value = true
  scrollToBottom()
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: calc(100vh - 64px);
  margin: -2rem;
  width: calc(100% + 4rem);
  overflow: hidden;
}

.chat-main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-left h2 {
  margin: 0;
  color: #2c3e50;
  font-size: 1.25rem;
}

.project-desc {
  font-size: 12px;
  color: #666;
}

.header-right {
  display: flex;
  gap: 0.8rem;
  align-items: center;
}

.provider-badge {
  font-size: 0.85rem;
  padding: 0.3rem 0.8rem;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border-radius: 12px;
  font-weight: 600;
  white-space: nowrap;
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

/* Tab 栏 */
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 8px 24px 0;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.tab-btn {
  padding: 10px 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: #333;
  background: #f5f5f5;
}

.tab-btn.active {
  color: #2196f3;
  border-bottom-color: #2196f3;
  font-weight: 500;
}

/* 内容区域 */
.content-area {
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* ===== 对话区域 ===== */
.chat-container {
  height: 100%;
  display: flex;
  flex-direction: column;
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
  background: #f8f9fa;
}

.message-item.user {
  background: #e3f2fd;
  margin-left: 2rem;
}

.message-item.assistant {
  background: #f5f5f5;
  margin-right: 2rem;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
}

.role-badge {
  font-weight: bold;
  color: #555;
}

.timestamp {
  color: #999;
}

.message-content :deep(p) {
  margin: 0.5rem 0;
}

.message-content :deep(pre) {
  background: #f4f4f4;
  padding: 1rem;
  border-radius: 4px;
  overflow-x: auto;
}

.message-content :deep(code) {
  background: #f4f4f4;
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
  font-family: monospace;
}

.input-area {
  padding: 1rem 1.5rem;
  border-top: 1px solid #e0e0e0;
  background: white;
}

.input-controls {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.model-selector {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
}

.btn-new, .btn-clear {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.btn-new:hover, .btn-clear:hover {
  background: #f5f5f5;
}

.input-row {
  display: flex;
  gap: 0.5rem;
}

.input-row textarea {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: none;
  font-family: inherit;
  font-size: 1rem;
}

.input-row textarea:focus {
  outline: none;
  border-color: #2196f3;
}

.input-row textarea:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.btn-send {
  padding: 0.75rem 1.5rem;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}

.btn-send:hover:not(:disabled) {
  background: #1976d2;
}

.btn-send:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* ===== Wiki 区域 ===== */
.wiki-container {
  height: 100%;
  overflow: hidden;
}

.wiki-layout-inner {
  display: flex;
  height: 100%;
}

.wiki-sidebar {
  width: 220px;
  background: #fafafa;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

.wiki-sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.wiki-sidebar-header h4 {
  margin: 0;
  font-size: 14px;
  color: #666;
}

.btn-refresh {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
}

.wiki-doc-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.wiki-empty-tip {
  text-align: center;
  padding: 40px 20px;
  color: #999;
  font-size: 13px;
}

.wiki-doc-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 13px;
  margin-bottom: 2px;
}

.wiki-doc-item:hover {
  background: #e8e8e8;
}

.wiki-doc-item.active {
  background: #2196f3;
  color: white;
}

.doc-icon {
  margin-right: 8px;
}

.doc-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wiki-actions {
  padding: 12px;
  border-top: 1px solid #e0e0e0;
}

.btn-generate {
  width: 100%;
  padding: 10px;
  background: #4caf50;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.btn-generate:hover {
  background: #45a049;
}

.wiki-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: white;
}

.wiki-empty, .wiki-empty-content {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-state {
  text-align: center;
  color: #666;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-state h3 {
  margin: 0 0 8px;
  color: #333;
}

.empty-state p {
  margin: 0 0 24px;
  color: #999;
  line-height: 1.6;
}

.btn-generate-large {
  padding: 12px 24px;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
}

.btn-generate-large:hover {
  background: #1976d2;
}

.wiki-doc-viewer {
  max-width: 900px;
  margin: 0 auto;
}

.wiki-doc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #e0e0e0;
  margin-bottom: 24px;
}

.wiki-doc-header h2 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.doc-actions {
  display: flex;
  gap: 8px;
}

.btn-action {
  width: 36px;
  height: 36px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.btn-action:hover {
  background: #f5f5f5;
}

.wiki-doc-body {
  line-height: 1.8;
  color: #333;
}

.wiki-doc-body :deep(h1) {
  font-size: 32px;
  border-bottom: 2px solid #e0e0e0;
  padding-bottom: 12px;
}

.wiki-doc-body :deep(h2) {
  font-size: 24px;
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 8px;
  margin-top: 32px;
}

.wiki-doc-body :deep(pre) {
  background: #f5f5f5;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
}

/* ===== 对话框 ===== */
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
  width: 480px;
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
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  cursor: pointer;
  color: #666;
}

.dialog-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.project-display {
  padding: 10px 12px;
  background: #f5f5f5;
  border-radius: 6px;
  font-size: 14px;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
}

.checkbox-label input {
  width: auto;
}

.model-selector-dialog {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.model-selector-dialog:focus {
  outline: none;
  border-color: #2196f3;
}

textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
}

.dialog-footer {
  padding: 16px 20px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel, .btn-primary {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.btn-cancel {
  border: 1px solid #ddd;
  background: white;
  color: #666;
}

.btn-primary {
  border: none;
  background: #2196f3;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1976d2;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* 活动卡片 */
.activities-area {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.activity-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
}

.tool-card {
  background: #e8f5e9;
  border: 1px solid #c8e6c9;
}

.llm-card {
  background: #e3f2fd;
  border: 1px solid #bbdefb;
}

.activity-running {
  color: #2196f3;
  font-size: 0.8rem;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 1rem;
  color: #666;
}

.dot-animate {
  animation: bounce 1.4s infinite ease-in-out both;
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>
