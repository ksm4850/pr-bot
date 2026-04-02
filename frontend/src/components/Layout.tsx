import { Outlet } from 'react-router-dom'
import { WorkerControl } from '@/components/WorkerControl'
import { Bot } from 'lucide-react'

export function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-white">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <a href="/" className="flex items-center gap-2 text-foreground no-underline">
            <Bot className="h-5 w-5" />
            <span className="text-lg font-bold tracking-tight">PR-Bot</span>
          </a>
          <WorkerControl />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
