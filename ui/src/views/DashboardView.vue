<template>
  <div class="dashboard">
    <!-- 页面标题 -->
    <div class="dashboard-header">
      <h2>📊 仪表盘</h2>
      <div class="header-actions">
        <span class="last-update" v-if="dashboardStore.lastUpdate">
          最后更新: {{ formatTime(dashboardStore.lastUpdate) }}
        </span>
        <button class="refresh-btn" @click="handleRefresh" :disabled="dashboardStore.loading">
          <span :class="{ 'spinning': dashboardStore.loading }">🔄</span>
          刷新
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="dashboardStore.loading && !dashboardStore.stats" class="loading-container">
      <div class="loading-spinner"></div>
      <p>加载中...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="dashboardStore.error" class="error-container">
      <span class="error-icon">⚠️</span>
      <p>{{ dashboardStore.error }}</p>
      <button @click="handleRefresh">重试</button>
    </div>

    <!-- 仪表盘内容 -->
    <div v-else-if="dashboardStore.stats" class="dashboard-content">
      <!-- 顶部概览卡片 -->
      <section class="overview-section">
        <div class="overview-card agent-status" :class="dashboardStore.agentStatusClass">
          <div class="card-icon">🤖</div>
          <div class="card-content">
            <div class="card-title">Agent 状态</div>
            <div class="card-value">{{ dashboardStore.agentStatusText }}</div>
            <div class="card-sub">{{ dashboardStore.stats.agent.uptime_formatted }}</div>
          </div>
          <div class="status-indicator"></div>
        </div>

        <div class="overview-card model-info">
          <div class="card-icon">🧠</div>
          <div class="card-content">
            <div class="card-title">当前模型</div>
            <div class="card-value">{{ dashboardStore.stats.agent.current_model }}</div>
            <div class="card-sub">消息: {{ dashboardStore.stats.agent.total_messages }}</div>
          </div>
        </div>

        <div class="overview-card health-status" :class="dashboardStore.healthStatusClass">
          <div class="card-icon">💚</div>
          <div class="card-content">
            <div class="card-title">系统健康</div>
            <div class="card-value">{{ dashboardStore.healthStatusText }}</div>
            <div class="card-sub" v-if="dashboardStore.health">
              {{ Object.values(dashboardStore.health.components).filter(c => c === 'ok').length }}/{{ Object.keys(dashboardStore.health.components).length }} 组件正常
            </div>
          </div>
        </div>

        <div class="overview-card token-pool">
          <div class="card-icon">🎫</div>
          <div class="card-content">
            <div class="card-title">Token 池</div>
            <div class="card-value">{{ dashboardStore.stats.tokens.available_slots }}/{{ dashboardStore.stats.tokens.pool_size }}</div>
            <div class="card-sub">可用槽位</div>
          </div>
          <div class="token-bar">
            <div class="token-fill" :style="{ width: tokenPoolPercent + '%' }"></div>
          </div>
        </div>
      </section>

      <!-- 主内容区 -->
      <div class="main-content">
        <!-- 左侧列 -->
        <div class="left-column">
          <!-- 项目统计 -->
          <section class="card projects-section">
            <div class="section-header">
              <h3>📁 项目管理</h3>
              <span class="badge">{{ dashboardStore.stats.projects.total }} 个项目</span>
            </div>
            <div class="projects-list" v-if="dashboardStore.stats.projects.recent.length">
              <div 
                v-for="project in dashboardStore.stats.projects.recent" 
                :key="project.id" 
                class="project-item"
              >
                <div class="project-icon">{{ project.type === 'git' ? '🔗' : '📂' }}</div>
                <div class="project-info">
                  <div class="project-name">{{ project.name }}</div>
                  <div class="project-path">{{ truncatePath(project.path) }}</div>
                </div>
                <div class="project-meta">
                  <span class="project-type">{{ project.type }}</span>
                </div>
              </div>
            </div>
            <div v-else class="empty-state">
              <span>暂无项目</span>
            </div>
          </section>

          <!-- Agent 分布 -->
          <section class="card agents-section">
            <div class="section-header">
              <h3>🤖 Agent 分布</h3>
              <span class="badge">{{ dashboardStore.stats.agents.total }} 个</span>
            </div>
            <div class="agents-grid">
              <div class="agent-stat preset">
                <div class="stat-value">{{ dashboardStore.stats.agents.presets }}</div>
                <div class="stat-label">预设 Agent</div>
              </div>
              <div class="agent-stat custom">
                <div class="stat-value">{{ dashboardStore.stats.agents.custom }}</div>
                <div class="stat-label">自定义 Agent</div>
              </div>
            </div>
            <div class="domain-chart" v-if="Object.keys(dashboardStore.stats.agents.by_domain).length">
              <div class="chart-title">按领域分布</div>
              <div class="domain-bars">
                <div 
                  v-for="(count, domain) in dashboardStore.stats.agents.by_domain" 
                  :key="domain"
                  class="domain-bar"
                >
                  <span class="domain-name">{{ domain }}</span>
                  <div class="bar-container">
                    <div class="bar-fill" :style="{ width: (count / dashboardStore.stats.agents.total * 100) + '%' }"></div>
                  </div>
                  <span class="domain-count">{{ count }}</span>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- 右侧列 -->
        <div class="right-column">
          <!-- 技能状态 -->
          <section class="card skills-section">
            <div class="section-header">
              <h3>⚡ 技能状态</h3>
              <span class="badge">{{ dashboardStore.stats.skills.enabled }}/{{ dashboardStore.stats.skills.total }} 启用</span>
            </div>
            <div class="skills-grid">
              <div 
                v-for="skill in dashboardStore.stats.skills.list" 
                :key="skill.name"
                class="skill-item"
                :class="{ enabled: skill.enabled }"
              >
                <div class="skill-status">
                  <span class="status-dot" :class="{ active: skill.enabled }"></span>
                </div>
                <div class="skill-info">
                  <div class="skill-name">{{ skill.name }}</div>
                  <div class="skill-desc">{{ skill.description }}</div>
                </div>
              </div>
            </div>
          </section>

          <!-- 系统信息 -->
          <section class="card system-section">
            <div class="section-header">
              <h3>💻 系统信息</h3>
            </div>
            <div class="system-info">
              <div class="info-row">
                <span class="info-label">版本</span>
                <span class="info-value">{{ dashboardStore.stats.system.version }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Python</span>
                <span class="info-value">{{ dashboardStore.stats.system.python_version }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">平台</span>
                <span class="info-value">{{ truncateText(dashboardStore.stats.system.platform, 30) }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">配置</span>
                <span class="info-value path">{{ truncatePath(dashboardStore.stats.system.config_path) }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">工作目录</span>
                <span class="info-value path">{{ truncatePath(dashboardStore.stats.system.workspace_path) }}</span>
              </div>
            </div>
            
            <!-- 组件健康状态 -->
            <div class="components-health" v-if="dashboardStore.health">
              <div class="health-title">组件状态</div>
              <div class="health-items">
                <div 
                  v-for="(status, name) in dashboardStore.health.components" 
                  :key="name"
                  class="health-item"
                >
                  <span class="health-dot" :class="status"></span>
                  <span class="health-name">{{ formatComponentName(name) }}</span>
                  <span class="health-status">{{ formatHealthStatus(status) }}</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <!-- 统计概览底部 -->
      <section class="stats-footer">
        <div class="stat-item">
          <div class="stat-icon">📊</div>
          <div class="stat-content">
            <div class="stat-number">{{ formatNumber(dashboardStore.stats.tokens.total_used) }}</div>
            <div class="stat-label">Token 使用</div>
          </div>
        </div>
        <div class="stat-item">
          <div class="stat-icon">📨</div>
          <div class="stat-content">
            <div class="stat-number">{{ formatNumber(dashboardStore.stats.tokens.requests_today) }}</div>
            <div class="stat-label">今日请求</div>
          </div>
        </div>
        <div class="stat-item">
          <div class="stat-icon">📁</div>
          <div class="stat-content">
            <div class="stat-number">{{ dashboardStore.stats.projects.total }}</div>
            <div class="stat-label">项目总数</div>
          </div>
        </div>
        <div class="stat-item">
          <div class="stat-icon">🤖</div>
          <div class="stat-content">
            <div class="stat-number">{{ dashboardStore.stats.agents.total }}</div>
            <div class="stat-label">Agent 总数</div>
          </div>
        </div>
        <div class="stat-item">
          <div class="stat-icon">⚡</div>
          <div class="stat-content">
            <div class="stat-number">{{ dashboardStore.stats.skills.enabled }}</div>
            <div class="stat-label">启用技能</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'

const dashboardStore = useDashboardStore()

// Token 池百分比
const tokenPoolPercent = computed(() => {
  if (!dashboardStore.stats) return 0
  const { available_slots, pool_size } = dashboardStore.stats.tokens
  if (pool_size === 0) return 0
  return Math.round((available_slots / pool_size) * 100)
})

// 刷新数据
async function handleRefresh() {
  await dashboardStore.refresh()
}

// 格式化时间
function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// 截断路径
function truncatePath(path: string): string {
  if (path.length <= 40) return path
  return '...' + path.slice(-37)
}

// 截断文本
function truncateText(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}

// 格式化数字
function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

// 格式化组件名称
function formatComponentName(name: string): string {
  const names: Record<string, string> = {
    'agent_loop': 'Agent 循环',
    'provider': '模型提供者',
    'token_pool': 'Token 池'
  }
  return names[name] || name
}

// 格式化健康状态
function formatHealthStatus(status: string): string {
  const statuses: Record<string, string> = {
    'ok': '正常',
    'degraded': '降级',
    'error': '错误',
    'unknown': '未知',
    'not_started': '未启动'
  }
  return statuses[status] || status
}

// 自动刷新定时器
let refreshInterval: number | null = null

onMounted(async () => {
  await dashboardStore.refresh()
  // 每 30 秒自动刷新
  refreshInterval = window.setInterval(() => {
    dashboardStore.refresh()
  }, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.dashboard {
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

/* 页面标题 */
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.dashboard-header h2 {
  margin: 0;
  color: #1a1a2e;
  font-size: 1.5rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.last-update {
  color: #666;
  font-size: 0.85rem;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: #f5f5f5;
  border-color: #ccc;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinning {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 加载和错误状态 */
.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #f0f0f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 1rem;
}

.error-container {
  color: #e74c3c;
}

.error-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.error-container button {
  margin-top: 1rem;
  padding: 0.5rem 1.5rem;
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

/* 概览卡片区域 */
.overview-section {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.overview-card {
  background: white;
  border-radius: 12px;
  padding: 1.25rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  gap: 1rem;
  position: relative;
  overflow: hidden;
}

.card-icon {
  font-size: 2rem;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #f8f9fa;
}

.card-content {
  flex: 1;
}

.card-title {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 0.25rem;
}

.card-value {
  font-size: 1.3rem;
  font-weight: 700;
  color: #1a1a2e;
}

.card-sub {
  font-size: 0.75rem;
  color: #888;
  margin-top: 0.25rem;
}

/* Agent 状态卡片 */
.agent-status.idle {
  border-left: 4px solid #27ae60;
}

.agent-status.idle .status-indicator {
  background: #27ae60;
}

.agent-status.thinking {
  border-left: 4px solid #f39c12;
}

.agent-status.thinking .status-indicator {
  background: #f39c12;
  animation: pulse 1.5s ease-in-out infinite;
}

.agent-status.error {
  border-left: 4px solid #e74c3c;
}

.agent-status.error .status-indicator {
  background: #e74c3c;
}

.agent-status.offline {
  border-left: 4px solid #95a5a6;
}

.agent-status.offline .status-indicator {
  background: #95a5a6;
}

.status-indicator {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 4px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 健康状态卡片 */
.health-status.healthy {
  border-left: 4px solid #27ae60;
}

.health-status.degraded {
  border-left: 4px solid #f39c12;
}

.health-status.unhealthy {
  border-left: 4px solid #e74c3c;
}

/* Token 池卡片 */
.token-pool {
  flex-direction: column;
  align-items: stretch;
}

.token-pool .card-icon {
  position: absolute;
  right: 1rem;
  top: 1rem;
  width: 36px;
  height: 36px;
  font-size: 1.5rem;
}

.token-bar {
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  margin-top: 0.5rem;
  overflow: hidden;
}

.token-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* 主内容区 */
.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

/* 卡片通用样式 */
.card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  padding: 1.25rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #f0f0f0;
}

.section-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #1a1a2e;
}

.badge {
  background: #f0f0f0;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  color: #666;
}

/* 项目列表 */
.projects-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.project-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: #f8f9fa;
  border-radius: 8px;
  transition: background 0.2s;
}

.project-item:hover {
  background: #f0f0f0;
}

.project-icon {
  font-size: 1.25rem;
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-name {
  font-weight: 600;
  color: #1a1a2e;
  font-size: 0.9rem;
}

.project-path {
  font-size: 0.75rem;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-meta {
  display: flex;
  align-items: center;
}

.project-type {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  background: #e8e8e8;
  border-radius: 4px;
  color: #666;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #999;
}

/* Agent 分布 */
.agents-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.agent-stat {
  text-align: center;
  padding: 1rem;
  border-radius: 8px;
}

.agent-stat.preset {
  background: linear-gradient(135deg, #667eea20, #764ba220);
  border: 1px solid #667eea40;
}

.agent-stat.custom {
  background: linear-gradient(135deg, #f093fb20, #f5576c20);
  border: 1px solid #f5576c40;
}

.agent-stat .stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1a1a2e;
}

.agent-stat .stat-label {
  font-size: 0.75rem;
  color: #666;
  margin-top: 0.25rem;
}

.domain-chart {
  margin-top: 0.5rem;
}

.chart-title {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.domain-bars {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.domain-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.domain-name {
  width: 60px;
  font-size: 0.75rem;
  color: #666;
}

.bar-container {
  flex: 1;
  height: 8px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.domain-count {
  width: 20px;
  font-size: 0.75rem;
  color: #666;
  text-align: right;
}

/* 技能列表 */
.skills-grid {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
}

.skill-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  background: #f8f9fa;
  border-radius: 8px;
  opacity: 0.5;
}

.skill-item.enabled {
  opacity: 1;
}

.skill-status {
  flex-shrink: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  display: block;
}

.status-dot.active {
  background: #27ae60;
  box-shadow: 0 0 6px #27ae6060;
}

.skill-info {
  flex: 1;
  min-width: 0;
}

.skill-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: #1a1a2e;
}

.skill-desc {
  font-size: 0.7rem;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 系统信息 */
.system-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #f5f5f5;
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 0.8rem;
  color: #666;
}

.info-value {
  font-size: 0.8rem;
  color: #1a1a2e;
  font-weight: 500;
}

.info-value.path {
  font-family: monospace;
  font-size: 0.75rem;
  color: #666;
}

/* 组件健康状态 */
.components-health {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #f0f0f0;
}

.health-title {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 0.75rem;
}

.health-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.health-dot.ok {
  background: #27ae60;
}

.health-dot.degraded {
  background: #f39c12;
}

.health-dot.error {
  background: #e74c3c;
}

.health-dot.unknown,
.health-dot.not_started {
  background: #95a5a6;
}

.health-name {
  flex: 1;
  font-size: 0.8rem;
  color: #1a1a2e;
}

.health-status {
  font-size: 0.75rem;
  color: #666;
}

/* 统计底部 */
.stats-footer {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1rem;
}

.stat-item {
  background: white;
  border-radius: 12px;
  padding: 1rem 1.25rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.stat-item .stat-icon {
  font-size: 1.5rem;
}

.stat-item .stat-number {
  font-size: 1.25rem;
  font-weight: 700;
  color: #1a1a2e;
}

.stat-item .stat-label {
  font-size: 0.75rem;
  color: #666;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .overview-section {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .stats-footer {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  
  .stats-footer {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .overview-section {
    grid-template-columns: 1fr;
  }
  
  .stats-footer {
    grid-template-columns: 1fr;
  }
  
  .dashboard-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }
}
</style>
