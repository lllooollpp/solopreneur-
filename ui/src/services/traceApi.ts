/**
 * Trace Events API — 获取持久化的调用链和原始事件流
 */

const API_BASE = 'http://localhost:8000/api/v1'

export interface TraceRequest {
  request_id: string
  started_at: string
  ended_at: string
  event_count: number
}

export interface TraceEventRecord {
  id: number
  session_key: string
  request_id: string
  project_id: string | null
  event_type: string
  agent_name: string | null
  data: Record<string, any>
  created_at: string
}

/** 列出某 session 下的所有请求（历史列表） */
export async function listTraceRequests(sessionKey: string): Promise<TraceRequest[]> {
  const response = await fetch(`${API_BASE}/traces/${encodeURIComponent(sessionKey)}`)
  if (!response.ok) {
    console.warn('Failed to list trace requests:', response.statusText)
    return []
  }
  const data = await response.json()
  return data.requests || []
}

/** 获取某 session（或某次请求）的全部 trace 事件 */
export async function getTraceEvents(
  sessionKey: string,
  requestId?: string,
  limit: number = 500,
): Promise<TraceEventRecord[]> {
  const params = new URLSearchParams()
  if (requestId) params.set('request_id', requestId)
  params.set('limit', String(limit))

  const url = `${API_BASE}/traces/${encodeURIComponent(sessionKey)}/events?${params}`
  const response = await fetch(url)
  if (!response.ok) {
    console.warn('Failed to get trace events:', response.statusText)
    return []
  }
  const data = await response.json()
  return data.events || []
}

/** 删除 trace 事件 */
export async function deleteTraceEvents(
  sessionKey: string,
  requestId?: string,
): Promise<number> {
  const params = new URLSearchParams()
  if (requestId) params.set('request_id', requestId)

  const url = `${API_BASE}/traces/${encodeURIComponent(sessionKey)}?${params}`
  const response = await fetch(url, { method: 'DELETE' })
  if (!response.ok) {
    console.warn('Failed to delete trace events:', response.statusText)
    return 0
  }
  const data = await response.json()
  return data.deleted || 0
}
