/**
 * 技能管理 API
 */
import apiClient from './client'
import type { SkillItem, SkillConfig } from '@/types/skill'

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
 * 获取 Agent 定义内容 (SOUL.md)
 */
export async function getAgentDefinition(): Promise<string> {
  const response = await apiClient.get<{ content: string }>('/api/config/agent')
  return response.content
}

/**
 * 更新 Agent 定义
 */
export async function updateAgentDefinition(content: string): Promise<void> {
  await apiClient.put('/api/config/agent', { content })
}
