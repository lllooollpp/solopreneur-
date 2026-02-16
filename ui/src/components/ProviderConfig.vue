<template>
  <div class="provider-config">
    <h3>🌐 LLM Providers 配置</h3>
    <p class="section-desc">配置使用哪个 LLM 提供商，支持 GitHub Copilot 和其他第三方服务</p>

    <!-- GitHub Copilot 区域 -->
    <div class="copilot-section">
      <div class="section-header">
        <div class="section-title">
          <span class="title-icon">🐙</span>
          <h4>GitHub Copilot</h4>
        </div>
        <div class="priority-toggle">
          <label class="toggle-switch">
            <input type="checkbox" v-model="copilotPriority" @change="toggleCopilotPriority" />
            <span class="slider"></span>
          </label>
          <span class="toggle-label">{{ copilotPriority ? '优先使用' : '不优先' }}</span>
        </div>
      </div>
      <p class="section-desc">
        {{ copilotPriority ? '已启用：将优先使用 GitHub Copilot（需要先登录账号）' : '已禁用：将使用下方配置的其他 Provider' }}
      </p>
      <router-link to="/accounts" class="link-btn">前往账号池管理 →</router-link>
    </div>

    <div class="divider">
      <span>或配置其他 Provider</span>
    </div>

    <!-- 其他 Provider 选择器 -->
    <div class="provider-selector">
      <label class="selector-label">选择其他 Provider:</label>
      <div class="provider-tabs">
        <button
          v-for="opt in otherProviderOptions"
          :key="opt.value"
          :class="['provider-tab', { active: selectedProvider === opt.value }]"
          @click="selectProvider(opt.value)"
        >
          <span class="tab-icon">{{ opt.icon }}</span>
          <span class="tab-label">{{ opt.label }}</span>
        </button>
      </div>
    </div>

    <!-- 当前 Provider 配置 -->
    <div class="config-panel">
      <div class="provider-header">
        <div class="provider-title">
          <span class="title-icon">{{ currentProviderOption?.icon }}</span>
          <span class="title-text">{{ currentProviderOption?.label }}</span>
        </div>
        <span class="provider-desc">{{ currentProviderOption?.description }}</span>
      </div>

      <div class="provider-form">
        <div class="form-group">
          <label>API Key</label>
          <div class="input-with-toggle">
            <input
              v-model="currentConfig.api_key"
              :type="showApiKey ? 'text' : 'password'"
              placeholder="输入 API Key"
              class="input-field"
            />
            <button class="toggle-btn" @click="showApiKey = !showApiKey">
              {{ showApiKey ? '👁️' : '🔒' }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>API Base (可选)</label>
          <input
            v-model="currentConfig.api_base"
            placeholder="默认将使用官方 API 端点"
            class="input-field"
          />
          <span class="field-hint">留空则使用官方端点</span>
        </div>

        <div class="form-group">
          <label>默认模型</label>
          <div class="model-input-wrapper">
            <input
              v-model="agentDefaults.model"
              placeholder="模型名称"
              class="input-field"
            />
            <select v-model="selectedModelSuggestion" class="model-suggestions" @change="applyModelSuggestion">
              <option value="">快速选择...</option>
              <option v-for="model in modelSuggestions" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label>Max Tokens</label>
          <input
            v-model.number="agentDefaults.max_tokens"
            type="number"
            min="1"
            max="128000"
            class="input-field"
          />
        </div>

        <div class="form-group">
          <label>Temperature: {{ agentDefaults.temperature }}</label>
          <div class="slider-wrapper">
            <input
              v-model.number="agentDefaults.temperature"
              type="range"
              min="0"
              max="1"
              step="0.1"
              class="slider"
            />
            <span class="slider-value">{{ agentDefaults.temperature }}</span>
          </div>
        </div>

        <div class="form-group">
          <label>审批模式</label>
          <select v-model="agentDefaults.review_mode" class="input-field">
            <option value="auto">自动审核（自动继续执行）</option>
            <option value="manual">人工审核（先 message 通知并等待确认）</option>
          </select>
          <span class="field-hint">控制任务推进时是否需要用户确认</span>
        </div>

        <div class="form-actions">
          <button class="btn-test" @click="testConnection" :disabled="testing">
            {{ testing ? '⏳ 测试中...' : '🔍 测试连接' }}
          </button>
          <button class="btn-save" @click="saveConfig" :disabled="saving">
            {{ saving ? '⏳ 保存中...' : '💾 保存配置' }}
          </button>
        </div>

        <div v-if="testResult" :class="['test-result', testResult.success ? 'success' : 'error']">
          {{ testResult.success ? '✅' : '❌' }} {{ testResult.success ? '连接成功' : testResult.error }}
        </div>
      </div>
    </div>

    <!-- 配置说明 -->
    <div class="info-box">
      <h5>💡 Provider 选择逻辑</h5>
      <ul>
        <li><strong>优先使用 Copilot</strong>: 如果勾选"优先使用"，系统将优先使用 GitHub Copilot</li>
        <li><strong>其他 Provider</strong>: Copilot 未启用或不可用时，按以下优先级使用:
          <ul>
            <li>🏠 本地 OpenAI 标准接口 (vLLM)</li>
            <li>🌋 火山引擎 / 智谱 AI</li>
            <li>🌐 OpenRouter</li>
            <li>🧠 Anthropic Claude</li>
            <li>🤖 OpenAI</li>
            <li>⚡ Groq</li>
            <li>💎 Google Gemini</li>
          </ul>
        </li>
        <li><strong>注意</strong>: 修改配置后需要重启服务</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { PROVIDER_OPTIONS, MODEL_SUGGESTIONS, type ProviderType } from '@/types/provider'
import { getProvidersConfig, updateProvidersConfig, getAgentDefaults, updateAgentDefaults, testProviderConnection } from '@/api/provider'

// Copilot 优先级开关
const copilotPriority = ref(false)

const selectedProvider = ref<ProviderType>('vllm')  // 默认选择本地 Provider
const showApiKey = ref(false)
const testing = ref(false)
const saving = ref(false)
const testResult = ref<{ success: boolean; error?: string } | null>(null)

const providersConfig = reactive({
  anthropic: { api_key: '', api_base: null },
  openai: { api_key: '', api_base: null },
  openrouter: { api_key: '', api_base: null },
  groq: { api_key: '', api_base: null },
  zhipu: { api_key: '', api_base: null },
  vllm: { api_key: '', api_base: null },
  gemini: { api_key: '', api_base: null },
  copilot_priority: false as boolean
})

const agentDefaults = reactive({
  model: 'llama-3-8b',
  max_tokens: 8192,
  temperature: 0.7,
  review_mode: 'auto' as 'auto' | 'manual',
})

const selectedModelSuggestion = ref('')

// 过滤掉 copilot，只显示其他 Provider
const otherProviderOptions = computed(() => {
  return PROVIDER_OPTIONS.filter(opt => opt.value !== 'copilot')
})

const currentProviderOption = computed(() => {
  return PROVIDER_OPTIONS.find(opt => opt.value === selectedProvider.value)
})

const currentConfig = computed(() => {
  const config = providersConfig[selectedProvider.value as keyof typeof providersConfig]
  // 确保返回的是 ProviderConfig 类型
  if (typeof config === 'object' && config !== null && 'api_key' in config) {
    return config as { api_key: string; api_base: string | null }
  }
  return { api_key: '', api_base: null }
})

const modelSuggestions = computed(() => {
  return MODEL_SUGGESTIONS[selectedProvider.value] || []
})

function selectProvider(provider: ProviderType) {
  selectedProvider.value = provider
  testResult.value = null
  selectedModelSuggestion.value = ''
}

function applyModelSuggestion() {
  if (selectedModelSuggestion.value) {
    agentDefaults.model = selectedModelSuggestion.value
  }
}

async function toggleCopilotPriority() {
  const prev = providersConfig.copilot_priority
  providersConfig.copilot_priority = copilotPriority.value

  try {
    // 开关切换即立即持久化到后端
    await updateProvidersConfig(providersConfig as any)

    // 回读后端，确保与服务端一致
    const persistedProviders = await getProvidersConfig()
    Object.assign(providersConfig, persistedProviders)
    copilotPriority.value = persistedProviders.copilot_priority ?? false

    // 同步到本地缓存，供聊天页快速读取
    const configToSave = {
      providers: {
        copilot_priority: persistedProviders.copilot_priority,
        anthropic: persistedProviders.anthropic,
        openai: persistedProviders.openai,
        openrouter: persistedProviders.openrouter,
        groq: persistedProviders.groq,
        zhipu: persistedProviders.zhipu,
        vllm: persistedProviders.vllm,
        gemini: persistedProviders.gemini
      },
      agents: {
        defaults: agentDefaults
      }
    }
    localStorage.setItem('provider_config', JSON.stringify(configToSave))
  } catch (e: any) {
    // 失败回滚 UI 状态
    providersConfig.copilot_priority = prev
    copilotPriority.value = prev
    alert(`❌ 优先开关保存失败: ${e.response?.data?.detail || e.message || '未知错误'}`)
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const result = await testProviderConnection(selectedProvider.value, currentConfig.value)
    testResult.value = result
  } catch (e: any) {
    testResult.value = { success: false, error: e.response?.data?.detail || e.message || '测试失败' }
  } finally {
    testing.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    // 保存到后端
    await updateProvidersConfig(providersConfig)
    await updateAgentDefaults(agentDefaults)

    // 立刻回读后端，确保“优先使用”已真正持久化
    const persistedProviders = await getProvidersConfig()
    Object.assign(providersConfig, persistedProviders)
    copilotPriority.value = persistedProviders.copilot_priority ?? false

    // 同时保存到 localStorage（用于前端快速读取）
    const configToSave = {
      providers: {
        copilot_priority: persistedProviders.copilot_priority,
        anthropic: providersConfig.anthropic,
        openai: providersConfig.openai,
        openrouter: providersConfig.openrouter,
        groq: providersConfig.groq,
        zhipu: providersConfig.zhipu,
        vllm: providersConfig.vllm,
        gemini: providersConfig.gemini
      },
      agents: {
        defaults: agentDefaults
      }
    }
    localStorage.setItem('provider_config', JSON.stringify(configToSave))

    alert('✅ 配置已保存，请重启服务使配置生效！')
  } catch (e: any) {
    alert(`❌ 保存失败: ${e.response?.data?.detail || e.message || '未知错误'}`)
  } finally {
    saving.value = false
  }
}

async function loadConfig() {
  try {
    const [providers, defaults] = await Promise.all([
      getProvidersConfig(),
      getAgentDefaults()
    ])
    Object.assign(providersConfig, providers)
    Object.assign(agentDefaults, defaults)

    // 加载 copilot_priority 状态
    const anyProviders = providers as any
    copilotPriority.value = anyProviders.copilot_priority || false

    // 同时保存到 localStorage（供 ChatView 使用）
    const configToSave = {
      providers: {
        copilot_priority: providers.copilot_priority,
        anthropic: providers.anthropic,
        openai: providers.openai,
        openrouter: providers.openrouter,
        groq: providers.groq,
        zhipu: providers.zhipu,
        vllm: providers.vllm,
        gemini: providers.gemini
      },
      agents: {
        defaults: defaults
      }
    }
    localStorage.setItem('provider_config', JSON.stringify(configToSave))
  } catch (e: any) {
    console.error('加载配置失败:', e)
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.provider-config {
  margin-bottom: 2rem;
}

.section-desc {
  color: #757575;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
}

.provider-selector {
  margin-bottom: 1.5rem;
}

.selector-label {
  display: block;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 0.8rem;
}

.provider-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.provider-tab {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.2rem;
  background: #f5f5f5;
  border: 2px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
  color: #616161;
}

.provider-tab:hover {
  background: #eeeeee;
}

.provider-tab.active {
  background: #e3f2fd;
  border-color: #1976d2;
  color: #1976d2;
}

.tab-icon {
  font-size: 1.2rem;
}

.config-panel {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.provider-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e0e0e0;
}

.provider-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 1.3rem;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 0.4rem;
}

.title-icon {
  font-size: 1.5rem;
}

.provider-desc {
  color: #757575;
  font-size: 0.9rem;
}

.config-info {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 1rem;
  background: #e3f2fd;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  color: #1976d2;
}

.info-icon {
  font-size: 1.5rem;
}

.provider-form {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.9rem;
}

.input-field {
  padding: 0.8rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 0.95rem;
  transition: border-color 0.2s;
}

.input-field:focus {
  outline: none;
  border-color: #1976d2;
}

.input-with-toggle {
  display: flex;
  gap: 0.5rem;
}

.input-with-toggle .input-field {
  flex: 1;
}

.toggle-btn {
  padding: 0 1rem;
  background: #f5f5f5;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.2s;
}

.toggle-btn:hover {
  background: #eeeeee;
}

.field-hint {
  font-size: 0.8rem;
  color: #9e9e9e;
}

.model-input-wrapper {
  display: flex;
  gap: 0.5rem;
}

.model-input-wrapper .input-field {
  flex: 1;
}

.model-suggestions {
  padding: 0.8rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  background: white;
  font-size: 0.9rem;
  cursor: pointer;
}

.model-suggestions:focus {
  outline: none;
  border-color: #1976d2;
}

.slider-wrapper {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.slider {
  flex: 1;
  -webkit-appearance: none;
  height: 6px;
  background: #e0e0e0;
  border-radius: 3px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  background: #1976d2;
  border-radius: 50%;
  cursor: pointer;
}

.slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  background: #1976d2;
  border-radius: 50%;
  cursor: pointer;
}

.slider-value {
  font-weight: 600;
  color: #1976d2;
  min-width: 40px;
}

.form-actions {
  display: flex;
  gap: 1rem;
  margin-top: 0.5rem;
}

.btn-test,
.btn-save {
  flex: 1;
  padding: 0.9rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-test {
  background: #fff3e0;
  color: #e65100;
}

.btn-test:hover:not(:disabled) {
  background: #ffe0b2;
}

.btn-test:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-save {
  background: linear-gradient(135deg, #1976d2, #1565c0);
  color: white;
}

.btn-save:hover:not(:disabled) {
  background: linear-gradient(135deg, #1565c0, #0d47a1);
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.3);
}

.btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.test-result {
  margin-top: 1rem;
  padding: 0.8rem 1rem;
  border-radius: 8px;
  font-weight: 500;
}

.test-result.success {
  background: #e8f5e9;
  color: #2e7d32;
  border-left: 4px solid #4caf50;
}

.test-result.error {
  background: #ffebee;
  color: #c62828;
  border-left: 4px solid #f44336;
}

.btn-primary {
  display: inline-block;
  background: #1976d2;
  color: white;
  text-decoration: none;
  padding: 0.8rem 2rem;
  border-radius: 8px;
  font-weight: 600;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #1565c0;
}

/* 新增样式：Copilot 区域和分隔符 */
.copilot-section {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  border: 2px solid #90caf9;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.section-title h4 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
  color: #1565c0;
}

.priority-toggle {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 26px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-switch .slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .4s;
  border-radius: 26px;
}

.toggle-switch .slider:before {
  position: absolute;
  content: "";
  height: 20px;
  width: 20px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .4s;
  border-radius: 50%;
}

.toggle-switch input:checked + .slider {
  background: linear-gradient(135deg, #1976d2, #1565c0);
}

.toggle-switch input:checked + .slider:before {
  transform: translateX(24px);
}

.toggle-label {
  font-weight: 600;
  color: #1565c0;
  min-width: 60px;
}

.divider {
  position: relative;
  text-align: center;
  margin: 2rem 0;
}

.divider::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 100%;
  height: 2px;
  background: #e0e0e0;
}

.divider span {
  position: relative;
  background: white;
  padding: 0 1rem;
  color: #9e9e9e;
  font-weight: 500;
}

.link-btn {
  display: inline-block;
  color: #1976d2;
  text-decoration: none;
  font-weight: 600;
  padding: 0.5rem 0;
  transition: color 0.2s;
}

.link-btn:hover {
  color: #1565c0;
  text-decoration: underline;
}

.info-box {
  background: #f5f5f5;
  border-radius: 12px;
  padding: 1.5rem;
  margin-top: 2rem;
  border-left: 4px solid #1976d2;
}

.info-box h5 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 700;
  color: #2c3e50;
}

.info-box ul {
  margin: 0;
  padding-left: 1.5rem;
}

.info-box li {
  margin-bottom: 0.5rem;
  color: #616161;
  line-height: 1.6;
}

.info-box li ul {
  margin-top: 0.5rem;
  padding-left: 1.2rem;
}

.info-box li ul li {
  margin-bottom: 0.3rem;
  color: #757575;
}
</style>
