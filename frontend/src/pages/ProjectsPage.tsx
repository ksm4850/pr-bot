import { useEffect, useState, useCallback } from 'react'
import { Badge } from '@/components/ui/badge'
import { ProjectCard } from '@/components/ProjectCard'
import { CreateProjectModal } from '@/components/CreateProjectModal'
import { listProjects } from '@/api/client'
import type { Project } from '@/types/models'
import { FolderKanban } from 'lucide-react'

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setProjects(await listProjects())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-foreground">Projects</h1>
          <Badge variant="secondary">{projects.length}</Badge>
        </div>
        <CreateProjectModal onCreated={refresh} />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
          Loading...
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border py-20">
          <FolderKanban className="h-10 w-10 text-muted-foreground/50" />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">No projects yet</p>
            <p className="text-sm text-muted-foreground">
              Create a project to start receiving error webhooks
            </p>
          </div>
          <CreateProjectModal onCreated={refresh} />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}
    </div>
  )
}
