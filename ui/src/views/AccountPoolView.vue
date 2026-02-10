<template>
  <div class="account-pool">
    <div class="page-header">
      <h2>🔑 账号池管理</h2>
      <p class="page-desc">管理多个 GitHub Copilot 账号，实现负载均衡与 429 自动切换</p>
    </div>

    <!-- 状态概览 -->
    <div class="overview-bar">
      <div class="overview-item">
        <span class="ov-label">总账号</span>
        <span class="ov-value">{{ poolStatus.total_count }}</span>
      </div>
      <div class="overview-item active">
        <span class="ov-label">可用</span>
        <span class="ov-value">{{ poolStatus.active_count }}</span>
      </div>
      <div class="overview-item">
        <span class="ov-label">状态</span>
        <span :class="['ov-badge', poolStatus.authenticated ? 'ok' : 'off']">
          {{ poolStatus.authenticated ? '已认证' : '未认证' }}
        </span>
      </div>
      <div class="overview-actions">
        <button class="btn-primary" @click="openAddModal">
          ➕ 添加账号
        </button>
        <button class="btn-icon" @click="refreshStatus" :disabled="refreshing" title="刷新状态">
          <span :class="{ spinning: refreshing }">🔄</span>
        </button>
      </div>
    </div>

    <!-- 账号列表 -->
    <div v-if="poolStatus.slots.length === 0" class="empty-state">
      <div class="empty-icon">🔓</div>
      <h3>暂无账号</h3>
      <p>点击"添加账号"按钮，通过 GitHub 设备流登录来添加 Copilot 账号</p>
      <button class="btn-primary btn-lg" @click="openAddModal">添加第一个账号</button>
    </div>

    <div v-else class="slots-grid">
      <div
        v-for="slot in poolStatus.slots"
        :key="slot.slot_id"
        :class="['slot-card', `state-${slot.state}`]"
      >
        <!-- 卡片头：状态指示灯 + 编号 -->
        <div class="slot-header">
          <div class="slot-id-badge">
            <span class="slot-dot" :class="slot.state"></span>
            Slot {{ slot.slot_id }}
          </div>
          <span :class="['state-tag', slot.state]">{{ stateText(slot.state) }}</span>
        </div>

        <!-- 标签名 -->
        <div class="slot-label">
          <span v-if="!editingLabel[slot.slot_id]" @dblclick="startEditLabel(slot)">
            {{ slot.label || `账号${slot.slot_id}` }}
          </span>
          <input
            v-else
            v-model="editLabelValue"
            class="label-input"
            @keydown.enter="saveLabel(slot.slot_id)"
            @keydown.escape="cancelEditLabel(slot.slot_id)"
            @blur="saveLabel(slot.slot_id)"
            ref="labelInput"
            autofocus
          />
        </div>

        <!-- 统计信息 -->
        <div class="slot-stats">
          <div class="stat-row">
            <span class="stat-key">总请求</span>
            <span class="stat-val">{{ slot.total_requests.toLocaleString() }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-key">429 次数</span>
            <span :class="['stat-val', slot.total_429s > 0 ? 'warn' : '']">
              {{ slot.total_429s }}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-key">Token 过期</span>
            <span class="stat-val">{{ formatExpiry(slot.token_expires) }}</span>
          </div>
          <div v-if="slot.state === 'cooling' && slot.cooling_remaining" class="stat-row">
            <span class="stat-key">冷却剩余</span>
            <span class="stat-val warn">{{ slot.cooling_remaining }}</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="slot-actions">
          <button
            class="btn-sm btn-outline"
            @click="handleRefreshSlot(slot.slot_id)"
            :disabled="actionLoading[slot.slot_id]"
            title="刷新 Token"
          >
            🔄 刷新
          </button>
          <button
            class="btn-sm btn-danger-outline"
            @click="handleRemoveSlot(slot.slot_id, slot.label)"
            :disabled="actionLoading[slot.slot_id]"
            title="移除账号"
          >
            🗑️ 移除
          </button>
        </div>
      </div>
    </div>

    <!-- 添加账号模态框 -->
    <div v-if="showAddModal" class="modal-overlay" @click="closeAddModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>添加 GitHub Copilot 账号</h3>
          <button class="modal-close" @click="closeAddModal">✕</button>
        </div>

        <!-- 步骤 1：设置标签 -->
        <div v-if="addFlow.step === 'label'" class="add-step">
          <div class="step-icon">🏷️</div>
          <p class="step-desc">为新账号设置一个标签（可选）</p>
          <input
            v-model="addFlow.label"
            class="input-field"
            placeholder="例如：个人账号、公司账号A..."
            @keydown.enter="startDeviceFlow"
          />
          <button class="btn-primary btn-full" @click="startDeviceFlow">
            开始认证
          </button>
        </div>

        <!-- 步骤 2：等待用户授权 -->
        <div v-else-if="addFlow.step === 'waiting'" class="add-step">
          <div class="step-instructions">
            <p class="instruction-title">请在浏览器中完成授权：</p>

            <div class="auth-step-card">
              <div class="step-num">1</div>
              <div class="step-body">
                <p>访问以下网址：</p>
                <a :href="addFlow.verificationUri" target="_blank" class="auth-link">
                  {{ addFlow.verificationUri }}
                </a>
              </div>
            </div>

            <div class="auth-step-card">
              <div class="step-num">2</div>
              <div class="step-body">
                <p>输入验证码：</p>
                <div class="code-display" @click="copyUserCode">
                  {{ addFlow.userCode }}
                  <span class="copy-hint">{{ codeCopied ? '✅ 已复制' : '点击复制' }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="waiting-indicator">
            <span class="pulse-dot"></span>
            等待授权中...
          </div>

          <div v-if="addFlow.error" class="flow-error">
            ⚠️ {{ addFlow.error }}
          </div>
        </div>

        <!-- 步骤 3：成功 -->
        <div v-else-if="addFlow.step === 'success'" class="add-step success-step">
          <div class="success-icon">✅</div>
          <h4>账号添加成功！</h4>
          <p>Slot {{ addFlow.resultSlotId }} ({{ addFlow.resultLabel }}) 已加入池</p>
          <button class="btn-primary btn-full" @click="closeAddModal">完成</button>
        </div>

        <!-- 步骤 4：失败 -->
        <div v-else-if="addFlow.step === 'error'" class="add-step error-step">
          <div class="error-icon">❌</div>
          <h4>添加失败</h4>
          <p class="error-msg">{{ addFlow.error }}</p>
          <div class="error-actions">
            <button class="btn-primary" @click="resetAddFlow">重试</button>
            <button class="btn-secondary" @click="closeAddModal">关闭</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 确认删除模态框 -->
    <div v-if="showRemoveConfirm" class="modal-overlay" @click="showRemoveConfirm = false">
      <div class="modal-content modal-sm" @click.stop>
        <h3>确认移除</h3>
        <p>确定要移除 <strong>{{ removeTarget.label }}</strong> (Slot {{ removeTarget.slotId }}) 吗？</p>
        <p class="hint-text">移除后需要重新登录才能恢复此账号。</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showRemoveConfirm = false">取消</button>
          <button class="btn-danger" @click="confirmRemove">确认移除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, reactive } from 'vue'
import {
  getPoolStatus,
  startPoolLogin,
  pollPoolLogin,
  removePoolSlot,
  refreshPoolSlot,
  updateSlotLabel,
  type PoolStatus,
  type PoolSlot,
} from '@/api/pool'

// ========================================================================
// 状态
// ========================================================================

const poolStatus = reactive<PoolStatus>({
  authenticated: false,
  slots: [],
  active_count: 0,
  total_count: 0,
})

const refreshing = ref(false)
const actionLoading = reactive<Record<number, boolean>>({})
const editingLabel = reactive<Record<number, boolean>>({})
const editLabelValue = ref('')
const codeCopied = ref(false)

// 添加账号流程
const showAddModal = ref(false)
const addFlow = reactive({
  step: 'label' as 'label' | 'waiting' | 'success' | 'error',
  label: '',
  deviceCode: '',
  userCode: '',
  verificationUri: '',
  error: null as string | null,
  resultSlotId: 0,
  resultLabel: '',
})

// 删除确认
const showRemoveConfirm = ref(false)
const removeTarget = reactive({ slotId: 0, label: '' })

// 轮询定时器
let pollTimer: number | null = null
let statusTimer: number | null = null

// ========================================================================
// 生命周期
// ========================================================================

onMounted(async () => {
  await refreshStatus()
  // 每 15 秒自动刷新状态
  statusTimer = window.setInterval(refreshStatus, 15000)
})

onUnmounted(() => {
  stopPollTimer()
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
})

// ========================================================================
// 状态刷新
// ========================================================================

async function refreshStatus() {
  refreshing.value = true
  try {
    const status = await getPoolStatus()
    poolStatus.authenticated = status.authenticated
    poolStatus.slots = status.slots
    poolStatus.active_count = status.active_count
    poolStatus.total_count = status.total_count
  } catch (e) {
    console.error('获取池状态失败:', e)
  } finally {
    refreshing.value = false
  }
}

// ========================================================================
// 添加账号
// ========================================================================

function openAddModal() {
  resetAddFlow()
  showAddModal.value = true
}

function closeAddModal() {
  showAddModal.value = false
  stopPollTimer()
  resetAddFlow()
  // 关闭后刷新状态
  refreshStatus()
}

function resetAddFlow() {
  addFlow.step = 'label'
  addFlow.label = ''
  addFlow.deviceCode = ''
  addFlow.userCode = ''
  addFlow.verificationUri = ''
  addFlow.error = null
  addFlow.resultSlotId = 0
  addFlow.resultLabel = ''
  codeCopied.value = false
  stopPollTimer()
}

async function startDeviceFlow() {
  try {
    addFlow.error = null
    const flow = await startPoolLogin(addFlow.label)
    addFlow.deviceCode = flow.device_code
    addFlow.userCode = flow.user_code
    addFlow.verificationUri = flow.verification_uri
    addFlow.step = 'waiting'

    // 开始轮询
    startPollTimer()
  } catch (e: any) {
    addFlow.step = 'error'
    addFlow.error = e.response?.data?.detail || e.message || '启动设备流失败'
  }
}

let pollDelay = 5000
let pollAttempts = 0
const MAX_ATTEMPTS = 60 // 5分钟 (60 * 5s)

function startPollTimer() {
  pollDelay = 5000
  pollAttempts = 0
  doPoll()
}

function doPoll() {
  pollTimer = window.setTimeout(async () => {
    pollAttempts++
    if (pollAttempts > MAX_ATTEMPTS) {
      addFlow.step = 'error'
      addFlow.error = '认证超时（5分钟），请重试'
      return
    }

    try {
      const result = await pollPoolLogin(addFlow.deviceCode, 0, addFlow.label)

      if (result.status === 'success') {
        stopPollTimer()
        addFlow.step = 'success'
        addFlow.resultSlotId = result.slot_id!
        addFlow.resultLabel = result.label!
      } else if (result.status === 'pending') {
        doPoll()
      } else if (result.status === 'slow_down') {
        pollDelay = Math.min(pollDelay + 5000, 30000)
        addFlow.error = `请求过快，${pollDelay / 1000}s 后重试...`
        doPoll()
      } else if (result.status === 'error') {
        stopPollTimer()
        addFlow.step = 'error'
        addFlow.error = result.error || '认证失败'
      }
    } catch (e: any) {
      // 网络错误等，继续重试
      if (pollAttempts < MAX_ATTEMPTS) {
        addFlow.error = `轮询出错，继续重试... (${e.message})`
        doPoll()
      } else {
        stopPollTimer()
        addFlow.step = 'error'
        addFlow.error = e.message || '轮询失败'
      }
    }
  }, pollDelay)
}

function stopPollTimer() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function copyUserCode() {
  navigator.clipboard.writeText(addFlow.userCode).then(() => {
    codeCopied.value = true
    setTimeout(() => (codeCopied.value = false), 2000)
  })
}

// ========================================================================
// Slot 操作
// ========================================================================

async function handleRefreshSlot(slotId: number) {
  actionLoading[slotId] = true
  try {
    await refreshPoolSlot(slotId)
    await refreshStatus()
  } catch (e: any) {
    alert(`刷新失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    actionLoading[slotId] = false
  }
}

function handleRemoveSlot(slotId: number, label: string) {
  removeTarget.slotId = slotId
  removeTarget.label = label
  showRemoveConfirm.value = true
}

async function confirmRemove() {
  const slotId = removeTarget.slotId
  showRemoveConfirm.value = false
  actionLoading[slotId] = true
  try {
    await removePoolSlot(slotId)
    await refreshStatus()
  } catch (e: any) {
    alert(`移除失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    actionLoading[slotId] = false
  }
}

// ========================================================================
// 标签编辑
// ========================================================================

function startEditLabel(slot: PoolSlot) {
  editLabelValue.value = slot.label
  editingLabel[slot.slot_id] = true
}

async function saveLabel(slotId: number) {
  if (!editingLabel[slotId]) return
  editingLabel[slotId] = false
  try {
    await updateSlotLabel(slotId, editLabelValue.value)
    await refreshStatus()
  } catch (e: any) {
    console.error('更新标签失败:', e)
  }
}

function cancelEditLabel(slotId: number) {
  editingLabel[slotId] = false
}

// ========================================================================
// 辅助函数
// ========================================================================

function stateText(state: string): string {
  switch (state) {
    case 'active': return '🟢 正常'
    case 'cooling': return '🟡 冷却中'
    case 'expired': return '🟠 已过期'
    case 'dead': return '🔴 失效'
    default: return state
  }
}

function formatExpiry(isoString: string): string {
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diff = date.getTime() - now.getTime()

    if (diff < 0) return '已过期'

    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins} 分钟后`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours} 小时后`

    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoString
  }
}
</script>

