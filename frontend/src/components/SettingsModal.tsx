import { useEffect, useState } from 'react'
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
import { Switch } from '@/components/ui/switch'
import { Settings, Webhook, Copy, Check, Send } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getSettings, updateSettings, testNotification } from '@/api/client'

const TABS = [
  { id: 'webhook', label: 'Webhooks', icon: Webhook },
] as const

type TabId = (typeof TABS)[number]['id']

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const WEBHOOK_ENDPOINTS = [
  { source: 'Sentry', path: '/api/webhook/sentry' },
]

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Button variant="ghost" size="icon-xs" onClick={copy}>
      {copied ? (
        <Check className="h-3 w-3 text-green-600" />
      ) : (
        <Copy className="h-3 w-3 text-muted-foreground" />
      )}
    </Button>
  )
}

function WebhookSettings() {
  const [doorayUrl, setDoorayUrl] = useState('')
  const [notificationEnabled, setNotificationEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'success' | 'fail' | null>(null)

  useEffect(() => {
    getSettings()
      .then((data) => {
        setDoorayUrl(data.dooray_webhook_url ?? '')
        setNotificationEnabled(data.notification_enabled)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const data = await updateSettings({
        dooray_webhook_url: doorayUrl,
        notification_enabled: notificationEnabled,
      })
      setDoorayUrl(data.dooray_webhook_url ?? '')
      setNotificationEnabled(data.notification_enabled)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      alert('설정 저장에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="text-sm text-muted-foreground">불러오는 중...</div>
  }

  return (
    <div className="flex flex-col gap-6">

      <div className="h-px bg-border" />

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Notifications</h3>
          <div className="flex items-center gap-2">
            <Label htmlFor="notification-toggle" className="text-xs text-muted-foreground">
              알림 {notificationEnabled ? 'ON' : 'OFF'}
            </Label>
            <Switch
              id="notification-toggle"
              checked={notificationEnabled}
              onCheckedChange={setNotificationEnabled}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="dooray-url">Dooray Webhook URL</Label>
          <Input
            id="dooray-url"
            type="url"
            placeholder="https://hook.dooray.com/services/..."
            value={doorayUrl}
            onChange={(e) => setDoorayUrl(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            작업 시작/완료 알림을 받을 Dooray 웹훅 URL
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <Button
          variant="outline"
          size="sm"
          disabled={testing || !doorayUrl}
          onClick={async () => {
            setTesting(true)
            setTestResult(null)
            try {
              await testNotification(doorayUrl)
              setTestResult('success')
            } catch {
              setTestResult('fail')
            } finally {
              setTesting(false)
              setTimeout(() => setTestResult(null), 3000)
            }
          }}
        >
          <Send className="h-3 w-3 mr-1.5" />
          {testing ? '발송 중...' : testResult === 'success' ? '발송 성공' : testResult === 'fail' ? '발송 실패' : '테스트 발송'}
        </Button>
        <Button onClick={handleSave} disabled={saving} size="sm">
          {saving ? '저장 중...' : saved ? '저장 완료' : '저장'}
        </Button>
      </div>
    </div>
  )
}

export function SettingsModal() {
  const [open, setOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('webhook')

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon">
            <Settings className="h-4 w-4" />
          </Button>
        }
      />
      <DialogContent className="sm:max-w-[600px] p-0 gap-0" showCloseButton={false}>
        <div className="flex h-[480px]">
          {/* Left sidebar */}
          <div className="w-44 shrink-0 border-r border-border bg-muted/30 p-3 flex flex-col gap-1 rounded-l-xl">
            <DialogHeader className="px-2 pb-3">
              <DialogTitle className="text-sm">Settings</DialogTitle>
            </DialogHeader>
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left transition-colors',
                  activeTab === tab.id
                    ? 'bg-background text-foreground font-medium shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                )}
              >
                <tab.icon className="h-4 w-4 shrink-0" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Right content */}
          <div className="flex-1 overflow-y-auto p-5">
            {activeTab === 'webhook' && <WebhookSettings />}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}