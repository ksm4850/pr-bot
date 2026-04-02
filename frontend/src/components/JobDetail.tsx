import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { StatusBadge } from '@/components/StatusBadge'
import { StacktraceView } from '@/components/StacktraceView'
import { TaskTimeline } from '@/components/TaskTimeline'
import { listJobTasks } from '@/api/client'
import type { Job, JobTask } from '@/types/models'
import { FileCode, Coins, GitBranch, ExternalLink } from 'lucide-react'

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="w-28 shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  )
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function JobDetail({ job }: { job: Job }) {
  const [tasks, setTasks] = useState<JobTask[]>([])

  useEffect(() => {
    listJobTasks(job.id).then(setTasks).catch(() => {})
  }, [job.id])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-foreground">{job.title}</h2>
          {job.subtitle && (
            <p className="text-sm text-muted-foreground">{job.subtitle}</p>
          )}
        </div>
        <StatusBadge status={job.status} />
      </div>

      {/* Error Info */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <FileCode className="h-4 w-4" />
            Error Info
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <InfoRow label="Exception" value={job.exception_type} />
          <InfoRow label="Message" value={job.message} />
          <InfoRow
            label="Location"
            value={
              job.filename && (
                <span className="font-mono text-xs">
                  {job.filename}
                  {job.lineno != null && `:${job.lineno}`}
                  {job.function && ` in ${job.function}`}
                </span>
              )
            }
          />
          <InfoRow label="Transaction" value={job.transaction} />
          <InfoRow label="Environment" value={job.environment && (
            <Badge variant="outline" className="text-xs">{job.environment}</Badge>
          )} />
          <InfoRow label="Level" value={job.level} />
          {job.source_url && (
            <InfoRow
              label="Source"
              value={
                <a
                  href={job.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                >
                  View in {job.source}
                  <ExternalLink className="h-3 w-3" />
                </a>
              }
            />
          )}
        </CardContent>
      </Card>

      {/* Stacktrace */}
      {job.stacktrace && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Stacktrace</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <StacktraceView stacktrace={job.stacktrace} />
          </CardContent>
        </Card>
      )}

      {/* Result */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Coins className="h-4 w-4" />
            Result
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {job.work_branch && (
            <InfoRow
              label="Branch"
              value={
                <span className="inline-flex items-center gap-1 font-mono text-xs">
                  <GitBranch className="h-3 w-3" />
                  {job.work_branch}
                </span>
              }
            />
          )}
          <InfoRow
            label="Tokens"
            value={`${formatTokens(job.input_tokens)} in / ${formatTokens(job.output_tokens)} out`}
          />
          <InfoRow label="Retries" value={job.retry_count > 0 ? String(job.retry_count) : null} />
          {job.error_log && (
            <>
              <Separator className="my-2" />
              <pre className="max-h-40 overflow-auto rounded bg-red-50 p-3 text-xs text-red-800 whitespace-pre-wrap">
                {job.error_log}
              </pre>
            </>
          )}
        </CardContent>
      </Card>

      {/* Agent Tasks */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            Agent Tasks
            {tasks.length > 0 && (
              <Badge variant="secondary" className="text-xs">{tasks.length}</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <TaskTimeline tasks={tasks} />
        </CardContent>
      </Card>
    </div>
  )
}
