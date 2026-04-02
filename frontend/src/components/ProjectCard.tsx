import { useNavigate } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { Project } from '@/types/models'
import { ChevronRight, Github, GitlabIcon } from 'lucide-react'

function extractRepoName(url: string): string {
  try {
    const parts = new URL(url).pathname.split('/').filter(Boolean)
    return parts.slice(-2).join('/')
  } catch {
    return url
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

const sourceColors: Record<string, string> = {
  sentry: 'bg-violet-50 text-violet-700 border-violet-200',
  cloudwatch: 'bg-orange-50 text-orange-700 border-orange-200',
  datadog: 'bg-purple-50 text-purple-700 border-purple-200',
}

const platformIcon: Record<string, React.ReactNode> = {
  github: <Github className="h-3.5 w-3.5" />,
  gitlab: <GitlabIcon className="h-3.5 w-3.5" />,
}

export function ProjectCard({ project }: { project: Project }) {
  const navigate = useNavigate()
  const repoName = extractRepoName(project.repo_url)

  return (
    <Card
      className="group flex cursor-pointer flex-col gap-3 border border-border bg-white p-4 transition-all hover:border-slate-300 hover:shadow-sm"
      onClick={() =>
        navigate(`/projects/${project.source}/${project.source_project_id}`)
      }
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={sourceColors[project.source] ?? 'bg-slate-50 text-slate-700'}>
            {project.source}
          </Badge>
          <Badge variant="outline" className="bg-slate-50 text-slate-600 border-slate-200">
            {platformIcon[project.repo_platform]}
            <span className="ml-1">{project.repo_platform}</span>
          </Badge>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </div>

      <div>
        <p className="truncate text-sm font-semibold text-foreground">{repoName}</p>
        <p className="mt-1 text-xs text-muted-foreground">{formatDate(project.created_at)}</p>
      </div>
    </Card>
  )
}