<style scoped>
.account-pool {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

/* ── 页面头部 ── */
.page-header {
  margin-bottom: 2rem;
}
.page-header h2 {
  margin: 0 0 0.5rem 0;
  color: #2c3e50;
}
.page-desc {
  color: #757575;
  margin: 0;
  font-size: 0.95rem;
}

/* ── 概览栏 ── */
.overview-bar {
  display: flex;
  align-items: center;
  gap: 2rem;
  background: white;
  border-radius: 12px;
  padding: 1.2rem 2rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  margin-bottom: 2rem;
  flex-wrap: wrap;
}
.overview-item {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.ov-label {
  font-size: 0.8rem;
  color: #9e9e9e;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.ov-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: #2c3e50;
}
.overview-item.active .ov-value {
  color: #4caf50;
}
.ov-badge {
  padding: 0.3rem 0.8rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
}
.ov-badge.ok {
  background: #e8f5e9;
  color: #2e7d32;
}
.ov-badge.off {
  background: #ffebee;
  color: #c62828;
}
.overview-actions {
  margin-left: auto;
  display: flex;
  gap: 0.8rem;
  align-items: center;
}

/* ── 空状态 ── */
.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}
.empty-state h3 {
  color: #2c3e50;
  margin-bottom: 0.5rem;
}
.empty-state p {
  color: #9e9e9e;
  margin-bottom: 2rem;
}

/* ── Slot 卡片网格 ── */
.slots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.2rem;
}

