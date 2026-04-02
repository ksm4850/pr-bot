import { StatusBadge } from '@/components/StatusBadge'
import type { Job } from '@/types/models'
import { cn } from '@/lib/utils'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

interface Props {
  job: Job
  selected: boolean
  onClick: () => void
}

export function JobListItem({ job, selected, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex w-full flex-col gap-1 rounded-md border px-3 py-2.5 text-left transition-colors',
        selected
          ? 'border-l-2 border-l-primary bg-accent border-accent'
          : 'border-transparent hover:bg-muted/50'
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <StatusBadge status={job.status} />
        <span className="text-xs text-muted-foreground">{timeAgo(job.created_at)}</span>
      </div>
      <p className="truncate text-sm font-medium text-foreground">{job.title}</p>
      {job.exception_type && (
        <p className="truncate text-xs font-mono text-muted-foreground">{job.exception_type}</p>
      )}
    </button>
  )
}
