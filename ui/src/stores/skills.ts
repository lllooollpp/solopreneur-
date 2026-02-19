import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getSkills as fetchSkillsApi,
  getSkillContent as fetchSkillContentApi,
  createSkill as createSkillApi,
  updateSkillContent as updateSkillContentApi,
  deleteSkill as deleteSkillApi,
} from '@/api/skills'
import type { SkillCreatePayload } from '@/types/skill'

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
      const data = await fetchSkillsApi()
      skills.value = data || []
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

  /**
   * 获取技能内容
   */
  async function getSkillContent(skillName: string): Promise<string> {
    const res = await fetchSkillContentApi(skillName)
    return res.content
  }

  /**
   * 创建新技能
   */
  async function createSkill(payload: SkillCreatePayload) {
    await createSkillApi(payload)
    await loadSkills()
  }

  /**
   * 更新技能内容
   */
  async function updateSkillContent(skillName: string, content: string) {
    await updateSkillContentApi(skillName, content)
    await loadSkills()
  }

  /**
   * 删除技能
   */
  async function deleteSkill(skillName: string) {
    await deleteSkillApi(skillName)
    await loadSkills()
  }

  return {
    skills,
    loading,
    loadSkills,
    toggleSkill,
    updateSkillVariables,
    getSkillContent,
    createSkill,
    updateSkillContent,
    deleteSkill,
  }
})
