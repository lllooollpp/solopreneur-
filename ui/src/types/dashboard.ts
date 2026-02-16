/**
 * 仪表盘类型定义
 */

export interface AgentStats {
  status: string
  uptime_seconds: number
  uptime_formatted: string
  current_model: string
  total_messages: number
  current_task: string | null
}

export interface ProjectInfo {
  id: string
  name: string
  path: string
  type: string
  updated_at: string
}

export interface ProjectStats {
  total: number
  recent: ProjectInfo[]
}

export interface AgentDistribution {
  total: number
  presets: number
  custom: number
  by_domain: Record<string, number>
  by_type: Record<string, number>
}

export interface SkillInfo {
  name: string
  description: string
  enabled: boolean
}

export interface SkillStats {
  total: number
  enabled: number
  list: SkillInfo[]
}

export interface TokenStats {
  total_used: number
  requests_today: number
  pool_size: number
  available_slots: number
}

export interface ActivityItem {
  time: string
  type: string
  title: string
  description: string | null
  status: string | null
}

export interface RecentActivity {
  tasks: ActivityItem[]
  messages: ActivityItem[]
  errors: ActivityItem[]
}

export interface SystemInfo {
  version: string
  python_version: string
  platform: string
  config_path: string
  workspace_path: string
}

export interface DashboardStats {
  agent: AgentStats
  projects: ProjectStats
  agents: AgentDistribution
  skills: SkillStats
  tokens: TokenStats
  activity: RecentActivity
  system: SystemInfo
}

export interface HealthCheck {
  status: string
  components: Record<string, string>
  timestamp: string
}

export interface UsageSummary {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  avg_duration_ms: number
  stream_calls: number
}

export interface TaskSummary {
  total: number
  by_status: Record<string, number>
}

export interface MetricsSnapshot {
  usage: UsageSummary
  tasks: TaskSummary
}

export interface UsageDailyRow {
  day: string
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  avg_duration_ms: number
}

export interface UsageDailyResponse {
  days: number
  rows: UsageDailyRow[]
}

export interface TaskDailyRow {
  day: string
  status: string
  count: number
}

export interface TaskDailyResponse {
  days: number
  rows: TaskDailyRow[]
}
