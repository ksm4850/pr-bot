import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { createProject } from '@/api/client'
import { Plus } from 'lucide-react'

interface Props {
  onCreated: () => void
}

export function CreateProjectModal({ onCreated }: Props) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    source: 'sentry',
    source_project_id: '',
    repo_url: '',
    repo_platform: 'github',
    repo_token: '',
  })

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await createProject({
        ...form,
        repo_token: form.repo_token || undefined,
      })
      setOpen(false)
      setForm({
        source: 'sentry',
        source_project_id: '',
        repo_url: '',
        repo_platform: 'github',
        repo_token: '',
      })
      onCreated()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" className="gap-1.5">
            <Plus className="h-4 w-4" />
            New Project
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="source">Error Source</Label>
              <select
                id="source"
                value={form.source}
                onChange={(e) => update('source', e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                <option value="sentry">Sentry</option>
                <option value="cloudwatch">CloudWatch</option>
                <option value="datadog">Datadog</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="platform">Platform</Label>
              <select
                id="platform"
                value={form.repo_platform}
                onChange={(e) => update('repo_platform', e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
              </select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="project_id">Source Project ID</Label>
            <Input
              id="project_id"
              placeholder="e.g. 4509981525278720"
              value={form.source_project_id}
              onChange={(e) => update('source_project_id', e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="repo_url">Repository URL</Label>
            <Input
              id="repo_url"
              placeholder="https://github.com/org/repo"
              value={form.repo_url}
              onChange={(e) => update('repo_url', e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="repo_token">Token (optional)</Label>
            <Input
              id="repo_token"
              type="password"
              placeholder="GitHub PAT or GitLab token"
              value={form.repo_token}
              onChange={(e) => update('repo_token', e.target.value)}
            />
          </div>
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? 'Creating...' : 'Create Project'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
