/**
 * 技能相关类型定义
 */

export enum SkillSource {
  WORKSPACE = 'workspace',
  MANAGED = 'managed',
  BUNDLED = 'bundled'
}

export interface SkillItem {
  name: string
  source: SkillSource
  enabled: boolean
  description: string
  variables: Record<string, string>
  overridden: boolean
}

export interface SkillConfig {
  skills: SkillItem[]
}

export interface SkillCreatePayload {
  name: string
  description: string
  content: string
}

export interface SkillContentResponse {
  name: string
  content: string
}
