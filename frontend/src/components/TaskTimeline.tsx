import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { JobTask, JobTaskType } from '@/types/models'
import { ChevronDown, ChevronRight, MessageSquare, Terminal, AlertCircle, Info } from 'lucide-react'

const typeConfig: Record<JobTaskType, { icon: React.ReactNode; className: string }> = {
  tool_use: {
    icon: <Terminal className="h-3.5 w-3.5" />,
    className: 'bg-blue-50 text-blue-700 border-blue-200',
  },
  message: {
    icon: <MessageSquare className="h-3.5 w-3.5" />,
    className: 'bg-slate-50 text-slate-700 border-slate-200',
  },
  error: {
    icon: <AlertCircle className="h-3.5 w-3.5" />,
    className: 'bg-red-50 text-red-700 border-red-200',
  },
  status: {
    icon: <Info className="h-3.5 w-3.5" />,
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function TaskItem({ task }: { task: JobTask }) {
  const [open, setOpen] = useState(false)
  const config = typeConfig[task.type]
  const hasContent = !!task.content

  return (
    <div className="relative flex gap-3 pb-4">
      {/* Timeline line */}
      <div className="absolute left-[7px] top-5 bottom-0 w-px bg-border" />

      {/* Dot */}
      <div className="relative z-10 mt-1.5 h-3.5 w-3.5 shrink-0 rounded-full border-2 border-border bg-white" />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger className="flex w-full items-center gap-2 text-left">
            {hasContent && (
              open ? <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
            )}
            <Badge variant="outline" className={`${config.className} gap-1`}>
              {config.icon}
              {task.type}
            </Badge>
            <span className="truncate text-sm text-foreground">{task.label ?? task.type}</span>
            <span className="ml-auto shrink-0 text-xs text-muted-foreground">
              {formatTime(task.created_at)}
            </span>
          </CollapsibleTrigger>
          {hasContent && (
            <CollapsibleContent>
              <pre className="mt-2 max-h-60 overflow-auto rounded border border-border bg-slate-50 p-3 text-xs whitespace-pre-wrap">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(task.content!), null, 2)
                  } catch {
                    return task.content
                  }
                })()}
              </pre>
            </CollapsibleContent>
          )}
        </Collapsible>
      </div>
    </div>
  )
}

export function TaskTimeline({ tasks }: { tasks: JobTask[] }) {
  if (tasks.length === 0) {
    return <p className="text-sm text-muted-foreground">No agent tasks yet</p>
  }

  return (
    <div>
      {tasks.map((task) => (
        <TaskItem key={task.id} task={task} />
      ))}
    </div>
  )
}
