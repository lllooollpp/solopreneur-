<template>
  <div class="trace-panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-header" @click="isCollapsed = !isCollapsed">
      <span class="panel-title">📊 调用监控</span>
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

      <!-- 调用链路时间线 -->
      <div class="timeline-section">
        <div class="section-header">
          <h4>🔗 调用链路</h4>
          <button class="btn-clear-trace" @click="clearTrace" title="清空">🗑️</button>
        </div>
        <div class="timeline" ref="timelineRef">
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

const isCollapsed = ref(false)
const traceEvents = ref<TraceEvent[]>([])
const history = ref<HistoryRecord[]>([])
const expandedArgs = reactive(new Set<number>())
const timelineRef = ref<HTMLElement>()

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
  // 同时重置会话统计
  sessionSummary.totalTokens = 0
  sessionSummary.promptTokens = 0
  sessionSummary.completionTokens = 0
  sessionSummary.llmCalls = 0
  sessionSummary.toolCalls = 0
}

function toggleArgs(index: number) {
  if (expandedArgs.has(index)) {
    expandedArgs.delete(index)
  } else {
    expandedArgs.add(index)
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
  width: 360px;
  min-width: 360px;
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
