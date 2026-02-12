/**
 * 项目 API 服务
 */

import type { Project, ProjectCreate, ProjectUpdate, ProjectStatusInfo, PullResult } from '@/types/project'

const API_BASE = 'http://localhost:8000/api/v1'

/** 获取所有项目 */
export async function getProjects(): Promise<Project[]> {
  const response = await fetch(`${API_BASE}/projects`)
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to get projects: ${error}`)
  }
  const data = await response.json()
  return data.projects
}

/** 获取项目详情 */
export async function getProject(projectId: string): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`)
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to get project: ${error}`)
  }
  return await response.json()
}

/** 创建项目 */
export async function createProject(data: ProjectCreate): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to create project: ${error}`)
  }
  const result = await response.json()
  return result.project
}

/** 更新项目 */
export async function updateProject(projectId: string, data: ProjectUpdate): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to update project: ${error}`)
  }
  const result = await response.json()
  return result.project
}

/** 删除项目 */
export async function deleteProject(projectId: string, deleteFiles: boolean = false): Promise<void> {
  const response = await fetch(
    `${API_BASE}/projects/${projectId}?delete_files=${deleteFiles}`,
    { method: 'DELETE' }
  )
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to delete project: ${error}`)
  }
}

/** 拉取 Git 更新 */
export async function pullProject(projectId: string): Promise<PullResult> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/pull`, {
    method: 'POST',
  })
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to pull project: ${error}`)
  }
  return await response.json()
}

/** 获取项目状态 */
export async function getProjectStatus(projectId: string): Promise<ProjectStatusInfo> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/status`)
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to get project status: ${error}`)
  }
  return await response.json()
}

/** 获取项目文档列表 */
export async function getProjectDocs(projectId: string): Promise<{ files: Array<{ name: string; path: string }> }> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/docs`)
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to get project docs: ${error}`)
  }
  return await response.json()
}

/** 生成项目 Wiki */
export async function generateWiki(
  projectId: string,
  options?: Record<string, any>,
  model?: string,
  note?: string
): Promise<{ task_id: string; status: string }> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/wiki/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ options, model, note }),
  })
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to generate wiki: ${error}`)
  }
  return await response.json()
}
