import { useState } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { StackFrame } from '@/types/models'
import { ChevronDown, ChevronRight } from 'lucide-react'

function FrameItem({ frame, index }: { frame: StackFrame; index: number }) {
  const [open, setOpen] = useState(index === 0)

  const hasContext = frame.context_line || frame.pre_context.length > 0 || frame.post_context.length > 0

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted/50">
        {hasContext ? (
          open ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <span className="h-3.5 w-3.5 shrink-0" />
        )}
        <span className="font-mono text-xs">
          <span className="text-muted-foreground">{frame.filename}</span>
          <span className="text-muted-foreground">:</span>
          <span className="font-semibold text-foreground">{frame.lineno}</span>
          <span className="text-muted-foreground"> in </span>
          <span className="text-blue-600">{frame.function}</span>
        </span>
      </CollapsibleTrigger>
      {hasContext && (
        <CollapsibleContent>
          <div className="ml-6 overflow-x-auto rounded bg-slate-50 border border-border">
            <pre className="text-xs leading-5">
              {frame.pre_context.map((line, i) => (
                <div key={`pre-${i}`} className="px-3 text-muted-foreground">
                  <span className="mr-3 inline-block w-8 text-right text-slate-400">
                    {frame.lineno - frame.pre_context.length + i}
                  </span>
                  {line}
                </div>
              ))}
              {frame.context_line && (
                <div className="bg-red-50 px-3 font-medium text-red-800">
                  <span className="mr-3 inline-block w-8 text-right text-red-400">
                    {frame.lineno}
                  </span>
                  {frame.context_line}
                </div>
              )}
              {frame.post_context.map((line, i) => (
                <div key={`post-${i}`} className="px-3 text-muted-foreground">
                  <span className="mr-3 inline-block w-8 text-right text-slate-400">
                    {frame.lineno + 1 + i}
                  </span>
                  {line}
                </div>
              ))}
            </pre>
          </div>
        </CollapsibleContent>
      )}
    </Collapsible>
  )
}

export function StacktraceView({ stacktrace }: { stacktrace: string }) {
  let frames: StackFrame[]
  try {
    frames = JSON.parse(stacktrace)
  } catch {
    return <pre className="text-xs text-muted-foreground whitespace-pre-wrap">{stacktrace}</pre>
  }

  if (!Array.isArray(frames) || frames.length === 0) {
    return <p className="text-sm text-muted-foreground">No stacktrace available</p>
  }

  return (
    <div className="space-y-0.5">
      {frames.map((frame, i) => (
        <FrameItem key={i} frame={frame} index={i} />
      ))}
    </div>
  )
}
