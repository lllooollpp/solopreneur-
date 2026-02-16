/**
 * 项目相关类型定义
 */

/** 项目来源类型 */
export type ProjectSource = 'local' | 'github' | 'gitlab' | 'git'

/** 项目状态 */
export type ProjectStatus = 'active' | 'archived' | 'error'

/** Git 仓库信息 */
export interface GitInfo {
  url: string
  branch: string
  last_commit?: string
  last_sync?: string
  use_proxy?: boolean
  proxy_url?: string
}

/** 项目对象 */
export interface Project {
  id: string
  name: string
  description?: string
  source: ProjectSource
  path: string
  git_info?: GitInfo
  session_id: string
  status: ProjectStatus
  created_at: string
  updated_at: string
}

/** 创建项目请求 */
export interface ProjectCreate {
  name: string
  description?: string
  source: ProjectSource
  local_path?: string      // 本地项目路径
  git_url?: string         // Git 仓库 URL
  git_branch?: string      // Git 分支，默认为 main
  git_username?: string    // Git 用户名（可选）
  git_token?: string       // Git Token/密码（可选）
  use_proxy?: boolean      // 是否使用代理
  proxy_url?: string       // 代理地址，如 http://127.0.0.1:7890
}

/** 更新项目请求 */
export interface ProjectUpdate {
  name?: string
  description?: string
  status?: ProjectStatus
}

/** 项目状态信息 */
export interface ProjectStatusInfo {
  project_id: string
  exists: boolean
  is_git_repo: boolean
  git_status?: string
  uncommitted_changes: boolean
}

/** Git 拉取结果 */
export interface PullResult {
  success: boolean
  message: string
  project_id: string
}
