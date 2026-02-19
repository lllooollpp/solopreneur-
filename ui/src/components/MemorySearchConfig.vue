<template>
  <div class="memory-search-config">
    <h3>🧠 记忆搜索引擎</h3>
    <p class="section-desc">配置语义记忆搜索引擎，支持向量 + 关键词混合检索</p>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading">⏳ 加载配置中...</div>

    <template v-else>
      <!-- 总开关 -->
      <div class="main-toggle">
        <div class="toggle-info">
          <span class="toggle-title">启用记忆搜索</span>
          <span class="toggle-desc">开启后 Agent 将能语义检索项目记忆文件</span>
        </div>
        <label class="toggle-switch">
          <input type="checkbox" v-model="config.enabled" />
          <span class="slider"></span>
        </label>
      </div>

      <div :class="['config-body', { disabled: !config.enabled }]">
        <!-- Embedding 提供商 -->
        <div class="sub-section">
          <h4>📡 向量嵌入 (Embedding)</h4>

          <div class="form-group">
            <label>嵌入提供商</label>
            <select v-model="config.embedding_provider" class="input-field">
              <option value="local">💻 本地模型（CPU 运行，零 API 开销）</option>
              <option value="auto">🔄 Auto（优先本地 → 自动推断）</option>
              <option value="openai">🤖 OpenAI</option>
              <option value="litellm">🌐 LiteLLM（支持多后端）</option>
              <option value="custom">🔧 自定义 URL</option>
              <option value="noop">🚫 禁用向量（仅关键词搜索）</option>
            </select>
            <span class="field-hint">
              <template v-if="config.embedding_provider === 'local'">
                使用 sentence-transformers 在本地 CPU 运行，无需 API Key
              </template>
              <template v-else-if="config.embedding_provider === 'auto'">
                优先使用本地模型，未安装则自动复用 LLM Provider 的 API
              </template>
              <template v-else-if="config.embedding_provider === 'noop'">
                禁用向量搜索后仅使用 FTS5 关键词搜索
              </template>
              <template v-else>
                需要填写下方的 API Key 和 Base URL
              </template>
            </span>
          </div>

          <!-- 本地模式时显示设备选择 -->
          <template v-if="config.embedding_provider === 'local' || config.embedding_provider === 'auto'">
            <div class="form-group">
              <label>运行设备</label>
              <select v-model="config.embedding_device" class="input-field">
                <option value="auto">🔍 自动检测（有 GPU 用 GPU，否则 CPU）</option>
                <option value="cpu">💻 CPU（稳定，无需 GPU）</option>
                <option value="cuda">⚡ CUDA GPU（需要 NVIDIA GPU）</option>
              </select>
              <span class="field-hint">CPU 模式速度稍慢但兼容性好，推荐较小模型如 all-MiniLM-L6-v2</span>
            </div>
          </template>

          <!-- 非 auto / 非 noop / 非 local 时显示详细配置 -->
          <template v-if="showEmbeddingDetails">
            <div class="form-group">
              <label>Embedding API Key</label>
              <div class="input-with-toggle">
                <input
                  v-model="config.embedding_api_key"
                  :type="showApiKey ? 'text' : 'password'"
                  placeholder="输入 Embedding API Key"
                  class="input-field"
                />
                <button class="toggle-btn" @click="showApiKey = !showApiKey">
                  {{ showApiKey ? '👁️' : '🔒' }}
                </button>
              </div>
            </div>

            <div class="form-group">
              <label>Embedding API Base (可选)</label>
              <input
                v-model="config.embedding_api_base"
                placeholder="留空则使用官方端点"
                class="input-field"
              />
              <span class="field-hint">自定义 Embedding 服务地址，例如 http://localhost:8080/v1</span>
            </div>
          </template>

          <div class="form-row">
            <div class="form-group half">
              <label>模型名称</label>
              <input
                v-model="config.embedding_model"
                placeholder="text-embedding-3-small"
                class="input-field"
              />
            </div>
            <div class="form-group half">
              <label>向量维度</label>
              <input
                v-model.number="config.embedding_dimension"
                type="number"
                min="64"
                max="8192"
                class="input-field"
              />
            </div>
          </div>

          <div class="form-group">
            <label>批量嵌入大小</label>
            <input
              v-model.number="config.embedding_batch_size"
              type="number"
              min="1"
              max="512"
              class="input-field"
            />
            <span class="field-hint">每次 API 调用嵌入多少个文本块</span>
          </div>
        </div>

        <!-- 搜索参数 -->
        <div class="sub-section">
          <h4>🔍 搜索参数</h4>

          <div class="form-group">
            <label>向量权重: {{ config.vector_weight.toFixed(1) }}</label>
            <div class="dual-slider">
              <span class="slider-label left">关键词</span>
              <input
                v-model.number="config.vector_weight"
                type="range"
                min="0"
                max="1"
                step="0.1"
                class="slider"
                @input="syncWeights"
              />
              <span class="slider-label right">向量</span>
            </div>
            <div class="weight-display">
              <span class="weight-tag keyword">关键词 {{ config.keyword_weight.toFixed(1) }}</span>
              <span class="weight-tag vector">向量 {{ config.vector_weight.toFixed(1) }}</span>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group half">
              <label>返回条数 (Top-K)</label>
              <input
                v-model.number="config.top_k"
                type="number"
                min="1"
                max="50"
                class="input-field"
              />
            </div>
            <div class="form-group half">
              <label>最低分数阈值</label>
              <input
                v-model.number="config.min_score"
                type="number"
                min="0"
                max="1"
                step="0.05"
                class="input-field"
              />
            </div>
          </div>
        </div>

        <!-- 分块参数 -->
        <div class="sub-section">
          <h4>📄 文本分块</h4>

          <div class="form-row">
            <div class="form-group half">
              <label>最大块大小 (字符)</label>
              <input
                v-model.number="config.max_chunk_size"
                type="number"
                min="200"
                max="8000"
                step="100"
                class="input-field"
              />
            </div>
            <div class="form-group half">
              <label>最小块大小 (字符)</label>
              <input
                v-model.number="config.min_chunk_size"
                type="number"
                min="50"
                max="1000"
                step="50"
                class="input-field"
              />
            </div>
          </div>
        </div>

        <!-- 其他选项 -->
        <div class="sub-section">
          <h4>⚙️ 其他选项</h4>

          <div class="toggle-row">
            <div class="toggle-info">
              <span class="toggle-title">启动时自动索引</span>
              <span class="toggle-desc">Agent 启动时自动扫描并索引记忆目录</span>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" v-model="config.auto_index_on_start" />
              <span class="slider"></span>
            </label>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="form-actions">
          <button class="btn-reset" @click="resetDefaults">
            🔄 恢复默认
          </button>
          <button class="btn-save" @click="saveConfig" :disabled="saving">
            {{ saving ? '⏳ 保存中...' : '💾 保存配置' }}
          </button>
        </div>

        <!-- 保存结果 -->
        <div v-if="saveResult" :class="['save-result', saveResult.success ? 'success' : 'error']">
          {{ saveResult.success ? '✅' : '❌' }} {{ saveResult.message }}
        </div>
      </div>

      <!-- 配置说明 -->
      <div class="info-box">
        <h5>💡 记忆搜索说明</h5>
        <ul>
          <li><strong>Local 模式（推荐）</strong>: 本地 CPU 运行 sentence-transformers，零 API 开销，首次启动需下载模型 (~80MB)</li>
          <li><strong>Auto 模式</strong>: 优先本地运行，未安装 sentence-transformers 则自动从 LLM Providers 推断</li>
          <li><strong>混合搜索</strong>: 结合向量语义搜索和 FTS5 关键词搜索，通过权重控制偏好</li>
          <li><strong>CJK 优化</strong>: 内置中日韩文字分词，无需外部分词器</li>
          <li><strong>零依赖</strong>: 所有数据存储在本地 SQLite，不需要外部向量数据库</li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { getMemorySearchConfig, updateMemorySearchConfig, type MemorySearchConfig } from '@/api/memorySearch'

