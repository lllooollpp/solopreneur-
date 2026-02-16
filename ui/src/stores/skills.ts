import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 技能来源枚举
 */
export enum SkillSource {
  WORKSPACE = 'workspace',
  MANAGED = 'managed',
  BUNDLED = 'bundled'
}

/**
 * 技能项接口
 */
export interface SkillItem {
  name: string
  source: SkillSource
  enabled: boolean
  description: string
  variables: Record<string, string>
  overridden: boolean
}

/**
 * Skills Store
 * 管理技能配置
 */
export const useSkillsStore = defineStore('skills', () => {
  const skills = ref<SkillItem[]>([])
  const loading = ref(false)

  /**
   * 加载技能列表
   */
  async function loadSkills() {
    loading.value = true
    try {
      const response = await fetch('http://localhost:8000/api/config/skills')
      if (response.ok) {
        const data = await response.json()
        skills.value = data.skills || []
      } else {
        console.error('加载技能列表失败')
        skills.value = []
      }
    } catch (error) {
      console.error('加载技能列表失败:', error)
      skills.value = []
    } finally {
      loading.value = false
    }
  }

  /**
   * 切换技能启用状态
   */
  function toggleSkill(skillName: string) {
    const skill = skills.value.find(s => s.name === skillName)
    if (skill) {
      skill.enabled = !skill.enabled
    }
  }

  /**
   * 更新技能变量
   */
  function updateSkillVariables(skillName: string, variables: Record<string, string>) {
    const skill = skills.value.find(s => s.name === skillName)
    if (skill) {
      skill.variables = { ...skill.variables, ...variables }
    }
  }

  return {
    skills,
    loading,
    loadSkills,
    toggleSkill,
    updateSkillVariables
  }
})
