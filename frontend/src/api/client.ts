import type { Job, JobTask, Project, WorkerStatus, JobStatus } from '@/types/models'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${body}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// Projects
export const listProjects = (source?: string) =>
  fetchJSON<Project[]>(`/projects${source ? `?source=${source}` : ''}`)

export const createProject = (data: {
  source: string
  source_project_id: string
  repo_url: string
  repo_platform: string
  repo_token?: string
}) => fetchJSON<Project>('/projects', { method: 'POST', body: JSON.stringify(data) })

export const deleteProject = (source: string, sourceProjectId: string) =>
  fetchJSON<void>(`/projects/${source}/${sourceProjectId}`, { method: 'DELETE' })

// Jobs
export const listJobs = (params?: {
  status?: JobStatus
  source_project_id?: string
  page?: number
  limit?: number
}) => {
  const qs = new URLSearchParams()
  if (params?.status) qs.set('status', params.status)
  if (params?.source_project_id) qs.set('source_project_id', params.source_project_id)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.limit) qs.set('limit', String(params.limit))
  const q = qs.toString()
  return fetchJSON<Job[]>(`/jobs${q ? `?${q}` : ''}`)
}

export const getJob = (id: string) => fetchJSON<Job>(`/jobs/${id}`)

export const listJobTasks = (jobId: string) =>
  fetchJSON<JobTask[]>(`/jobs/${jobId}/tasks`)

// Worker
export const getWorkerStatus = () => fetchJSON<WorkerStatus>('/worker/status')

export const startWorker = () =>
  fetchJSON<{ ok: boolean }>('/worker/start', { method: 'POST' })

export const stopWorker = () =>
  fetchJSON<{ ok: boolean }>('/worker/stop', { method: 'POST' })

// Settings
export interface SettingsData {
  dooray_webhook_url: string | null
  notification_enabled: boolean
}

export const getSettings = () => fetchJSON<SettingsData>('/settings')

export const updateSettings = (data: Partial<SettingsData>) =>
  fetchJSON<SettingsData>('/settings', { method: 'PUT', body: JSON.stringify(data) })

export const testNotification = (webhookUrl: string) =>
  fetchJSON<{ ok: boolean }>('/settings/test-notification', {
    method: 'POST',
    body: JSON.stringify({ webhook_url: webhookUrl }),
  })