const loading = ref(true)
const saving = ref(false)
const showApiKey = ref(false)
const saveResult = ref<{ success: boolean; message: string } | null>(null)

const config = reactive<MemorySearchConfig>({
  enabled: true,
  embedding_provider: 'local',
  embedding_model: 'all-MiniLM-L6-v2',
  embedding_device: 'auto',
  embedding_api_key: '',
  embedding_api_base: '',
  embedding_dimension: 384,
  embedding_batch_size: 64,
  vector_weight: 0.6,
  keyword_weight: 0.4,
  max_chunk_size: 1200,
  min_chunk_size: 100,
  top_k: 5,
  min_score: 0.1,
  auto_index_on_start: true,
})

const showEmbeddingDetails = computed(() => {
  return config.embedding_provider !== 'auto'
    && config.embedding_provider !== 'noop'
    && config.embedding_provider !== 'local'
})

function syncWeights() {
  config.keyword_weight = Math.round((1 - config.vector_weight) * 10) / 10
}

function resetDefaults() {
  Object.assign(config, {
    enabled: true,
    embedding_provider: 'local',
    embedding_model: 'all-MiniLM-L6-v2',
    embedding_device: 'auto',
    embedding_api_key: '',
    embedding_api_base: '',
    embedding_dimension: 384,
    embedding_batch_size: 64,
    vector_weight: 0.6,
    keyword_weight: 0.4,
    max_chunk_size: 1200,
    min_chunk_size: 100,
    top_k: 5,
    min_score: 0.1,
    auto_index_on_start: true,
  })
  saveResult.value = null
}

