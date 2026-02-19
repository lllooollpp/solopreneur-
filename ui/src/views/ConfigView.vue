<template>
  <div class="config">
    <h2>⚙️ 配置管理</h2>
    
    <!-- 技能配置区域 -->
    <div class="config-section">
      <div class="section-header">
        <h3>🔧 技能列表</h3>
        <button class="btn-add" @click="openCreateSkill">＋ 新建技能</button>
      </div>
      <div v-if="skillsStore.loading" class="loading">加载中...</div>
      <div v-else-if="skillsStore.skills.length === 0" class="empty">
        <p>暂无技能配置</p>
      </div>
      <div v-else class="skills-grid">
        <div
          v-for="skill in skillsStore.skills"
          :key="skill.name"
          class="skill-card"
        >
          <div class="skill-header">
            <span class="skill-name">{{ skill.name }}</span>
            <label class="switch">
              <input
                type="checkbox"
                :checked="skill.enabled"
                @change="toggleSkill(skill.name)"
              />
              <span class="slider"></span>
            </label>
          </div>
          <p class="skill-description">{{ skill.description }}</p>
          <div class="skill-meta">
            <span :class="['source-tag', skill.source]">
              {{ sourceText(skill.source) }}
            </span>
            <span v-if="skill.overridden" class="overridden-tag">已重写</span>
          </div>
          <div class="skill-actions">
            <button class="btn-action btn-edit" @click="openEditSkill(skill.name)">编辑</button>
            <button
              class="btn-action btn-delete"
              @click="confirmDeleteSkill(skill.name, skill.source)"
              :disabled="skill.source === 'bundled' && !skill.overridden"
              :title="skill.source === 'bundled' && !skill.overridden ? '内置技能不可删除' : '删除技能'"
            >删除</button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Agents 管理区域 -->
    <div class="config-section">
      <h3>🤖 Agents 管理</h3>
      <AgentsManager />
    </div>

    <!-- LLM Providers 配置区域 -->
    <div class="config-section">
      <ProviderConfig />
    </div>

    <!-- 记忆搜索引擎配置 -->
    <div class="config-section">
      <MemorySearchConfig />
    </div>

    <!-- GitHub Copilot 认证区域 -->
    <div class="config-section">
      <h3>🔐 GitHub Copilot 认证</h3>
      <div class="copilot-auth">
        <div v-if="copilotAuth.loading" class="auth-status">
          <span class="spinner">⏳</span>
          <p>正在检查认证状态...</p>
        </div>
        
        <div v-else-if="copilotAuth.authenticated" class="auth-status authenticated">
          <span class="status-icon">✅</span>
          <div class="auth-info">
            <p class="auth-text">已认证 ({{ copilotAuth.activeCount }}/{{ copilotAuth.totalCount }} 账号可用)</p>
            <p v-if="copilotAuth.expiresAt" class="auth-detail">
              最近过期时间: {{ formatExpiry(copilotAuth.expiresAt) }}
            </p>
          </div>
          <router-link to="/accounts" class="btn-primary">管理账号池</router-link>
        </div>
        
        <div v-else class="auth-status">
          <span class="status-icon">❌</span>
          <p class="auth-text">未认证</p>
          <router-link to="/accounts" class="btn-primary">前往登录</router-link>
        </div>
        
        <div v-if="copilotAuth.error" class="auth-error">
          ⚠️ {{ copilotAuth.error }}
        </div>
      </div>
    </div>

    <!-- 技能编辑器模态框 -->
    <SkillEditor
      v-if="showSkillEditor"
      :is-create="skillEditorMode === 'create'"
      :skill-name="editingSkillName"
      :initial-content="editingSkillContent"
      @close="closeSkillEditor"
      @save="handleSkillSave"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { useSkillsStore } from '@/stores/skills'
import { SkillSource } from '@/types/skill'
import { getAuthStatus } from '@/api/auth'
import AgentsManager from '@/components/AgentsManager.vue'
import ProviderConfig from '@/components/ProviderConfig.vue'
import MemorySearchConfig from '@/components/MemorySearchConfig.vue'
import SkillEditor from '@/components/SkillEditor.vue'

const skillsStore = useSkillsStore()

// Copilot 认证状态
const copilotAuth = reactive({
  authenticated: false,
  expiresAt: null as string | null,
  activeCount: 0,
  totalCount: 0,
  loading: false,
  error: null as string | null,
})

function sourceText(source: SkillSource): string {
  switch (source) {
    case SkillSource.WORKSPACE: return 'Workspace'
    case SkillSource.MANAGED: return 'Managed'
    case SkillSource.BUNDLED: return 'Bundled'
    default: return source
  }
}

function toggleSkill(name: string) {
  skillsStore.toggleSkill(name)
}

// ====== Skill CRUD ======
const showSkillEditor = ref(false)
const skillEditorMode = ref<'create' | 'edit'>('create')
const editingSkillName = ref('')
const editingSkillContent = ref('')

function openCreateSkill() {
  skillEditorMode.value = 'create'
  editingSkillName.value = ''
  editingSkillContent.value = ''
  showSkillEditor.value = true
}

