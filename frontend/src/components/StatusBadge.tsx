import { Badge } from '@/components/ui/badge'
import type { JobStatus } from '@/types/models'

const statusConfig: Record<JobStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; className: string }> = {
  pending: { label: 'Pending', variant: 'secondary', className: 'bg-slate-100 text-slate-700 border-slate-200' },
  processing: { label: 'Processing', variant: 'default', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  rate_limited: { label: 'Rate Limited', variant: 'outline', className: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  done: { label: 'Done', variant: 'default', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  failed: { label: 'Failed', variant: 'destructive', className: 'bg-red-50 text-red-700 border-red-200' },
}

export function StatusBadge({ status }: { status: JobStatus }) {
  const config = statusConfig[status]
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  )
}