.slot-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-left: 4px solid #e0e0e0;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.slot-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}
.slot-card.state-active {
  border-left-color: #4caf50;
}
.slot-card.state-cooling {
  border-left-color: #ff9800;
}
.slot-card.state-expired {
  border-left-color: #ff5722;
}
.slot-card.state-dead {
  border-left-color: #9e9e9e;
  opacity: 0.7;
}

.slot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
}
.slot-id-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.95rem;
}
.slot-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.slot-dot.active {
  background: #4caf50;
  box-shadow: 0 0 6px rgba(76, 175, 80, 0.5);
}
.slot-dot.cooling {
  background: #ff9800;
  animation: pulse-orange 1.5s infinite;
}
.slot-dot.expired {
  background: #ff5722;
}
.slot-dot.dead {
  background: #9e9e9e;
}

@keyframes pulse-orange {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.state-tag {
  font-size: 0.8rem;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-weight: 500;
}
.state-tag.active {
  background: #e8f5e9;
  color: #2e7d32;
}
.state-tag.cooling {
  background: #fff3e0;
  color: #e65100;
}
.state-tag.expired {
  background: #fbe9e7;
  color: #bf360c;
}
.state-tag.dead {
  background: #f5f5f5;
  color: #616161;
}

.slot-label {
  font-size: 1.1rem;
  font-weight: 600;
  color: #37474f;
  margin-bottom: 1rem;
  cursor: default;
}
.slot-label span {
  cursor: pointer;
  border-bottom: 1px dashed transparent;
  transition: border-color 0.2s;
}
.slot-label span:hover {
  border-bottom-color: #bbb;
}
.label-input {
  width: 100%;
  padding: 0.4rem 0.6rem;
  border: 2px solid #1976d2;
  border-radius: 6px;
  font-size: 1rem;
  outline: none;
}

.slot-stats {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 0.35rem 0.6rem;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 0.88rem;
}
.stat-key {
  color: #757575;
}
.stat-val {
  font-weight: 600;
  color: #2c3e50;
}
.stat-val.warn {
  color: #e65100;
}

.slot-actions {
  display: flex;
  gap: 0.6rem;
  padding-top: 0.8rem;
  border-top: 1px solid #f0f0f0;
}

/* ── 按钮样式 ── */
.btn-primary {
  background: linear-gradient(135deg, #1976d2, #1565c0);
  color: white;
  border: none;
  padding: 0.7rem 1.5rem;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-primary:hover {
  background: linear-gradient(135deg, #1565c0, #0d47a1);
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.3);
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-lg {
  padding: 0.9rem 2.5rem;
  font-size: 1.05rem;
}
.btn-full {
  width: 100%;
  margin-top: 1rem;
}

.btn-secondary {
  background: #757575;
  color: white;
  border: none;
  padding: 0.7rem 1.5rem;
  border-radius: 8px;
  font-size: 0.95rem;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-secondary:hover {
  background: #616161;
}

.btn-danger {
  background: #e53935;
  color: white;
  border: none;
  padding: 0.7rem 1.5rem;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-danger:hover {
  background: #c62828;
}

.btn-sm {
  padding: 0.4rem 0.8rem;
  font-size: 0.82rem;
  border-radius: 6px;
}
.btn-outline {
  background: transparent;
  color: #1976d2;
  border: 1px solid #1976d2;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-outline:hover {
  background: #e3f2fd;
}
.btn-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-danger-outline {
  background: transparent;
  color: #e53935;
  border: 1px solid #e53935;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-danger-outline:hover {
  background: #ffebee;
}
.btn-danger-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-icon {
  background: none;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 1.2rem;
  transition: all 0.2s;
}
.btn-icon:hover {
  background: #f5f5f5;
  border-color: #bdbdbd;
}
.btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── 模态框 ── */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-content {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  max-width: 520px;
  width: 92%;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.25s ease-out;
}
@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.modal-sm {
  max-width: 400px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.modal-header h3 {
  margin: 0;
  color: #2c3e50;
}
.modal-close {
  background: none;
  border: none;
  font-size: 1.3rem;
  color: #9e9e9e;
  cursor: pointer;
  padding: 0.3rem;
  line-height: 1;
  border-radius: 50%;
  transition: all 0.2s;
}
.modal-close:hover {
  color: #424242;
  background: #f5f5f5;
}

.modal-actions {
  display: flex;
  gap: 0.8rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.hint-text {
  color: #9e9e9e;
  font-size: 0.88rem;
  margin-top: 0.5rem;
}

/* ── 添加流程 ── */
.add-step {
  text-align: center;
}
.step-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}
.step-desc {
  color: #757575;
  margin-bottom: 1.2rem;
}
.input-field {
  width: 100%;
  padding: 0.8rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 0.95rem;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.input-field:focus {
  outline: none;
  border-color: #1976d2;
}

.step-instructions {
  text-align: left;
}
.instruction-title {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 1.2rem;
  text-align: center;
}

.auth-step-card {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.2rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 10px;
}
.step-num {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #1976d2, #1565c0);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}
.step-body {
  flex: 1;
}
.step-body p {
  margin: 0 0 0.4rem 0;
  color: #757575;
  font-size: 0.9rem;
}
.auth-link {
  color: #1976d2;
  text-decoration: none;
  font-weight: 500;
  word-break: break-all;
}
.auth-link:hover {
  text-decoration: underline;
}

.code-display {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  background: white;
  border: 2px solid #1976d2;
  border-radius: 10px;
  padding: 0.8rem 1.6rem;
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: 0.25em;
  color: #1976d2;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  transition: all 0.2s;
  user-select: all;
}
.code-display:hover {
  background: #e3f2fd;
}
.copy-hint {
  font-size: 0.7rem;
  color: #9e9e9e;
  letter-spacing: normal;
  font-weight: 500;
}

.waiting-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.8rem;
  padding: 1.2rem;
  margin-top: 1.5rem;
  background: #f5f5f5;
  border-radius: 10px;
  color: #757575;
  font-weight: 500;
}
.pulse-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #1976d2;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.5; }
}

.flow-error {
  margin-top: 1rem;
  padding: 0.6rem 1rem;
  background: #fff3e0;
  border-left: 3px solid #ff9800;
  border-radius: 6px;
  color: #e65100;
  font-size: 0.88rem;
  text-align: left;
}

.success-step {
  padding: 2rem 0;
}
.success-icon, .error-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}
.success-step h4 {
  color: #2e7d32;
  font-size: 1.3rem;
  margin-bottom: 0.5rem;
}
.success-step p {
  color: #757575;
}

.error-step {
  padding: 2rem 0;
}
.error-step h4 {
  color: #c62828;
  font-size: 1.3rem;
  margin-bottom: 0.5rem;
}
.error-msg {
  color: #757575;
  margin-bottom: 1.5rem;
  white-space: pre-line;
}
.error-actions {
  display: flex;
  gap: 0.8rem;
  justify-content: center;
}

/* ── 动画 ── */
.spinning {
  display: inline-block;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
