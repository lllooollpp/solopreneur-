/**
 * 技能管理 API
 */
import apiClient from './client'
import type { SkillItem, SkillConfig, SkillCreatePayload, SkillContentResponse } from '@/types/skill'

/**
 * 获取所有技能列表
 */
export async function getSkills(): Promise<SkillItem[]> {
  const response = await apiClient.get<SkillConfig>('/api/config/skills')
  return response.skills
}

/**
 * 更新技能配置
 */
export async function updateSkill(skillName: string, updates: Partial<SkillItem>): Promise<void> {
  await apiClient.put(`/api/config/skills/${skillName}`, updates)
}

/**
 * 切换技能启用状态
 */
export async function toggleSkillEnabled(skillName: string, enabled: boolean): Promise<void> {
  await apiClient.put(`/api/config/skills/${skillName}`, { enabled })
}

/**
 * 更新技能变量
 */
export async function updateSkillVariables(
  skillName: string,
  variables: Record<string, string>
): Promise<void> {
  await apiClient.put(`/api/config/skills/${skillName}/variables`, { variables })
}

/**
 * 获取技能内容
 */
export async function getSkillContent(skillName: string): Promise<SkillContentResponse> {
  return await apiClient.get<SkillContentResponse>(`/api/config/skills/${skillName}/content`)
}

/**
 * 创建新技能
 */
export async function createSkill(payload: SkillCreatePayload): Promise<void> {
  await apiClient.post('/api/config/skills', payload)
}

/**
 * 更新技能内容
 */
export async function updateSkillContent(skillName: string, content: string): Promise<void> {
  await apiClient.put(`/api/config/skills/${skillName}/content`, { content })
}

/**
 * 删除技能
 */
export async function deleteSkill(skillName: string): Promise<void> {
  await apiClient.delete(`/api/config/skills/${skillName}`)
}

