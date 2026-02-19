<template>
  <div class="agents-manager">
    <div class="agents-header">
      <div class="agents-actions">
        <button class="btn-primary" @click="showCreateModal = true">
          <span class="icon">+</span> 创建 Agent
        </button>
        <button class="btn-secondary" @click="reloadAgents" :disabled="loading">
          <span class="icon">↻</span> 重载
        </button>
      </div>
      <div class="agents-filter">
        <select v-model="filterDomain" class="filter-select">
          <option value="">所有领域</option>
          <option value="software">软件工程</option>
          <option value="medical">医疗</option>
          <option value="legal">法律</option>
          <option value="general">通用</option>
          <option value="custom">自定义</option>
        </select>
        <select v-model="filterSource" class="filter-select">
          <option value="">所有来源</option>
          <option value="preset">预设</option>
          <option value="custom">自定义</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="filteredAgents.length === 0" class="empty">
      <p>暂无 Agent 配置</p>
    </div>
    <div v-else class="agents-grid">
      <div
        v-for="agent in filteredAgents"
        :key="agent.name"
        class="agent-card"
        :class="{ custom: agent.source === 'custom' }"
      >
        <div class="agent-header">
          <span class="agent-emoji">{{ agent.emoji }}</span>
          <div class="agent-title">
            <h4>{{ agent.title }}</h4>
            <span class="agent-name">{{ agent.name }}</span>
          </div>
          <div class="agent-badges">
            <span :class="['badge', 'source', agent.source]">
              {{ agent.source === 'preset' ? '预设' : '自定义' }}
            </span>
            <span class="badge domain">{{ agent.domain }}</span>
          </div>
        </div>
        <p class="agent-description">{{ agent.description }}</p>
        <div class="agent-footer">
          <span class="agent-type">{{ agent.type }}</span>
          <div class="agent-actions">
            <button class="btn-icon" @click="viewDetail(agent.name)" title="查看详情">
              👁
            </button>
            <button 
              class="btn-icon" 
              @click="editAgent(agent)"
              title="编辑"
            >
              ✏️
            </button>
            <button 
              v-if="agent.source === 'custom'"
              class="btn-icon danger" 
              @click="deleteAgent(agent.name)"
              title="删除"
            >
              🗑
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建 Agent 模态框 -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>创建新 Agent</h3>
          <button class="btn-close" @click="showCreateModal = false">×</button>
        </div>
        <form @submit.prevent="createAgent" class="create-form">
          <div class="form-group">
            <label>名称 (英文标识) *</label>
            <input 
              v-model="newAgent.name" 
              required
              pattern="[a-zA-Z0-9_\-]+"
              placeholder="例如: pediatrician"
            />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>标题 *</label>
              <input v-model="newAgent.title" required placeholder="例如: 儿科医生" />
            </div>
            <div class="form-group small">
              <label>Emoji</label>
              <div class="emoji-picker-wrapper" @click.stop>
                <button type="button" class="emoji-trigger" @click.stop="showEmojiPicker = showEmojiPicker === 'create' ? '' : 'create'">
                  {{ newAgent.emoji || '🤖' }}
                </button>
                <div v-if="showEmojiPicker === 'create'" class="emoji-grid">
                  <span
                    v-for="e in EMOJI_LIST" :key="e"
                    class="emoji-option"
                    @click="newAgent.emoji = e; showEmojiPicker = ''"
                  >{{ e }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label>描述</label>
            <input v-model="newAgent.description" placeholder="简要描述 Agent 的用途" />
          </div>
          <div class="form-group">
            <label>System Prompt *</label>
            <textarea 
              v-model="newAgent.system_prompt" 
              required
              rows="8"
              placeholder="定义 Agent 的行为和职责..."
            ></textarea>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>类型</label>
              <select v-model="newAgent.type">
                <option value="subagent">子 Agent</option>
                <option value="master">主 Agent</option>
                <option value="standalone">独立 Agent</option>
              </select>
            </div>
            <div class="form-group">
              <label>最大迭代次数</label>
              <input v-model.number="newAgent.max_iterations" type="number" min="1" max="100" />
            </div>
          </div>
          <div class="form-group">
            <label>技能</label>
            <div class="skills-checklist">
              <label v-for="skill in availableSkills" :key="skill.name" class="skill-item">
                <input
                  class="skill-checkbox"
                  type="checkbox"
                  :checked="isSkillSelected(newAgent.skills, skill.name)"
                  @change="toggleSkill('new', skill.name, ($event.target as HTMLInputElement).checked)"
                />
                <div class="skill-meta">
                  <div class="skill-main">
                    <span class="skill-name">{{ skill.name }}</span>
                    <span class="skill-source">{{ skill.source }}</span>
                  </div>
                  <span class="skill-desc">{{ skill.description }}</span>
                </div>
              </label>
              <div v-if="!availableSkills.length" class="pick-empty">暂无可用技能</div>
            </div>
          </div>
          <div v-if="isCopilotGlobal" class="form-group">
            <label>专用模型 <span class="label-hint">(不选则使用全局默认)</span></label>
            <select v-model="newAgent.model" class="model-select">
              <option :value="null">— 使用全局默认 —</option>
              <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
              <option v-if="!availableModels.length" :value="null" disabled>未获取到 Copilot 模型，请先登录 Copilot</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="button" class="btn-secondary" @click="showCreateModal = false">
              取消
            </button>
            <button type="submit" class="btn-primary" :disabled="creating">
              {{ creating ? '创建中...' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- 详情模态框 -->
    <div v-if="showDetailModal && selectedAgent" class="modal-overlay" @click.self="closeDetail">
      <div class="modal-content detail-modal">
        <div class="modal-header">
          <h3>{{ selectedAgent.emoji }} {{ selectedAgent.title }}</h3>
          <button class="btn-close" @click="closeDetail">×</button>
        </div>
        <div class="detail-content">
          <div class="detail-section">
            <label>名称:</label>
            <code>{{ selectedAgent.name }}</code>
          </div>
          <div class="detail-section">
            <label>类型:</label>
            <span>{{ selectedAgent.type }}</span>
          </div>
          <div class="detail-section">
            <label>来源:</label>
            <span :class="['badge', selectedAgent.source]">
              {{ selectedAgent.source === 'preset' ? '预设' : '自定义' }}
            </span>
          </div>
          <div class="detail-section">
            <label>System Prompt:</label>
            <pre class="prompt-preview">{{ selectedAgent.system_prompt }}</pre>
          </div>
          <div v-if="selectedAgent.skills?.length" class="detail-section">
            <label>技能:</label>
            <div class="tags">
              <span v-for="skill in selectedAgent.skills" :key="skill" class="tag">{{ skill }}</span>
            </div>
          </div>
          <div v-if="selectedAgent.tools?.length" class="detail-section">
            <label>工具:</label>
            <div class="tags">
              <span v-for="tool in selectedAgent.tools" :key="tool" class="tag">{{ tool }}</span>
            </div>
          </div>
          <div v-if="isCopilotGlobal" class="detail-section">
            <label>专用模型:</label>
            <span v-if="selectedAgent.model" class="model-badge">{{ selectedAgent.model }}</span>
            <span v-else class="model-default">跟随全局默认</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑 Agent 模态框 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>编辑 Agent</h3>
          <button class="btn-close" @click="showEditModal = false">×</button>
        </div>
        <form @submit.prevent="updateAgent" class="create-form">
          <div class="form-row">
            <div class="form-group">
              <label>标题</label>
              <input v-model="editingAgent.title" placeholder="例如: 儿科医生" />
            </div>
            <div class="form-group small">
              <label>Emoji</label>
              <div class="emoji-picker-wrapper" @click.stop>
                <button type="button" class="emoji-trigger" @click.stop="showEmojiPicker = showEmojiPicker === 'edit' ? '' : 'edit'">
                  {{ editingAgent.emoji || '🤖' }}
                </button>
                <div v-if="showEmojiPicker === 'edit'" class="emoji-grid">
                  <span
                    v-for="e in EMOJI_LIST" :key="e"
                    class="emoji-option"
                    @click="editingAgent.emoji = e; showEmojiPicker = ''"
                  >{{ e }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label>描述</label>
            <input v-model="editingAgent.description" placeholder="简要描述 Agent 的用途" />
          </div>
          <div class="form-group">
            <label>System Prompt</label>
            <textarea 
              v-model="editingAgent.system_prompt" 
              rows="8"
              placeholder="定义 Agent 的行为和职责..."
            ></textarea>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>类型</label>
              <select v-model="editingAgent.type">
                <option value="subagent">子 Agent</option>
                <option value="master">主 Agent</option>
                <option value="standalone">独立 Agent</option>
              </select>
            </div>
            <div class="form-group">
              <label>最大迭代次数</label>
              <input v-model.number="editingAgent.max_iterations" type="number" min="1" max="100" />
            </div>
          </div>
          <div class="form-group">
            <label>技能</label>
            <div class="skills-checklist">
              <label v-for="skill in availableSkills" :key="skill.name" class="skill-item">
                <input
                  class="skill-checkbox"
                  type="checkbox"
                  :checked="isSkillSelected(editingAgent.skills, skill.name)"
                  @change="toggleSkill('edit', skill.name, ($event.target as HTMLInputElement).checked)"
                />
                <div class="skill-meta">
                  <div class="skill-main">
                    <span class="skill-name">{{ skill.name }}</span>
                    <span class="skill-source">{{ skill.source }}</span>
                  </div>
                  <span class="skill-desc">{{ skill.description }}</span>
                </div>
              </label>
              <div v-if="!availableSkills.length" class="pick-empty">暂无可用技能</div>
            </div>
          </div>
          <div v-if="isCopilotGlobal" class="form-group">
            <label>专用模型 <span class="label-hint">(不选则使用全局默认)</span></label>
            <select v-model="editingAgent.model" class="model-select">
              <option :value="null">— 使用全局默认 —</option>
              <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
              <option v-if="!availableModels.length" :value="null" disabled>未获取到 Copilot 模型，请先登录 Copilot</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="button" class="btn-secondary" @click="showEditModal = false">
              取消
            </button>
            <button type="submit" class="btn-primary" :disabled="editing">
              {{ editing ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAgentsStore, type CreateAgentRequest } from '@/stores/agents'
import { apiClient } from '@/api/client'

const EMOJI_LIST = [
  '🤖','👨‍💻','👩‍💻','🧑‍🔬','👩‍⚕️','👨‍⚕️','🧑‍🏫','🧑‍💼','👮','🕵️',
  '⚙️','🔧','🛠️','🔨','📝','📋','📊','🗂️','🚀','⚡',
  '🔍','💡','✅','🎯','🌐','🏗️','🔐','🛡️','📡','🧩',
  '🦊','🦁','🐉','🦅','🐺','🌟','💫','🔮','🌈','🎨',
]

const agentsStore = useAgentsStore()

// State
const loading = computed(() => agentsStore.loading)
const filterDomain = ref('')
const filterSource = ref('')
const showCreateModal = ref(false)
const showDetailModal = ref(false)
const showEditModal = ref(false)
const showEmojiPicker = ref<'create' | 'edit' | ''>('')
const availableModels = ref<string[]>([])
const availableSkills = ref<{name: string, description: string, source: string}[]>([])
const isCopilotGlobal = ref(false)
const selectedAgent = computed(() => agentsStore.currentAgent)
const creating = ref(false)
const editing = ref(false)
const editingAgent = ref<Partial<CreateAgentRequest>>({})
const editingAgentName = ref('')

const newAgent = ref<CreateAgentRequest>({
  name: '',
  title: '',
  emoji: '🤖',
  description: '',
  system_prompt: '',
  type: 'subagent',
  skills: [],
  max_iterations: 15,
  model: null,
})

// Computed
const filteredAgents = computed(() => {
  let agents = agentsStore.agents
  if (filterDomain.value) {
    agents = agents.filter(a => a.domain === filterDomain.value || 
      (filterDomain.value === 'custom' && a.source === 'custom'))
  }
  if (filterSource.value) {
    agents = agents.filter(a => a.source === filterSource.value)
  }
  return agents
})

// Methods
async function loadModels() {
  try {
    if (!isCopilotGlobal.value) {
      availableModels.value = []
      return
    }

    const res = await apiClient.get('/api/auth/copilot-models')
    availableModels.value = res.models || []

    if (!availableModels.value.length) {
      const fallback = await apiClient.get('/api/auth/models')
      availableModels.value = fallback.models || []
    }
  } catch (e) {
    console.error('Failed to load models:', e)
  }
}

async function loadProviderMode() {
  try {
    const cfg = await apiClient.get('/api/config/providers')
    isCopilotGlobal.value = !!cfg.copilot_priority
  } catch (e) {
    console.error('Failed to load provider mode:', e)
    isCopilotGlobal.value = false
  }
}

async function loadSkills() {
  try {
    const res = await apiClient.get('/api/config/skills')
    availableSkills.value = (res.skills || []).map((s: any) => ({
      name: String(s.name || '').trim(),
      description: s.description || s.name,
      source: s.source || 'unknown',
    }))
  } catch (e) {
    console.error('Failed to load skills:', e)
  }
}

function normalizeSkills(skills: unknown): string[] {
  if (!Array.isArray(skills)) return []
  const seen = new Set<string>()
  const result: string[] = []
  for (const item of skills) {
    const v = String(item || '').trim()
    if (!v || seen.has(v)) continue
    seen.add(v)
    result.push(v)
  }
  return result
}

function isSkillSelected(skills: unknown, skillName: string): boolean {
  const normalized = normalizeSkills(skills)
  return normalized.includes(String(skillName || '').trim())
}

function toggleSkill(target: 'new' | 'edit', skillName: string, checked: boolean) {
  const name = String(skillName || '').trim()
  if (!name) return

  const current = target === 'new'
    ? normalizeSkills(newAgent.value.skills)
    : normalizeSkills(editingAgent.value.skills)

  const next = checked
    ? Array.from(new Set([...current, name]))
    : current.filter(s => s !== name)

  if (target === 'new') {
    newAgent.value.skills = next
  } else {
    editingAgent.value.skills = next
  }
}

function closeAllPickers() {
  showEmojiPicker.value = ''
}

onMounted(() => {
  agentsStore.loadAgents()
  Promise.all([loadProviderMode(), loadSkills()]).then(() => loadModels())
  document.addEventListener('click', closeAllPickers)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeAllPickers)
})

async function reloadAgents() {
  await agentsStore.reloadAgents()
}

async function createAgent() {
  creating.value = true
  try {
    newAgent.value.skills = normalizeSkills(newAgent.value.skills)
    await agentsStore.createAgent(newAgent.value)
    showCreateModal.value = false
    resetForm()
  } finally {
    creating.value = false
  }
}

async function viewDetail(name: string) {
  await agentsStore.loadAgentDetail(name)
  showDetailModal.value = true
}

function closeDetail() {
  showDetailModal.value = false
  agentsStore.currentAgent = null
}

async function deleteAgent(name: string) {
  if (!confirm(`确定要删除 Agent "${name}" 吗？`)) return
  await agentsStore.deleteAgent(name)
}

function editAgent(agent: any) {
  editingAgentName.value = agent.name || ''
  editingAgent.value = {
    title: agent.title,
    emoji: agent.emoji,
    description: agent.description,
    system_prompt: '', // 需要重新加载详情获取
    type: agent.type,
    skills: normalizeSkills(agent.skills),
    max_iterations: 15,
    model: null,
  }
  // 加载完整详情
  agentsStore.loadAgentDetail(agent.name).then(() => {
    if (agentsStore.currentAgent) {
      editingAgent.value.system_prompt = agentsStore.currentAgent.system_prompt
      editingAgent.value.skills = normalizeSkills(agentsStore.currentAgent.skills)
      editingAgent.value.max_iterations = agentsStore.currentAgent.max_iterations
      editingAgent.value.model = agentsStore.currentAgent.model || null
    }
  })
  showEditModal.value = true
}

async function updateAgent() {
  editing.value = true
  try {
    const name = editingAgentName.value || agentsStore.currentAgent?.name
    if (!name) {
      console.error('No editing agent name found')
      return
    }

    if (editingAgent.value.skills !== undefined) {
      editingAgent.value.skills = normalizeSkills(editingAgent.value.skills)
    }
    
    await agentsStore.updateAgent(name, editingAgent.value)
    showEditModal.value = false
    editingAgentName.value = ''
  } finally {
    editing.value = false
  }
}

function resetForm() {
  newAgent.value = {
    name: '',
    title: '',
    emoji: '🤖',
    description: '',
    system_prompt: '',
    type: 'subagent',
    skills: [],
    max_iterations: 15,
    model: null,
  }
}
</script>

<style scoped>
.agents-manager {
  padding: 1rem 0;
}

.agents-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.agents-actions {
  display: flex;
  gap: 0.5rem;
}

.agents-filter {
  display: flex;
  gap: 0.5rem;
}

.filter-select {
  padding: 0.5rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
}

.btn-primary, .btn-secondary {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.6rem 1rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-primary {
  background: #1976d2;
  color: white;
}

.btn-primary:hover {
  background: #1565c0;
}

.btn-secondary {
  background: #f5f5f5;
  color: #616161;
  border: 1px solid #e0e0e0;
}

.btn-secondary:hover:not(:disabled) {
  background: #e0e0e0;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.icon {
  font-size: 1.1rem;
}

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: #616161;
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.agent-card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.2s;
}

.agent-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.agent-card.custom {
  border-left: 4px solid #1976d2;
}

.agent-header {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-bottom: 0.8rem;
}

.agent-emoji {
  font-size: 1.5rem;
}

.agent-title {
  flex: 1;
}

.agent-title h4 {
  margin: 0;
  font-size: 1rem;
  color: #2c3e50;
}

.agent-name {
  font-size: 0.8rem;
  color: #616161;
  font-family: monospace;
}

.agent-badges {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  align-items: flex-end;
}

.badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
}

.badge.source.preset {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge.source.custom {
  background: #e3f2fd;
  color: #1976d2;
}

.badge.domain {
  background: #f5f5f5;
  color: #616161;
  text-transform: capitalize;
}

.agent-description {
  font-size: 0.85rem;
  color: #616161;
  margin: 0 0 0.8rem 0;
  line-height: 1.4;
  min-height: 2.8em;
}

.agent-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.8rem;
  border-top: 1px solid #f0f0f0;
}

.agent-type {
  font-size: 0.75rem;
  color: #9e9e9e;
  text-transform: uppercase;
}

.agent-actions {
  display: flex;
  gap: 0.3rem;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  font-size: 1rem;
  opacity: 0.6;
  transition: all 0.2s;
}

.btn-icon:hover {
  opacity: 1;
  background: #f5f5f5;
}

.btn-icon.danger:hover {
  background: #ffebee;
}

/* Modal */
.modal-overlay {
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
  max-width: 600px;
  max-height: 90vh;
  overflow: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
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
  cursor: pointer;
  color: #616161;
}

.create-form {
  padding: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row .form-group {
  flex: 1;
}

.form-row .form-group.small {
  flex: 0.3;
}

.form-group label {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.85rem;
  color: #616161;
  font-weight: 500;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.6rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 0.9rem;
  font-family: inherit;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #1976d2;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.8rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #e0e0e0;
}

/* Detail Modal */
.detail-modal {
  max-width: 700px;
}

.detail-content {
  padding: 1.5rem;
}

.detail-section {
  margin-bottom: 1rem;
}

.detail-section label {
  display: block;
  font-size: 0.8rem;
  color: #9e9e9e;
  margin-bottom: 0.3rem;
}

.prompt-preview {
  background: #f5f5f5;
  padding: 1rem;
  border-radius: 4px;
  font-size: 0.85rem;
  line-height: 1.6;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.tag {
  background: #e3f2fd;
  color: #1976d2;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.8rem;
}

.model-badge {
  display: inline-block;
  background: #fff3e0;
  color: #e65100;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-family: monospace;
  border: 1px solid #ffcc80;
}

.model-default {
  font-size: 0.85rem;
  color: #9e9e9e;
  font-style: italic;
}

.label-hint {
  font-size: 0.75rem;
  color: #9e9e9e;
  font-weight: normal;
}

.model-select {
  width: 100%;
  padding: 0.6rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 0.9rem;
  font-family: inherit;
  background: white;
  cursor: pointer;
}

.model-select:focus {
  outline: none;
  border-color: #1976d2;
}

.provider-hint {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: #9e9e9e;
}

.multi-select {
  width: 100%;
  min-height: 120px;
  padding: 0.5rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 0.9rem;
  background: white;
}

.multi-select:focus {
  outline: none;
  border-color: #1976d2;
}

.skills-checklist {
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 0.5rem;
  background: #fff;
}

.skill-item {
  display: grid;
  grid-template-columns: 18px 1fr;
  align-items: start;
  gap: 0.6rem;
  padding: 0.45rem 0.25rem;
  cursor: pointer;
  border-radius: 4px;
}

.skill-item:hover {
  background: #f8f9fa;
}

.skill-checkbox {
  width: auto !important;
  margin-top: 0.2rem;
  cursor: pointer;
}

.skill-meta {
  min-width: 0;
}

.skill-main {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.skill-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: #2c3e50;
}

.skill-source {
  font-size: 0.72rem;
  color: #5f6b7a;
  background: #eef2f7;
  border: 1px solid #d9e2ef;
  border-radius: 999px;
  padding: 0.05rem 0.4rem;
}

.skill-desc {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.78rem;
  color: #8c96a3;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Emoji Picker */
.emoji-picker-wrapper {
  position: relative;
  display: inline-block;
}

.emoji-trigger {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 1.4rem;
  line-height: 1;
  text-align: center;
  transition: border-color 0.2s;
  min-width: 52px;
}

.emoji-trigger:hover {
  border-color: #1976d2;
}

.emoji-grid {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 2000;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 8px;
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 2px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  min-width: 280px;
}

.emoji-option {
  font-size: 1.3rem;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  text-align: center;
  transition: background 0.15s;
  user-select: none;
}

.emoji-option:hover {
  background: #f0f0f0;
}

/* Skills / 多选下拉 */
.multi-pick-wrapper {
  position: relative;
}

.multi-pick-trigger {
  width: 100%;
  min-height: 38px;
  padding: 0.4rem 0.6rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 0.9rem;
  text-align: left;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  transition: border-color 0.2s;
}

.multi-pick-trigger:hover {
  border-color: #1976d2;
}

.pick-placeholder {
  color: #aaa;
  flex: 1;
}

.pick-tags {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.pick-tag {
  background: #e3f2fd;
  color: #1565c0;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.78rem;
}

.drop-arrow {
  color: #9e9e9e;
  font-size: 0.8rem;
  flex-shrink: 0;
}

.multi-pick-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 2000;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  max-height: 220px;
  overflow-y: auto;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.pick-option {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  transition: background 0.15s;
}

.pick-option:hover {
  background: #f5f5f5;
}

.pick-option input[type="checkbox"] {
  flex-shrink: 0;
  cursor: pointer;
}

.pick-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #2c3e50;
  white-space: nowrap;
}

.pick-desc {
  font-size: 0.75rem;
  color: #9e9e9e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.pick-empty {
  padding: 0.75rem;
  text-align: center;
  color: #9e9e9e;
  font-size: 0.85rem;
}
</style>