async function openEditSkill(name: string) {
  skillEditorMode.value = 'edit'
  editingSkillName.value = name
  try {
    editingSkillContent.value = await skillsStore.getSkillContent(name)
  } catch {
    editingSkillContent.value = ''
  }
  showSkillEditor.value = true
}

function closeSkillEditor() {
  showSkillEditor.value = false
}

async function handleSkillSave(payload: { name: string; description: string; content: string }) {
  try {
    if (skillEditorMode.value === 'create') {
      await skillsStore.createSkill({
        name: payload.name,
        description: payload.description,
        content: payload.content,
      })
      alert('✅ 技能已创建')
    } else {
      await skillsStore.updateSkillContent(payload.name, payload.content)
      alert('✅ 技能已更新')
    }
    showSkillEditor.value = false
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error.message || '操作失败'
    alert(`❌ ${msg}`)
  }
}

async function confirmDeleteSkill(name: string, source: string) {
  if (source === 'bundled') {
    alert('内置技能不可删除')
    return
  }
  const confirmed = confirm(`确定要删除技能 "${name}" 吗？此操作不可恢复。`)
  if (!confirmed) return
  try {
    await skillsStore.deleteSkill(name)
    alert('✅ 技能已删除')
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error.message || '删除失败'
    alert(`❌ ${msg}`)
  }
}

function formatExpiry(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function checkAuthStatus() {
  copilotAuth.loading = true
  copilotAuth.error = null
  
  try {
    const status = await getAuthStatus()
    copilotAuth.authenticated = status.authenticated
    copilotAuth.expiresAt = status.expiresAt
    // 从扩展的 status 中获取池信息
    copilotAuth.activeCount = (status as any).active_count ?? 0
    copilotAuth.totalCount = (status as any).total_count ?? 0
  } catch (error: any) {
    copilotAuth.error = error.message || '检查认证状态失败'
  } finally {
    copilotAuth.loading = false
  }
}

onMounted(() => {
  skillsStore.loadSkills()
  checkAuthStatus()
})
</script>

<style scoped>
.config {
  padding: 2rem;
  max-width: 1200px;
}

h2 {
  margin-bottom: 1.5rem;
  color: #2c3e50;
}

.config-section {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.config-section h3 {
  margin-bottom: 1rem;
  color: #2c3e50;
}

.loading,
.empty {
  text-align: center;
  padding: 2rem;
  color: #9e9e9e;
}

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.skill-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 1rem;
  transition: box-shadow 0.2s;
}

.skill-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h3 {
  margin-bottom: 0;
}

.btn-add {
  background: #4caf50;
  color: white;
  border: none;
  padding: 0.5rem 1.2rem;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-add:hover {
  background: #388e3c;
}

.skill-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.8rem;
  padding-top: 0.8rem;
  border-top: 1px solid #f0f0f0;
}

.btn-action {
  padding: 0.3rem 0.8rem;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  border: 1px solid #e0e0e0;
  transition: all 0.2s;
}

.btn-edit {
  background: #e3f2fd;
  color: #1976d2;
  border-color: #bbdefb;
}

.btn-edit:hover {
  background: #bbdefb;
}

.btn-delete {
  background: #ffebee;
  color: #c62828;
  border-color: #ffcdd2;
}

.btn-delete:hover:not(:disabled) {
  background: #ffcdd2;
}

.btn-delete:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.skill-name {
  font-weight: 600;
  color: #2c3e50;
}

.switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 24px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: 0.3s;
  border-radius: 24px;
}

.slider:before {
  position: absolute;
  content: '';
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}

input:checked + .slider {
  background-color: #4caf50;
}

input:checked + .slider:before {
  transform: translateX(24px);
}

.skill-description {
  font-size: 0.9rem;
  color: #616161;
  margin-bottom: 0.8rem;
}

.skill-meta {
  display: flex;
  gap: 0.5rem;
}

.source-tag,
.overridden-tag {
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
}

.source-tag.workspace {
  background: #e3f2fd;
  color: #1976d2;
}

.source-tag.managed {
  background: #f3e5f5;
  color: #7b1fa2;
}

.source-tag.bundled {
  background: #e8f5e9;
  color: #388e3c;
}

.overridden-tag {
  background: #fff3e0;
  color: #f57c00;
}

.btn-primary {
  background: #1976d2;
  color: white;
  border: none;
  padding: 0.8rem 2rem;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.2s;
  text-decoration: none;
  display: inline-block;
}

.btn-primary:hover {
  background: #1565c0;
}

.hint {
  margin-top: 1rem;
  color: #9e9e9e;
  font-size: 0.9rem;
}

/* Copilot 认证样式 */
.copilot-auth {
  padding: 1rem;
}

.auth-status {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  background: #fafafa;
}

.auth-status.authenticated {
  border-color: #4caf50;
  background: #f1f8f4;
}

.status-icon {
  font-size: 2rem;
}

.auth-info {
  flex: 1;
}

.auth-text {
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.auth-detail {
  font-size: 0.9rem;
  color: #616161;
  margin: 0.3rem 0 0 0;
}

.auth-error {
  margin-top: 1rem;
  padding: 0.8rem;
  background: #ffebee;
  border-left: 4px solid #f44336;
  border-radius: 4px;
  color: #c62828;
}

.spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
