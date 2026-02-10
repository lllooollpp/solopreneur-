<template>
  <div class="skill-card">
    <div class="card-header">
      <div class="title-area">
        <h4 class="skill-name">{{ skill.name }}</h4>
        <span :class="['source-badge', skill.source]">
          {{ sourceLabel }}
        </span>
        <span v-if="skill.overridden" class="overridden-badge">重写</span>
      </div>
      <label class="toggle-switch">
        <input
          type="checkbox"
          :checked="skill.enabled"
          @change="$emit('toggle', skill.name)"
        />
        <span class="slider"></span>
      </label>
    </div>
    
    <p class="description">{{ skill.description }}</p>
    
    <!-- 技能变量配置 -->
    <div v-if="Object.keys(skill.variables).length > 0" class="variables-section">
      <h5>环境变量</h5>
      <div
        v-for="(value, key) in skill.variables"
        :key="key"
        class="variable-item"
      >
        <label>{{ key }}</label>
        <input
          type="text"
          :value="value"
          @input="updateVariable(key, ($event.target as HTMLInputElement).value)"
          :placeholder="`输入 ${key} 的值`"
        />
      </div>
    </div>
    
    <div class="card-actions">
      <button class="btn-secondary" @click="$emit('edit', skill.name)">
        编辑配置
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SkillItem } from '@/types/skill'
import { SkillSource } from '@/types/skill'

const props = defineProps<{
  skill: SkillItem
}>()

const emit = defineEmits<{
  toggle: [name: string]
  edit: [name: string]
  updateVariables: [name: string, variables: Record<string, string>]
}>()

const sourceLabel = computed(() => {
  switch (props.skill.source) {
    case SkillSource.WORKSPACE: return 'Workspace'
    case SkillSource.MANAGED: return 'Managed'
    case SkillSource.BUNDLED: return 'Bundled'
    default: return props.skill.source
  }
})

function updateVariable(key: string, value: string) {
  emit('updateVariables', props.skill.name, {
    ...props.skill.variables,
    [key]: value
  })
}
</script>

<style scoped>
.skill-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 1rem;
  background: white;
  transition: all 0.2s;
}

.skill-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.8rem;
}

.title-area {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  flex: 1;
}

.skill-name {
  margin: 0;
  color: #2c3e50;
  font-size: 1.1rem;
}

.source-badge,
.overridden-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
}

.source-badge.workspace {
  background: #e3f2fd;
  color: #1976d2;
}

.source-badge.managed {
  background: #f3e5f5;
  color: #7b1fa2;
}

.source-badge.bundled {
  background: #e8f5e9;
  color: #388e3c;
}

.overridden-badge {
  background: #fff3e0;
  color: #f57c00;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 24px;
  flex-shrink: 0;
}

.toggle-switch input {
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

.description {
  color: #616161;
  font-size: 0.9rem;
  margin-bottom: 1rem;
  line-height: 1.4;
}

.variables-section {
  margin-bottom: 1rem;
  padding: 0.8rem;
  background: #f5f5f5;
  border-radius: 4px;
}

.variables-section h5 {
  margin: 0 0 0.5rem 0;
  color: #2c3e50;
  font-size: 0.9rem;
}

.variable-item {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.5rem;
}

.variable-item:last-child {
  margin-bottom: 0;
}

.variable-item label {
  font-size: 0.85rem;
  font-weight: 500;
  color: #616161;
}

.variable-item input {
  padding: 0.4rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.variable-item input:focus {
  outline: none;
  border-color: #1976d2;
}

.card-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn-secondary {
  background: white;
  color: #1976d2;
  border: 1px solid #1976d2;
  padding: 0.4rem 1rem;
  border-radius: 4px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: #1976d2;
  color: white;
}
</style>
