<template>
  <div class="project-sidebar">
    <div class="sidebar-header">
      <h3>📁 项目列表</h3>
      <button class="btn-add" @click="showCreateDialog = true" title="新建项目">+</button>
    </div>
    
    <div class="project-list">
      <div
        v-for="project in projects"
        :key="project.id"
        :class="['project-item', { active: currentProjectId === project.id }]"
        @click="selectProject(project)"
      >
        <div class="project-icon">
          {{ getProjectIcon(project.source) }}
        </div>
        <div class="project-info">
          <div class="project-name">{{ project.name }}</div>
          <div class="project-meta">
            <span class="project-source">{{ formatSource(project.source) }}</span>
            <span v-if="project.git_info?.last_sync" class="last-sync">
              {{ formatDate(project.git_info.last_sync) }}
            </span>
          </div>
        </div>
        <div class="project-actions">
          <button 
            v-if="project.source !== 'local'"
            class="btn-action"
            @click.stop="pullProjectAction(project.id)"
            title="拉取更新"
          >
            🔄
          </button>
          <button class="btn-action" @click.stop="editProject(project)" title="编辑">✏️</button>
          <button 
            v-if="project.id !== 'default'"
            class="btn-action delete"
            @click.stop="confirmDelete(project)"
            title="删除"
          >
            🗑️
          </button>
        </div>
      </div>
    </div>
    
    <!-- 创建/编辑项目对话框 -->
    <ProjectDialog
      v-model:visible="showCreateDialog"
      :project="editingProject"
      @save="handleSaveProject"
    />
    
    <!-- 删除确认对话框 -->
    <ConfirmDialog
      v-model:visible="showDeleteDialog"
      title="删除项目"
      :message="deleteMessage"
      @confirm="handleDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Project, ProjectCreate, ProjectUpdate } from '@/types/project'
import { getProjects, createProject, updateProject, deleteProject, pullProject } from '@/services/projectApi'
import ProjectDialog from './ProjectDialog.vue'
import ConfirmDialog from './ConfirmDialog.vue'

const props = defineProps<{
  currentProjectId?: string
}>()

const emit = defineEmits<{
  select: [project: Project]
}>()

const projects = ref<Project[]>([])
const showCreateDialog = ref(false)
const showDeleteDialog = ref(false)
const editingProject = ref<Project | undefined>(undefined)
const deletingProject = ref<Project | null>(null)
const deleteMessage = ref('')

// 加载项目列表
async function loadProjects() {
  try {
    projects.value = await getProjects()
  } catch (error) {
    console.error('Failed to load projects:', error)
    alert('加载项目列表失败')
  }
}

// 选择项目
function selectProject(project: Project) {
  emit('select', project)
}

// 编辑项目
function editProject(project: Project) {
  editingProject.value = project
  showCreateDialog.value = true
}

// 保存项目（创建或更新）
async function handleSaveProject(data: ProjectCreate | ProjectUpdate, isEdit: boolean) {
  try {
    if (isEdit && editingProject.value) {
      await updateProject(editingProject.value.id, data as ProjectUpdate)
    } else {
      await createProject(data as ProjectCreate)
    }
    await loadProjects()
    showCreateDialog.value = false
    editingProject.value = undefined
  } catch (error) {
    console.error('Failed to save project:', error)
    alert(isEdit ? '更新项目失败' : '创建项目失败')
  }
}

// 确认删除
function confirmDelete(project: Project) {
  deletingProject.value = project
  deleteMessage.value = `确定要删除项目 "${project.name}" 吗？\n\n此操作不可恢复。`
  showDeleteDialog.value = true
}

// 执行删除
async function handleDelete() {
  if (!deletingProject.value) return
  
  try {
    await deleteProject(deletingProject.value.id, false)
    await loadProjects()
    showDeleteDialog.value = false
    deletingProject.value = null
  } catch (error) {
    console.error('Failed to delete project:', error)
    alert('删除项目失败')
  }
}

// 拉取项目更新
async function pullProjectAction(projectId: string) {
  try {
    const result = await pullProject(projectId)
    alert(result.message || '拉取成功')
    await loadProjects()
  } catch (error) {
    console.error('Failed to pull project:', error)
    alert('拉取更新失败')
  }
}

// 获取项目图标
function getProjectIcon(source: string): string {
  const icons: Record<string, string> = {
    'local': '📁',
    'github': '🐙',
    'gitlab': '🦊',
    'git': '📦',
  }
  return icons[source] || '📁'
}

// 格式化来源
function formatSource(source: string): string {
  const labels: Record<string, string> = {
    'local': '本地',
    'github': 'GitHub',
    'gitlab': 'GitLab',
    'git': 'Git',
  }
  return labels[source] || source
}

// 格式化日期
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  // 小于1小时显示分钟
  if (diff < 3600000) {
    const mins = Math.floor(diff / 60000)
    return mins < 1 ? '刚刚' : `${mins}分钟前`
  }
  // 小于24小时显示小时
  if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  }
  // 否则显示日期
  return date.toLocaleDateString('zh-CN')
}

onMounted(() => {
  loadProjects()
})

defineExpose({
  refresh: loadProjects
})
</script>

<style scoped>
.project-sidebar {
  width: 280px;
  background: #fff;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.btn-add {
  width: 28px;
  height: 28px;
  border: none;
  background: #4caf50;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  transition: background 0.2s;
}

.btn-add:hover {
  background: #45a049;
}

.project-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.project-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
}

.project-item:hover {
  background: #f5f5f5;
}

.project-item.active {
  background: #e3f2fd;
}

.project-icon {
  font-size: 24px;
  margin-right: 12px;
  width: 32px;
  text-align: center;
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-name {
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.project-source {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
}

.last-sync {
  color: #999;
}

.project-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.project-item:hover .project-actions {
  opacity: 1;
}

.btn-action {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-action:hover {
  background: #e0e0e0;
}

.btn-action.delete:hover {
  background: #ffebee;
}
</style>
