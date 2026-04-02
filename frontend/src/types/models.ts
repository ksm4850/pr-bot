export type JobStatus = 'pending' | 'processing' | 'rate_limited' | 'done' | 'failed'
export type ErrorSource = 'sentry' | 'cloudwatch' | 'datadog'
export type RepoPlatform = 'github' | 'gitlab'
export type JobTaskType = 'tool_use' | 'message' | 'error' | 'status'

export interface Job {
  id: string
  status: JobStatus
  source: ErrorSource
  source_project_id: string | null
  source_issue_id: string
  title: string
  subtitle: string | null
  message: string | null
  level: string | null
  environment: string | null
  exception_type: string | null
  transaction: string | null
  filename: string | null
  lineno: number | null
  function: string | null
  stacktrace: string | null
  work_branch: string | null
  error_log: string | null
  rate_limited_until: string | null
  input_tokens: number
  output_tokens: number
  retry_count: number
  source_url: string | null
  raw_payload: string | null
  created_at: string
  updated_at: string
}

export interface JobTask {
  id: string
  job_id: string
  sequence: number
  type: JobTaskType
  label: string | null
  content: string | null
  created_at: string
}

export interface Project {
  id: string
  source: string
  source_project_id: string
  repo_url: string
  repo_platform: RepoPlatform
  repo_token: string | null
  created_at: string
  updated_at: string
}

export interface WorkerStatus {
  running: boolean
  current_job_id: string | null
  processed_count: number
  started_at: string | null
}

export interface StackFrame {
  filename: string
  lineno: number
  function: string
  context_line: string | null
  pre_context: string[]
  post_context: string[]
  in_app: boolean
}
