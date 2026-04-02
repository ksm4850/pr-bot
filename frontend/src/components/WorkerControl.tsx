import { useEffect, useState, useCallback } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { getWorkerStatus, startWorker, stopWorker } from '@/api/client'
import type { WorkerStatus } from '@/types/models'
import { Play, Square } from 'lucide-react'

export function WorkerControl() {
  const [status, setStatus] = useState<WorkerStatus | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setStatus(await getWorkerStatus())
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [refresh])

  const toggle = async () => {
    setLoading(true)
    try {
      if (status?.running) {
        await stopWorker()
      } else {
        await startWorker()
      }
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  const running = status?.running ?? false

  return (
    <div className="flex items-center gap-2">
      <Badge
        variant="outline"
        className={
          running
            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
            : 'bg-slate-100 text-slate-500 border-slate-200'
        }
      >
        <span
          className={`mr-1.5 inline-block h-2 w-2 rounded-full ${
            running ? 'bg-emerald-500' : 'bg-slate-400'
          }`}
        />
        {running ? 'Running' : 'Stopped'}
      </Badge>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={toggle}
        disabled={loading}
      >
        {running ? <Square className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
      </Button>
    </div>
  )
}
