import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { JobListItem } from '@/components/JobListItem'
import { JobDetail } from '@/components/JobDetail'
import { listJobs } from '@/api/client'
import type { Job, JobStatus } from '@/types/models'
import { ArrowLeft, Inbox } from 'lucide-react'

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'done', label: 'Done' },
  { value: 'failed', label: 'Failed' },
]

export function ProjectDetailPage() {
  const { source, sourceProjectId } = useParams<{
    source: string
    sourceProjectId: string
  }>()
  const navigate = useNavigate()

  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!sourceProjectId) return
    try {
      const result = await listJobs({
        source_project_id: sourceProjectId,
        status: statusFilter === 'all' ? undefined : (statusFilter as JobStatus),
        limit: 100,
      })
      setJobs(result)
      if (result.length > 0 && !selectedId) {
        setSelectedId(result[0].id)
      }
    } finally {
      setLoading(false)
    }
  }, [sourceProjectId, statusFilter, selectedId])

  useEffect(() => {
    setLoading(true)
    refresh()
  }, [refresh])

  // Auto-refresh
  useEffect(() => {
    const id = setInterval(refresh, 10000)
    return () => clearInterval(id)
  }, [refresh])

  const selectedJob = jobs.find((j) => j.id === selectedId)

  return (
    <div>
      {/* Back button */}
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 gap-1.5 text-muted-foreground"
        onClick={() => navigate('/')}
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Projects
      </Button>

      <div className="mb-4">
        <h1 className="text-lg font-semibold text-foreground">
          {source} / {sourceProjectId}
        </h1>
      </div>

      <div className="flex gap-4" style={{ height: 'calc(100vh - 220px)' }}>
        {/* Left sidebar: Job list */}
        <div className="flex w-80 shrink-0 flex-col rounded-lg border border-border bg-white">
          <div className="border-b border-border p-3">
            <Tabs value={statusFilter} onValueChange={setStatusFilter}>
              <TabsList className="w-full">
                {STATUS_FILTERS.map((f) => (
                  <TabsTrigger key={f.value} value={f.value} className="text-xs">
                    {f.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>

          <ScrollArea className="flex-1">
            <div className="space-y-1 p-2">
              {loading ? (
                <p className="py-8 text-center text-sm text-muted-foreground">Loading...</p>
              ) : jobs.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                  <Inbox className="h-8 w-8 opacity-50" />
                  <p className="text-sm">No jobs found</p>
                </div>
              ) : (
                jobs.map((job) => (
                  <JobListItem
                    key={job.id}
                    job={job}
                    selected={job.id === selectedId}
                    onClick={() => setSelectedId(job.id)}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Right main: Job detail */}
        <div className="flex-1 overflow-y-auto rounded-lg border border-border bg-white p-6">
          {selectedJob ? (
            <JobDetail job={selectedJob} />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Select a job to view details
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
