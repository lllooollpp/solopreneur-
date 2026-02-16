<template>
  <div class="trace-panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-header" @click="isCollapsed = !isCollapsed">
      <span class="panel-title">📊 调用链路</span>
      <span class="toggle-icon">{{ isCollapsed ? '◀' : '▶' }}</span>
    </div>

    <div v-if="!isCollapsed" class="panel-body">
      <!-- 会话累积统计 -->
      <div class="summary-section session-summary">
        <h4>🌐 会话累计 (Session)</h4>
        <div class="stats-grid">
          <div class="stat-item">
            <span class="stat-label">总 Tokens</span>
            <span class="stat-value total">{{ sessionSummary.totalTokens.toLocaleString() }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">LLM 次数</span>
            <span class="stat-value">{{ sessionSummary.llmCalls }}</span>
          </div>
        </div>
      </div>

      <!-- 当前调用统计 -->
      <div class="summary-section">
        <h4>📈 当前调用 (Turn)</h4>
        <div class="stats-grid">
          <div class="stat-item">
            <span class="stat-label">Tokens</span>
            <span class="stat-value total">{{ summary.totalTokens.toLocaleString() }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">输入</span>
            <span class="stat-value prompt">{{ summary.promptTokens.toLocaleString() }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">输出</span>
            <span class="stat-value completion">{{ summary.completionTokens.toLocaleString() }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">耗时</span>
            <span class="stat-value duration">{{ formatDuration(summary.totalDurationMs) }}</span>
          </div>
        </div>
        <div class="stats-grid">
          <div class="stat-item">
            <span class="stat-label">工具调用</span>
            <span class="stat-value">{{ summary.toolCalls }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">状态</span>
            <span :class="['stat-value', 'status', statusClass]">{{ statusText }}</span>
          </div>
        </div>
      </div>

      <!-- Token 进度条 -->
      <div v-if="summary.totalTokens > 0" class="token-bar-section">
        <div class="token-bar">
          <div
            class="token-bar-fill prompt-fill"
            :style="{ width: promptPercent + '%' }"
            :title="`输入: ${summary.promptTokens}`"
          ></div>
          <div
            class="token-bar-fill completion-fill"
            :style="{ width: completionPercent + '%' }"
            :title="`输出: ${summary.completionTokens}`"
          ></div>
        </div>
        <div class="token-bar-legend">
          <span class="legend-item"><span class="dot prompt-dot"></span> 输入 {{ promptPercent }}%</span>
          <span class="legend-item"><span class="dot completion-dot"></span> 输出 {{ completionPercent }}%</span>
        </div>
      </div>

      <!-- 协作调用链路（合并视图） -->
      <div class="collab-section">
        <div class="section-header">
          <h4>🏢🧭 协作调用链（Agent → Skill/Tool）</h4>
          <button class="btn-clear-trace" @click="clearTrace" title="清空">🗑️</button>
        </div>

        <div v-if="agentChains.length === 0" class="empty-timeline">
          暂无调用记录，发送消息后将显示协作动画与调用链路
        </div>

        <div v-else class="collab-content" ref="timelineRef">
          <div class="office-stage">
            <div class="office-floor"></div>
            <div
              v-for="worker in officeWorkers"
              :key="worker.agentName"
              class="worker-lane"
              :class="worker.status"
              :data-selected="selectedAgent === worker.agentName"
              @click="toggleWorkerDetails(worker.agentName)"
            >
              <div class="desk">
                <div class="monitor" :class="worker.status">
                  <span v-if="worker.status === 'busy'" class="typing-dot">●</span>
                  <span v-if="worker.status === 'busy'" class="typing-dot delay-1">●</span>
                  <span v-if="worker.status === 'busy'" class="typing-dot delay-2">●</span>
                  <span v-if="worker.status !== 'busy'" class="monitor-text">{{ worker.status === 'done' ? 'DONE' : 'IDLE' }}</span>
                </div>
              </div>

              <div class="worker-body" :class="worker.status">
                <div class="person-sprite" :class="worker.status">
                  <div class="person-head"></div>
                  <div class="person-torso"></div>
                  <div class="person-leg left"></div>
                  <div class="person-leg right"></div>
                  <div class="person-arm"></div>
                </div>
                <div class="worker-info">
                  <div class="worker-name">{{ worker.agentName }} <span class="role-emoji">{{ worker.emoji }}</span></div>
                  <div class="worker-task">{{ worker.currentTask }}</div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!selectedAgent" class="empty-chain-hint">
            点击上方小人查看该 Agent 的调用工具详情
          </div>

          <div v-else class="chain-list">
          <div
            v-for="(chain, chainIndex) in selectedAgentChains"
            :key="`chain-${chain.agentName}-${chainIndex}`"
            class="agent-chain"
          >
            <div v-if="chainIndex > 0" class="agent-chain-sep">⬇</div>

            <div class="chain-agent-card">
              <div class="chain-title">🤖 Agent</div>
              <div class="chain-subtitle">
                {{ chain.agentName }}
                <span v-if="summary.model && chainIndex === 0">· {{ summary.model }}</span>
              </div>
            </div>

            <div
              v-for="step in chain.steps"
              :key="step.id"
              class="chain-step"
            >
              <div class="chain-arrow">↓</div>
              <div class="chain-step-card">
                <div class="chain-step-head">
                  <div class="chain-step-main">
                    <span class="chain-kind" :class="step.kind">
                      {{ step.kind === 'skill' ? '🧩 Skill' : step.kind === 'agent' ? '🧠 Agent 调用' : '🔧 Tool' }}
                    </span>
                    <span class="chain-name">{{ step.toolName }}</span>
                  </div>
                  <div class="chain-step-meta">
                    <span v-if="step.durationMs" class="meta-chip">⏱️ {{ step.durationMs }}ms</span>
                    <span class="meta-chip" :class="step.done ? 'done' : 'running'">
                      {{ step.done ? '已完成' : '执行中' }}
                    </span>
                    <button class="btn-expand" @click="toggleStep(step.id)">
                      {{ expandedSteps.has(step.id) ? '收起' : '展开' }}
                    </button>
                  </div>
                </div>

                <div v-if="expandedSteps.has(step.id)" class="chain-step-details">
                  <div class="detail-line">执行 Agent: {{ step.agentName }}</div>
                  <div class="detail-line">轮次: #{{ step.iteration }}</div>
                  <div class="detail-line">时间: {{ formatTime(step.timestamp) }}</div>
                  <div class="detail-block">
                    <div class="detail-label">参数</div>
                    <pre>{{ formatArgs(step.toolArgs) }}</pre>
                  </div>
                  <div v-if="step.resultPreview" class="detail-block">
                    <div class="detail-label">结果预览</div>
                    <pre>{{ step.resultPreview }}</pre>
                  </div>
                  <div v-else-if="step.resultLength != null" class="detail-line">
                    输出长度: {{ step.resultLength }} 字符
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      </div>

      <!-- 原始事件流（可展开） -->
      <div class="timeline-section">
        <div class="section-header">
          <h4>🧾 原始事件流</h4>
        </div>
        <div class="timeline">
          <div v-if="traceEvents.length === 0" class="empty-timeline">
            暂无调用记录，发送消息后开始跟踪
          </div>
          <div
            v-for="(event, index) in traceEvents"
            :key="index"
            :class="['timeline-item', event.event]"
          >
            <div class="timeline-dot" :class="event.event"></div>
            <div class="timeline-content">
              <!-- start -->
              <template v-if="event.event === 'start'">
                <div class="event-title">🚀 开始处理</div>
                <div class="event-detail">模型: {{ event.model }}</div>
              </template>

              <!-- agent_start -->
              <template v-else-if="event.event === 'agent_start'">
                <div class="event-title">🤖 Agent 启动: {{ event.agent_name }}</div>
                <div class="event-detail">ID: {{ event.agent_id }}</div>
              </template>

              <!-- agent_end -->
              <template v-else-if="event.event === 'agent_end'">
                <div class="event-title">✅ Agent 完成: {{ event.agent_name }}</div>
                <div class="event-detail">迭代: {{ event.total_iterations }} · 结果 {{ event.result_length }} 字符</div>
              </template>

              <!-- llm_start -->
              <template v-else-if="event.event === 'llm_start'">
                <div class="event-title">🤖 LLM 调用 #{{ event.iteration }}</div>
                <div class="event-detail">模型: {{ event.model }}</div>
              </template>

              <!-- llm_end -->
              <template v-else-if="event.event === 'llm_end'">
                <div class="event-title">✅ LLM 返回 #{{ event.iteration }}</div>
                <div class="event-details-grid">
                  <span>⏱️ {{ event.duration_ms }}ms</span>
                  <span>📥 {{ event.prompt_tokens || 0 }}</span>
                  <span>📤 {{ event.completion_tokens || 0 }}</span>
                  <span>📊 累计 {{ event.cumulative_tokens || 0 }}</span>
                </div>
                <div v-if="event.has_tool_calls" class="event-badge tool-badge">→ 触发工具调用</div>
              </template>

              <!-- skill_start -->
              <template v-else-if="event.event === 'skill_start'">
                <div class="event-title">🧩 Skill: {{ event.skill_name }}</div>
                <div class="event-detail">通过 {{ event.tool_name || 'tool' }} 加载</div>
                <div class="event-detail tool-args" @click="toggleArgs(index)">
                  {{ expandedArgs.has(index) ? '▼' : '▶' }} 参数
                </div>
                <pre v-if="expandedArgs.has(index)" class="args-content">{{ formatArgs(event.tool_args) }}</pre>
              </template>

              <!-- skill_end -->
              <template v-else-if="event.event === 'skill_end'">
                <div class="event-title">✅ Skill {{ event.skill_name }} 已加载</div>
                <div class="event-detail">⏱️ {{ event.duration_ms }}ms · {{ event.result_length }} 字符</div>
                <button v-if="event.result_preview" class="btn-expand-inline" @click="toggleRaw(index)">
                  {{ expandedRaw.has(index) ? '收起结果' : '展开结果' }}
                </button>
                <pre v-if="expandedRaw.has(index) && event.result_preview" class="args-content">{{ event.result_preview }}</pre>
              </template>

              <!-- tool_start -->
              <template v-else-if="event.event === 'tool_start'">
                <div class="event-title">🔧 工具: {{ event.tool_name }}</div>
                <div class="event-detail tool-args" @click="toggleArgs(index)">
                  {{ expandedArgs.has(index) ? '▼' : '▶' }} 参数
                </div>
                <pre v-if="expandedArgs.has(index)" class="args-content">{{ formatArgs(event.tool_args) }}</pre>
              </template>

              <!-- tool_end -->
              <template v-else-if="event.event === 'tool_end'">
                <div class="event-title">✅ {{ event.tool_name }} 完成</div>
                <div class="event-detail">⏱️ {{ event.duration_ms }}ms · {{ event.result_length }} 字符</div>
                <button v-if="event.result_preview" class="btn-expand-inline" @click="toggleRaw(index)">
                  {{ expandedRaw.has(index) ? '收起结果' : '展开结果' }}
                </button>
                <pre v-if="expandedRaw.has(index) && event.result_preview" class="args-content">{{ event.result_preview }}</pre>
              </template>

              <!-- end -->
              <template v-else-if="event.event === 'end'">
                <div class="event-title">🏁 处理完成</div>
                <div class="event-details-grid">
                  <span>⏱️ {{ formatDuration(event.total_duration_ms) }}</span>
                  <span>🔄 {{ event.total_iterations }} 轮</span>
                  <span>📊 {{ (event.total_tokens || 0).toLocaleString() }} tokens</span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史记录 -->
      <div v-if="history.length > 0" class="history-section">
        <h4>📜 历史请求 ({{ history.length }})</h4>
        <div class="history-list">
          <div
            v-for="(item, idx) in history"
            :key="idx"
            class="history-item"
            @click="viewHistory(idx)"
          >
            <span class="history-time">{{ formatTime(item.timestamp) }}</span>
            <span class="history-tokens">{{ item.totalTokens }} tk</span>
            <span class="history-duration">{{ formatDuration(item.totalDurationMs) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, reactive } from 'vue'

interface TraceEvent {
  event: string
  [key: string]: any
}

interface HistoryRecord {
  timestamp: number
  totalTokens: number
  totalDurationMs: number
  events: TraceEvent[]
}

interface ChainStep {
  id: string
  agentName: string
  iteration: number
  toolName: string
  toolArgs?: Record<string, any>
  resultPreview?: string
  resultLength?: number
  durationMs?: number
  timestamp: number
  kind: 'skill' | 'tool' | 'agent'
  done: boolean
}

interface AgentChain {
  agentName: string
  steps: ChainStep[]
}

interface OfficeWorker {
  agentName: string
  emoji: string
  currentTask: string
  status: 'busy' | 'done' | 'idle'
}

const isCollapsed = ref(false)
const traceEvents = ref<TraceEvent[]>([])
const history = ref<HistoryRecord[]>([])
const expandedArgs = reactive(new Set<number>())
const expandedSteps = reactive(new Set<string>())
const expandedRaw = reactive(new Set<number>())
const timelineRef = ref<HTMLElement>()
const selectedAgent = ref<string>('')

// 会话累积统计
const sessionSummary = reactive({
  totalTokens: 0,
  promptTokens: 0,
  completionTokens: 0,
  llmCalls: 0,
  toolCalls: 0,
})

const summary = computed(() => {
  const endEvent = traceEvents.value.find(e => e.event === 'end')
  const startEvent = traceEvents.value.find(e => e.event === 'start')
  const llmEnds = traceEvents.value.filter(e => e.event === 'llm_end')
  const toolStarts = traceEvents.value.filter(e => e.event === 'tool_start')

  return {
    totalTokens: endEvent?.total_tokens || llmEnds.reduce((s, e) => s + (e.total_tokens || 0), 0),
    promptTokens: endEvent?.prompt_tokens || llmEnds.reduce((s, e) => s + (e.prompt_tokens || 0), 0),
    completionTokens: endEvent?.completion_tokens || llmEnds.reduce((s, e) => s + (e.completion_tokens || 0), 0),
    totalDurationMs: endEvent?.total_duration_ms || 0,
    llmCalls: llmEnds.length,
    toolCalls: toolStarts.length,
    model: startEvent?.model || '',
    isRunning: traceEvents.value.length > 0 && !endEvent,
  }
})

const statusClass = computed(() => {
  if (traceEvents.value.length === 0) return 'idle'
  return summary.value.isRunning ? 'running' : 'done'
})

const statusText = computed(() => {
  if (traceEvents.value.length === 0) return '空闲'
  return summary.value.isRunning ? '运行中...' : '已完成'
})

const promptPercent = computed(() => {
  const total = summary.value.totalTokens
  if (total === 0) return 0
  return Math.round((summary.value.promptTokens / total) * 100)
})

const completionPercent = computed(() => {
  const total = summary.value.totalTokens
  if (total === 0) return 0
  return Math.round((summary.value.completionTokens / total) * 100)
})

const agentChains = computed<AgentChain[]>(() => {
  const chains: AgentChain[] = []
  const chainMap = new Map<string, AgentChain>()
  const pending = new Map<string, ChainStep[]>()
  const hasSkillEvents = traceEvents.value.some(e => e.event === 'skill_start' || e.event === 'skill_end')

  function upsertChain(agentName: string): AgentChain {
    const normalized = agentName || '主控 Agent'
    if (!chainMap.has(normalized)) {
      const chain = { agentName: normalized, steps: [] }
      chainMap.set(normalized, chain)
      chains.push(chain)
    }
    return chainMap.get(normalized)!
  }

  function buildToolKey(event: TraceEvent, agentName: string): string {
    const iteration = event.iteration || 0
    let toolKey = String(event.tool_name || '')
    if (toolKey === 'delegate' && event.delegate_agent) {
      toolKey = `${toolKey}:${event.delegate_agent}`
    }
    return `${agentName}:${iteration}:${toolKey}`
  }

  traceEvents.value.forEach((event, index) => {
    if (event.event === 'start') {
      upsertChain(event.agent_name || '主控 Agent')
      return
    }

    if (event.event === 'agent_start') {
      upsertChain(event.agent_name || 'unknown-agent')
      return
    }

    if (event.event === 'skill_start') {
      const agentName = event.agent_name || '主控 Agent'
      const key = `${agentName}:${event.iteration || 0}:skill:${event.skill_name || ''}`
      const chain = upsertChain(agentName)
      const step: ChainStep = {
        id: `step-${index}`,
        agentName,
        iteration: event.iteration || 0,
        toolName: event.skill_name || 'unknown_skill',
        toolArgs: event.tool_args,
        timestamp: event.timestamp || Date.now() / 1000,
        kind: 'skill',
        done: false,
      }
      if (!pending.has(key)) pending.set(key, [])
      pending.get(key)!.push(step)
      chain.steps.push(step)
      return
    }

    if (event.event === 'skill_end') {
      const agentName = event.agent_name || '主控 Agent'
      const key = `${agentName}:${event.iteration || 0}:skill:${event.skill_name || ''}`
      const queue = pending.get(key)
      const current = queue && queue.length > 0 ? queue.shift() : null
      if (current) {
        current.done = true
        current.durationMs = event.duration_ms
        current.resultLength = event.result_length
        current.resultPreview = event.result_preview
        current.timestamp = event.timestamp || current.timestamp
      }
      return
    }

    if (event.event === 'tool_start') {
      const agentName = event.agent_name || '主控 Agent'
      if (hasSkillEvents && isSkillToolCall(event.tool_name, event.tool_args) && agentName === '主控 Agent') {
        return
      }
      const key = buildToolKey(event, agentName)
      const chain = upsertChain(agentName)
      const isDelegate = event.tool_name === 'delegate' && !!event.delegate_agent
      const step: ChainStep = {
        id: `step-${index}`,
        agentName,
        iteration: event.iteration || 0,
        toolName: isDelegate ? `delegate → ${event.delegate_agent}` : (event.tool_name || 'unknown_tool'),
        toolArgs: event.tool_args,
        timestamp: event.timestamp || Date.now() / 1000,
        kind: isDelegate ? 'agent' : (isSkillToolCall(event.tool_name, event.tool_args) ? 'skill' : 'tool'),
        done: false,
      }
      if (!pending.has(key)) pending.set(key, [])
      pending.get(key)!.push(step)
      chain.steps.push(step)
      return
    }

    if (event.event === 'tool_end') {
      const agentName = event.agent_name || '主控 Agent'
      if (hasSkillEvents && isSkillToolCall(event.tool_name) && agentName === '主控 Agent') {
        return
      }
      const key = buildToolKey(event, agentName)
      const queue = pending.get(key)
      const current = queue && queue.length > 0 ? queue.shift() : null
      if (current) {
        current.done = true
        current.durationMs = event.duration_ms
        current.resultLength = event.result_length
        current.resultPreview = event.result_preview
        current.timestamp = event.timestamp || current.timestamp
      }
    }
  })

  return chains
})

const officeWorkers = computed<OfficeWorker[]>(() => {
  return agentChains.value.map((chain) => {
    const runningStep = chain.steps.find((s) => !s.done)
    const lastStep = chain.steps.length > 0 ? chain.steps[chain.steps.length - 1] : null

    let status: 'busy' | 'done' | 'idle' = 'idle'
    let currentTask = '等待任务...'

    if (runningStep && summary.value.isRunning) {
      status = 'busy'
      currentTask = `${runningStep.kind === 'skill' ? 'Skill' : runningStep.kind === 'agent' ? 'Agent' : 'Tool'} · ${runningStep.toolName}`
    } else if (lastStep) {
      status = 'done'
      currentTask = `完成：${lastStep.toolName}`
    }

    return {
      agentName: chain.agentName,
      emoji: roleEmoji(chain.agentName),
      currentTask,
      status,
    }
  })
})

const selectedAgentChains = computed<AgentChain[]>(() => {
  if (!selectedAgent.value) return []
  return agentChains.value.filter(c => c.agentName === selectedAgent.value)
})

function roleEmoji(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('architect')) return '🏗️'
  if (n.includes('developer') || n.includes('dev')) return '👨‍💻'
  if (n.includes('tester') || n.includes('qa')) return '🧪'
  if (n.includes('review')) return '🔍'
  if (n.includes('devops')) return '🚀'
  if (n.includes('product') || n.includes('pm')) return '📋'
  if (n.includes('main') || n.includes('主控')) return '🧠'
  return '🧑‍💼'
}

function isSkillToolCall(toolName?: string, toolArgs?: Record<string, any>): boolean {
  if (!toolName) return false
  if (toolName.startsWith('skill_')) return true
  if (toolName !== 'read_file') return false
  const path = String(toolArgs?.path || '')
  const normalized = path.replace(/\\/g, '/').toLowerCase()
  return normalized.includes('/skills/') && normalized.endsWith('/skill.md')
}

function handleTraceEvent(event: TraceEvent) {
  // 调试日志
  if (event.event === 'llm_end') {
    console.log('TracePanel: 收到 llm_end 事件', {
      prompt_tokens: event.prompt_tokens,
      completion_tokens: event.completion_tokens,
      total_tokens: event.total_tokens,
      duration_ms: event.duration_ms,
    })
  }

  if (event.event === 'start') {
    // 保存旧的到历史
    if (traceEvents.value.length > 0) {
      const endEvt = traceEvents.value.find(e => e.event === 'end')
      if (endEvt) {
        history.value.unshift({
          timestamp: endEvt.timestamp || Date.now() / 1000,
          totalTokens: endEvt.total_tokens || 0,
          totalDurationMs: endEvt.total_duration_ms || 0,
          events: [...traceEvents.value],
        })
        if (history.value.length > 20) history.value.pop()
      }
    }
    traceEvents.value = []
    expandedArgs.clear()
    expandedSteps.clear()
    expandedRaw.clear()
    selectedAgent.value = ''
  }

  // 累积到会话统计
  if (event.event === 'llm_end') {
    sessionSummary.promptTokens += (event.prompt_tokens || 0)
    sessionSummary.completionTokens += (event.completion_tokens || 0)
    sessionSummary.totalTokens += (event.total_tokens || 0)
    sessionSummary.llmCalls += 1
  } else if (event.event === 'tool_start') {
    sessionSummary.toolCalls += 1
  }

  traceEvents.value.push(event)
  scrollTimeline()
}

async function scrollTimeline() {
  await nextTick()
  if (timelineRef.value) {
    timelineRef.value.scrollTop = timelineRef.value.scrollHeight
  }
}

function clearTrace() {
  traceEvents.value = []
  expandedArgs.clear()
  expandedSteps.clear()
  expandedRaw.clear()
  selectedAgent.value = ''
  // 同时重置会话统计
  sessionSummary.totalTokens = 0
  sessionSummary.promptTokens = 0
  sessionSummary.completionTokens = 0
  sessionSummary.llmCalls = 0
  sessionSummary.toolCalls = 0
}

function toggleWorkerDetails(agentName: string) {
  selectedAgent.value = selectedAgent.value === agentName ? '' : agentName
}

function toggleArgs(index: number) {
  if (expandedArgs.has(index)) {
    expandedArgs.delete(index)
  } else {
    expandedArgs.add(index)
  }
}

function toggleStep(id: string) {
  if (expandedSteps.has(id)) {
    expandedSteps.delete(id)
  } else {
    expandedSteps.add(id)
  }
}

function toggleRaw(index: number) {
  if (expandedRaw.has(index)) {
    expandedRaw.delete(index)
  } else {
    expandedRaw.add(index)
  }
}

function formatArgs(args: any): string {
  if (!args) return '{}'
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
}

function formatDuration(ms: number): string {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('zh-CN')
}

function viewHistory(idx: number) {
  const item = history.value[idx]
  if (item) {
    traceEvents.value = [...item.events]
    expandedArgs.clear()
  }
}

defineExpose({ handleTraceEvent })
</script>

<style scoped>
.trace-panel {
  width: 100%;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  border-left: 1px solid #e0e0e0;
  overflow: hidden;
  transition: width 0.3s, min-width 0.3s;
}

.trace-panel.collapsed {
  width: 40px;
  min-width: 40px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.8rem 1rem;
  background: #f0f4f8;
  border-bottom: 1px solid #e0e0e0;
  cursor: pointer;
  user-select: none;
}

.collapsed .panel-header {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  padding: 1rem 0.5rem;
  justify-content: flex-start;
  gap: 0.5rem;
}

.panel-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #2c3e50;
}

.toggle-icon {
  font-size: 0.8rem;
  color: #999;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* 汇总统计 */
.summary-section {
  padding: 0.8rem 1rem;
  border-bottom: 1px solid #eee;
}

.session-summary {
  background: #fdf6ff;
  border-bottom: 2px solid #e1bee7;
}

.summary-section h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.85rem;
  color: #555;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
  margin-bottom: 0.4rem;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.25rem 0.5rem;
  background: white;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
}

.stat-label {
  font-size: 0.75rem;
  color: #888;
}

.stat-value {
  font-size: 0.8rem;
  font-weight: 600;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
}

.stat-value.total { color: #1976d2; }
.stat-value.prompt { color: #7b1fa2; }
.stat-value.completion { color: #388e3c; }
.stat-value.duration { color: #e65100; }
.stat-value.model { color: #555; font-size: 0.7rem; }
.stat-value.status.idle { color: #999; }
.stat-value.status.running { color: #e65100; }
.stat-value.status.done { color: #388e3c; }

/* Token 进度条 */
.token-bar-section {
  padding: 0.4rem 1rem 0.6rem;
  border-bottom: 1px solid #eee;
}

.token-bar {
  height: 8px;
  background: #eee;
  border-radius: 4px;
  display: flex;
  overflow: hidden;
}

.token-bar-fill {
  height: 100%;
  transition: width 0.3s;
}

.prompt-fill { background: #7b1fa2; }
.completion-fill { background: #388e3c; }

.token-bar-legend {
  display: flex;
  gap: 1rem;
  margin-top: 0.3rem;
  font-size: 0.7rem;
  color: #888;
}

.legend-item { display: flex; align-items: center; gap: 0.3rem; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.prompt-dot { background: #7b1fa2; }
.completion-dot { background: #388e3c; }

/* 时间线 */
.timeline-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0.4rem 0;
  border-top: 1px solid #eee;
}

.collab-section {
  display: flex;
  flex-direction: column;
  max-height: 56%;
  min-height: 260px;
  border-bottom: 1px solid #eee;
}

.collab-content {
  overflow-y: auto;
  padding-bottom: 0.5rem;
}

.office-stage {
  margin: 0 0.8rem 0.5rem;
  border: 1px solid #dbe4f0;
  border-radius: 10px;
  background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
  padding: 0.6rem;
  position: relative;
  overflow: hidden;
}

.office-floor {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 26%;
  background: repeating-linear-gradient(
    45deg,
    rgba(203, 213, 225, 0.28),
    rgba(203, 213, 225, 0.28) 8px,
    rgba(226, 232, 240, 0.28) 8px,
    rgba(226, 232, 240, 0.28) 16px
  );
}

.worker-lane {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 0.36rem 0.4rem;
  border-radius: 8px;
  margin-bottom: 0.36rem;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(203, 213, 225, 0.6);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}

.worker-lane:hover {
  transform: translateY(-1px);
  border-color: #93c5fd;
  box-shadow: 0 4px 12px rgba(30, 64, 175, 0.08);
}

.worker-lane[data-selected="true"] {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.desk {
  width: 48px;
  height: 32px;
  background: #94a3b8;
  border-radius: 4px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 3px;
  box-shadow: inset 0 -4px 0 rgba(51, 65, 85, 0.18);
}

.monitor {
  width: 34px;
  height: 16px;
  border-radius: 3px;
  background: #1f2937;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f8fafc;
  font-size: 0.52rem;
}

.monitor.busy {
  background: #0f172a;
}

.monitor.done {
  background: #14532d;
}

.monitor.idle {
  background: #374151;
}

.monitor-text {
  letter-spacing: 0.4px;
}

.typing-dot {
  color: #22c55e;
  font-size: 0.5rem;
  animation: blink 1.1s infinite;
}

.typing-dot.delay-1 {
  animation-delay: 0.2s;
}

.typing-dot.delay-2 {
  animation-delay: 0.4s;
}

.worker-body {
  flex: 1;
  margin-left: 0.55rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}

.person-sprite {
  width: 28px;
  height: 28px;
  position: relative;
  flex-shrink: 0;
}

.person-head {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f1c27d;
  position: absolute;
  left: 9px;
  top: 0;
  border: 1px solid rgba(120, 53, 15, 0.15);
}

.person-torso {
  width: 12px;
  height: 9px;
  border-radius: 4px;
  background: #3b82f6;
  position: absolute;
  left: 8px;
  top: 10px;
}

.person-leg {
  width: 4px;
  height: 8px;
  border-radius: 3px;
  background: #334155;
  position: absolute;
  top: 19px;
}

.person-leg.left { left: 9px; }
.person-leg.right { left: 15px; }

.person-arm {
  width: 8px;
  height: 3px;
  border-radius: 3px;
  background: #1d4ed8;
  position: absolute;
  top: 13px;
  left: 17px;
  transform-origin: left center;
}

.worker-body.busy .person-sprite {
  animation: bob 1.1s ease-in-out infinite;
}

.worker-body.busy .person-leg.left {
  animation: walk-left 0.65s ease-in-out infinite;
}

.worker-body.busy .person-leg.right {
  animation: walk-right 0.65s ease-in-out infinite;
}

.worker-body.busy .person-arm {
  animation: arm-type 0.7s ease-in-out infinite;
}

.worker-body.done .person-torso {
  background: #16a34a;
}

.role-emoji {
  font-size: 0.78rem;
  opacity: 0.88;
}

.worker-info {
  min-width: 0;
}

.worker-name {
  font-size: 0.74rem;
  color: #1e293b;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.worker-task {
  margin-top: 2px;
  font-size: 0.67rem;
  color: #475569;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@keyframes bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}

@keyframes walk-left {
  0%, 100% { transform: rotate(10deg); }
  50% { transform: rotate(-12deg); }
}

@keyframes walk-right {
  0%, 100% { transform: rotate(-10deg); }
  50% { transform: rotate(12deg); }
}

@keyframes arm-type {
  0%, 100% { transform: rotate(6deg); }
  50% { transform: rotate(-24deg); }
}

@keyframes blink {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 1; }
}

.chain-list {
  padding: 0 0.8rem 0.6rem;
}

.empty-chain-hint {
  margin: 0.2rem 0.8rem 0.6rem;
  padding: 0.7rem 0.8rem;
  font-size: 0.74rem;
  color: #64748b;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
}

.agent-chain {
  margin-bottom: 0.55rem;
}

.agent-chain-sep {
  text-align: center;
  color: #94a3b8;
  font-size: 0.78rem;
  margin: 0.15rem 0 0.25rem;
}

.chain-agent-card {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  border-radius: 8px;
  padding: 0.55rem 0.7rem;
}

.chain-title {
  font-size: 0.78rem;
  color: #1e3a8a;
  font-weight: 700;
}

.chain-subtitle {
  margin-top: 2px;
  font-size: 0.72rem;
  color: #334155;
}

.chain-step {
  margin-top: 0.35rem;
}

.chain-arrow {
  color: #94a3b8;
  font-size: 0.78rem;
  padding-left: 6px;
  margin-bottom: 2px;
}

.chain-step-card {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
}

.chain-step-head {
  display: flex;
  justify-content: space-between;
  gap: 0.4rem;
}

.chain-step-main {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.chain-kind {
  font-size: 0.68rem;
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.chain-kind.skill {
  color: #6d28d9;
  background: #f3e8ff;
}

.chain-kind.tool {
  color: #0f766e;
  background: #ccfbf1;
}

.chain-kind.agent {
  color: #1e3a8a;
  background: #dbeafe;
}

.chain-name {
  font-size: 0.79rem;
  font-weight: 600;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chain-step-meta {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.meta-chip {
  font-size: 0.67rem;
  padding: 1px 5px;
  border-radius: 10px;
  background: #f3f4f6;
  color: #4b5563;
  white-space: nowrap;
}

.meta-chip.done {
  background: #dcfce7;
  color: #166534;
}

.meta-chip.running {
  background: #ffedd5;
  color: #9a3412;
}

.btn-expand {
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 4px;
  padding: 0 6px;
  height: 22px;
  font-size: 0.67rem;
  cursor: pointer;
}

.btn-expand:hover {
  background: #f9fafb;
}

.chain-step-details {
  margin-top: 0.45rem;
  padding-top: 0.45rem;
  border-top: 1px dashed #e5e7eb;
}

.detail-line {
  font-size: 0.71rem;
  color: #6b7280;
  margin-bottom: 0.25rem;
}

.detail-block {
  margin-top: 0.35rem;
}

.detail-label {
  font-size: 0.69rem;
  color: #6b7280;
  margin-bottom: 2px;
}

.detail-block pre {
  margin: 0;
  padding: 0.42rem;
  font-size: 0.68rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 140px;
  overflow-y: auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 1rem;
}

.section-header h4 {
  margin: 0;
  font-size: 0.85rem;
  color: #555;
}

.btn-clear-trace {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0.2rem;
  opacity: 0.5;
}

.btn-clear-trace:hover { opacity: 1; }

.timeline {
  flex: 1;
  overflow-y: auto;
  padding: 0 0.8rem 0.5rem 1.2rem;
}

.empty-timeline {
  text-align: center;
  color: #bbb;
  padding: 2rem 0;
  font-size: 0.85rem;
}

.timeline-item {
  display: flex;
  gap: 0.6rem;
  padding: 0.3rem 0;
  position: relative;
}

.timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 18px;
  bottom: -4px;
  width: 2px;
  background: #e0e0e0;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-top: 3px;
  flex-shrink: 0;
  z-index: 1;
}

.timeline-dot.start { background: #1976d2; }
.timeline-dot.llm_start { background: #ff9800; }
.timeline-dot.llm_end { background: #4caf50; }
.timeline-dot.skill_start { background: #7c3aed; }
.timeline-dot.skill_end { background: #a78bfa; }
.timeline-dot.tool_start { background: #9c27b0; }
.timeline-dot.tool_end { background: #8bc34a; }
.timeline-dot.end { background: #2196f3; }

.timeline-content {
  flex: 1;
  min-width: 0;
}

.event-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 2px;
}

.event-detail {
  font-size: 0.72rem;
  color: #888;
}

.event-details-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.72rem;
  color: #666;
}

.event-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.68rem;
  margin-top: 2px;
}

.tool-badge {
  background: #fff3e0;
  color: #e65100;
}

.tool-args {
  cursor: pointer;
  color: #7b1fa2;
}

.tool-args:hover {
  text-decoration: underline;
}

.args-content {
  margin: 4px 0 0;
  padding: 0.4rem;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 0.7rem;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: #333;
}

.btn-expand-inline {
  margin-top: 4px;
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 4px;
  padding: 0 6px;
  height: 22px;
  font-size: 0.67rem;
  cursor: pointer;
}

/* 历史记录 */
.history-section {
  padding: 0.5rem 1rem;
  border-top: 1px solid #eee;
}

.history-section h4 {
  margin: 0 0 0.4rem 0;
  font-size: 0.85rem;
  color: #555;
}

.history-list {
  max-height: 120px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  justify-content: space-between;
  padding: 0.25rem 0.4rem;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.72rem;
  color: #666;
}

.history-item:hover {
  background: #e3f2fd;
}

.history-time { flex: 1; }
.history-tokens { margin: 0 0.5rem; color: #1976d2; font-weight: 500; }
.history-duration { color: #e65100; }
</style>