async function saveConfig() {
  saving.value = true
  saveResult.value = null
  try {
    await updateMemorySearchConfig(config)
    saveResult.value = { success: true, message: '记忆搜索配置已保存，重启后生效' }
  } catch (e: any) {
    saveResult.value = {
      success: false,
      message: e.response?.data?.detail || e.message || '保存失败',
    }
  } finally {
    saving.value = false
  }
}

async function loadConfig() {
  loading.value = true
  try {
    const data = await getMemorySearchConfig()
    Object.assign(config, data)
  } catch (e: any) {
    console.error('加载记忆搜索配置失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.memory-search-config {
  margin-bottom: 2rem;
}

.section-desc {
  color: #757575;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #9e9e9e;
}

/* 总开关 */
.main-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.2rem 1.5rem;
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  border-radius: 12px;
  border: 2px solid #a5d6a7;
  margin-bottom: 1.5rem;
}

.config-body {
  transition: opacity 0.3s;
}

.config-body.disabled {
  opacity: 0.4;
  pointer-events: none;
}

/* 子区域 */
.sub-section {
  background: #fafafa;
  border-radius: 10px;
  padding: 1.2rem 1.5rem;
  margin-bottom: 1.2rem;
  border: 1px solid #e0e0e0;
}

.sub-section h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 700;
  color: #2c3e50;
}

/* 表单 */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.9rem;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-group.half {
  flex: 1;
}

.input-field {
  padding: 0.7rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 0.95rem;
  transition: border-color 0.2s;
  background: white;
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

/* 双向滑块 */
.dual-slider {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.slider-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #757575;
  min-width: 45px;
}

.slider-label.left {
  text-align: right;
}

.slider-label.right {
  text-align: left;
}

.slider {
  flex: 1;
  -webkit-appearance: none;
  height: 6px;
  background: linear-gradient(to right, #ff9800, #1976d2);
  border-radius: 3px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  appearance: none;
  -webkit-appearance: none;
  width: 22px;
  height: 22px;
  background: white;
  border: 3px solid #1976d2;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.slider::-moz-range-thumb {
  width: 22px;
  height: 22px;
  background: white;
  border: 3px solid #1976d2;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.weight-display {
  display: flex;
  justify-content: space-between;
  margin-top: 0.4rem;
}

.weight-tag {
  padding: 0.2rem 0.8rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}

.weight-tag.keyword {
  background: #fff3e0;
  color: #e65100;
}

.weight-tag.vector {
  background: #e3f2fd;
  color: #1565c0;
}

/* Toggle 行 */
.toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.toggle-title {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.95rem;
}

.toggle-desc {
  font-size: 0.82rem;
  color: #9e9e9e;
}

/* Toggle 开关 */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 26px;
  flex-shrink: 0;
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
  transition: 0.3s;
  border-radius: 26px;
}

.toggle-switch .slider:before {
  position: absolute;
  content: '';
  height: 20px;
  width: 20px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}

.toggle-switch input:checked + .slider {
  background: linear-gradient(135deg, #4caf50, #388e3c);
}

.toggle-switch input:checked + .slider:before {
  transform: translateX(24px);
}

/* 操作按钮 */
.form-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1.5rem;
}

.btn-reset,
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

.btn-reset {
  background: #f5f5f5;
  color: #616161;
  border: 2px solid #e0e0e0;
}

.btn-reset:hover {
  background: #eeeeee;
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

/* 保存结果 */
.save-result {
  margin-top: 1rem;
  padding: 0.8rem 1rem;
  border-radius: 8px;
  font-weight: 500;
}

.save-result.success {
  background: #e8f5e9;
  color: #2e7d32;
  border-left: 4px solid #4caf50;
}

.save-result.error {
  background: #ffebee;
  color: #c62828;
  border-left: 4px solid #f44336;
}

/* 说明卡 */
.info-box {
  background: #f5f5f5;
  border-radius: 12px;
  padding: 1.5rem;
  margin-top: 1.5rem;
  border-left: 4px solid #7c4dff;
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
</style>
