<template>
  <div v-if="visible" class="dialog-overlay" @click="handleClose">
    <div class="dialog" @click.stop>
      <div class="dialog-header">
        <h3>{{ isEdit ? '编辑项目' : '新建项目' }}</h3>
        <button class="btn-close" @click="handleClose">×</button>
      </div>
      
      <div class="dialog-body">
        <!-- 项目名称 -->
        <div class="form-group">
          <label>项目名称 <span class="required">*</span></label>
          <input
            v-model="form.name"
            type="text"
            placeholder="输入项目名称"
            maxlength="100"
          />
        </div>
        
        <!-- 项目描述 -->
        <div class="form-group">
          <label>项目描述</label>
          <textarea
            v-model="form.description"
            placeholder="输入项目描述（可选）"
            rows="3"
            maxlength="500"
          ></textarea>
        </div>
        
        <!-- 项目来源 -->
        <div class="form-group">
          <label>项目来源</label>
          <div class="radio-group">
            <label class="radio-label">
              <input
                v-model="form.source"
                type="radio"
                value="local"
                :disabled="isEdit"
              />
              <span>📁 本地项目</span>
            </label>
            <label class="radio-label">
              <input
                v-model="form.source"
                type="radio"
                value="github"
                :disabled="isEdit"
              />
              <span>🐙 GitHub</span>
            </label>
            <label class="radio-label">
              <input
                v-model="form.source"
                type="radio"
                value="gitlab"
                :disabled="isEdit"
              />
              <span>🦊 GitLab</span>
            </label>
            <label class="radio-label">
              <input
                v-model="form.source"
                type="radio"
                value="git"
                :disabled="isEdit"
              />
              <span>📦 其他 Git</span>
            </label>
          </div>
        </div>
        
        <!-- 本地项目路径 -->
        <div v-if="form.source === 'local'" class="form-group">
          <label>项目路径 <span class="required">*</span></label>
          <input
            v-model="form.local_path"
            type="text"
            placeholder="输入绝对路径，例如: /home/user/projects/myapp"
            :disabled="isEdit"
          />
          <span class="hint">可以是已存在的目录，系统会自动创建不存在的目录</span>
        </div>
        
        <!-- Git 仓库 URL -->
        <div v-else class="form-group">
          <label>仓库地址 <span class="required">*</span></label>
          <input
            v-model="form.git_url"
            type="text"
            placeholder="https://github.com/username/repo.git"
            :disabled="isEdit"
          />
        </div>
        
        <!-- Git 分支 -->
        <div v-if="form.source !== 'local'" class="form-group">
          <label>分支</label>
          <input
            v-model="form.git_branch"
            type="text"
            placeholder="main"
            :disabled="isEdit"
          />
          <span class="hint">默认为 main</span>
        </div>
        
        <!-- Git 认证信息（仅创建时显示） -->
        <template v-if="form.source !== 'local' && !isEdit">
          <div class="form-divider"></div>
          <div class="form-section-title">
            🔐 认证信息（私有仓库需要）
          </div>
          
          <div class="form-group">
            <label>用户名</label>
            <input
              v-model="form.git_username"
              type="text"
              placeholder="Git 用户名或组织名（可选）"
            />
            <span class="hint">GitHub 可填写任意值，GitLab 需填写实际用户名</span>
          </div>
          
          <div class="form-group">
            <label>Token / 密码</label>
            <input
              v-model="form.git_token"
              type="password"
              placeholder="Personal Access Token"
            />
            <span class="hint">
              GitHub: Settings → Developer settings → Personal access tokens<br>
              GitLab: Preferences → Access Tokens
            </span>
          </div>
          
          <div class="form-divider"></div>
          <div class="form-section-title">
            🌐 网络代理（国内访问需要）
          </div>
          
          <div class="form-group">
            <label class="checkbox-label">
              <input
                v-model="form.use_proxy"
                type="checkbox"
              />
              <span>使用代理访问</span>
            </label>
          </div>
          
          <div v-if="form.use_proxy" class="form-group">
            <label>代理地址 <span class="required">*</span></label>
            <input
              v-model="form.proxy_url"
              type="text"
              placeholder="http://127.0.0.1:7890"
            />
            <span class="hint">
              格式: http://host:port 或 socks5://host:port<br>
              常见端口: Clash(7890), v2rayN(10808), Shadowsocks(1080)
            </span>
          </div>
        </template>
      </div>
      
      <div class="dialog-footer">
        <button class="btn-cancel" @click="handleClose">取消</button>
        <button class="btn-save" :disabled="!isValid" @click="handleSave">
          {{ isEdit ? '保存' : '创建' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { Project, ProjectCreate, ProjectUpdate } from '@/types/project'

interface FormData {
  name: string
  description: string
  source: 'local' | 'github' | 'gitlab' | 'git'
  local_path: string
  git_url: string
  git_branch: string
  git_username: string
  git_token: string
  use_proxy: boolean
  proxy_url: string
}

const props = defineProps<{
  visible: boolean
  project?: Project
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [data: ProjectCreate | ProjectUpdate, isEdit: boolean]
}>()

const defaultForm: FormData = {
  name: '',
  description: '',
  source: 'local',
  local_path: '',
  git_url: '',
  git_branch: 'main',
  git_username: '',
  git_token: '',
  use_proxy: false,
  proxy_url: '',
}

const form = ref<FormData>({ ...defaultForm })

const isEdit = computed(() => !!props.project)

const isValid = computed(() => {
  if (!form.value.name.trim()) return false
  
  if (props.project) {
    // 编辑模式只需要名称
    return true
  }
  
  // 创建模式需要验证路径
  if (form.value.source === 'local') {
    return !!form.value.local_path.trim()
  } else {
    // Git 项目需要 URL
    if (!form.value.git_url.trim()) return false
    // 如果使用代理，需要填写代理地址
    if (form.value.use_proxy && !form.value.proxy_url.trim()) return false
    return true
  }
})

// 监听 visible 变化，初始化表单
watch(() => props.visible, (visible) => {
  if (visible) {
    if (props.project) {
      // 编辑模式，填充数据
      form.value = {
        name: props.project.name,
        description: props.project.description || '',
        source: props.project.source,
        local_path: props.project.source === 'local' ? props.project.path : '',
        git_url: props.project.git_info?.url || '',
        git_branch: props.project.git_info?.branch || 'main',
        git_username: '',
        git_token: '',
        use_proxy: props.project.git_info?.use_proxy || false,
        proxy_url: props.project.git_info?.proxy_url || '',
      }
    } else {
      // 创建模式，重置表单
      form.value = { ...defaultForm }
    }
  }
})

function handleClose() {
  emit('update:visible', false)
}

function handleSave() {
  if (!isValid.value) return
  
  if (props.project) {
    // 编辑模式
    const data: ProjectUpdate = {
      name: form.value.name.trim(),
      description: form.value.description.trim() || undefined,
    }
    emit('save', data, true)
  } else {
    // 创建模式
    const data: ProjectCreate = {
      name: form.value.name.trim(),
      description: form.value.description.trim() || undefined,
      source: form.value.source,
      local_path: form.value.source === 'local' ? form.value.local_path.trim() : undefined,
      git_url: form.value.source !== 'local' ? form.value.git_url.trim() : undefined,
      git_branch: form.value.source !== 'local' ? form.value.git_branch.trim() || 'main' : undefined,
      git_username: form.value.source !== 'local' ? form.value.git_username.trim() || undefined : undefined,
      git_token: form.value.source !== 'local' ? form.value.git_token.trim() || undefined : undefined,
      use_proxy: form.value.source !== 'local' ? form.value.use_proxy : undefined,
      proxy_url: form.value.source !== 'local' && form.value.use_proxy ? form.value.proxy_url.trim() : undefined,
    }
    emit('save', data, false)
  }
}
</script>

<style scoped>
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
  width: 500px;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
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
  color: #333;
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  cursor: pointer;
  border-radius: 4px;
  color: #666;
}

.btn-close:hover {
  background: #f5f5f5;
}

.dialog-body {
  padding: 20px;
  overflow-y: auto;
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

.form-group .required {
  color: #f44336;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #2196f3;
}

.form-group input:disabled,
.form-group textarea:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.form-group .hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #999;
}

.form-divider {
  height: 1px;
  background: #e0e0e0;
  margin: 20px 0;
}

.form-section-title {
  font-size: 14px;
  font-weight: 500;
  color: #666;
  margin-bottom: 16px;
}

.radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.radio-label:hover {
  background: #f5f5f5;
}

.radio-label input {
  width: auto;
  margin: 0;
}

.radio-label input:disabled + span {
  opacity: 0.5;
  cursor: not-allowed;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: normal;
}

.checkbox-label input {
  width: auto;
  margin: 0;
}

.dialog-footer {
  padding: 16px 20px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel,
.btn-save {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  border: 1px solid #ddd;
  background: white;
  color: #666;
}

.btn-cancel:hover {
  background: #f5f5f5;
}

.btn-save {
  border: none;
  background: #2196f3;
  color: white;
}

.btn-save:hover:not(:disabled) {
  background: #1976d2;
}

.btn-save:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>
