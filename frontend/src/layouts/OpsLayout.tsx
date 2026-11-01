import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Bot, Building2, ClipboardCheck, Database, FileText, FilePenLine, LayoutDashboard, LogOut, PanelLeftClose, PanelLeftOpen, RefreshCw, ScrollText, ShieldCheck, Users, FileSearch } from 'lucide-react'
import { api, useAuth } from '../auth/AuthContext'
import { Badge, Button, Modal, cn } from '../components/ui'
import { title } from '../lib/format'
import { BrandLogo } from '../components/BrandLogo'

const items = [
  ['/ops', 'Overview', LayoutDashboard, true], ['/ops/applicants', 'Applicants', Users, false], ['/ops/assets', 'Insured assets', Building2, false],
  ['/ops/quotes', 'Quotes', FileText, false], ['/ops/underwriting', 'Underwriting', ClipboardCheck, false], ['/ops/copilot', 'AI Copilot', Bot, false], ['/ops/policies', 'Policies', ShieldCheck, false],
  ['/ops/endorsements', 'Endorsements', FilePenLine, false], ['/ops/renewals', 'Renewals', RefreshCw, false], ['/ops/exceptions', 'Exceptions', AlertTriangle, false],
  ['/ops/audit', 'Audit log', ScrollText, false], ['/ops/data', 'Data & validation', Database, false],
] as const

export default function OpsLayout() {
  const { session, logout } = useAuth()
  const nav = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [showDemoNotice, setShowDemoNotice] = useState(true)
  const pending = useQuery({ queryKey: ['ops', 'summary'], queryFn: () => api.ops.summary(), refetchInterval: 15000 })
  return <div className="flex min-h-screen flex-col">
    <Modal
      open={showDemoNotice}
      onClose={() => setShowDemoNotice(false)}
      title="Demo Environment"
      footer={<Button onClick={() => setShowDemoNotice(false)} data-testid="dismiss-ops-demo-notice">Got it</Button>}
    >
      <div className="space-y-2 text-sm text-slate-600">
        <p className="font-medium text-slate-800">DEMO ENVIRONMENT — operations console over synthetic data. Not production authentication.</p>
        <p className="text-xs text-slate-500">All customer profiles, quotes, policies, and underwriting decisions in this operations console are synthetic demonstrations created for evaluation.</p>
      </div>
    </Modal>
    <div className="flex flex-1">
      <aside className={cn('sticky top-0 hidden h-screen shrink-0 flex-col border-r border-slate-200 bg-white transition-all md:flex', collapsed ? 'w-16' : 'w-60')} aria-label="Operations navigation">
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-4 text-lg font-semibold text-brand-700"><BrandLogo size="md" className="shrink-0" />{!collapsed && 'InsureFlow Ops'}</div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {items.map(([to, label, Icon, end]) => <NavLink key={to} to={to} end={end} title={label} className={({ isActive }) => cn('flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium', isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100')}>
            <Icon className="h-4 w-4 shrink-0" />{!collapsed && <span className="flex-1">{label}</span>}
            {!collapsed && label === 'Underwriting' && !!pending.data?.pending_underwriting_reviews && <Badge tone="amber">{pending.data.pending_underwriting_reviews}</Badge>}
            {!collapsed && label === 'Exceptions' && !!pending.data?.exception_count && <Badge tone="red">{pending.data.exception_count}</Badge>}
          </NavLink>)}
        </nav>
        <button onClick={() => setCollapsed(!collapsed)} className="m-2 flex items-center gap-2 rounded-md p-2 text-sm text-slate-500 hover:bg-slate-100" aria-label="Toggle sidebar">{collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <><PanelLeftClose className="h-4 w-4" />Collapse</>}</button>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/90 px-6 py-3 backdrop-blur">
          <nav className="flex gap-1 overflow-x-auto md:hidden" aria-label="Operations navigation (mobile)">{items.map(([to, label]) => <NavLink key={to} to={to} end={to === '/ops'} className={({ isActive }) => cn('whitespace-nowrap rounded px-2 py-1 text-xs', isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600')}>{label}</NavLink>)}</nav>
          <div className="hidden text-sm text-slate-500 md:block"><FileSearch className="mr-1 inline h-4 w-4" />Same persisted records as the customer portal</div>
          <div className="flex items-center gap-3 text-sm"><Badge tone="purple">{title(session?.role)}</Badge><span className="text-slate-600">{session?.display_name || session?.user_id}</span>
            <Button variant="ghost" size="sm" onClick={() => { logout(); nav('/ops/login') }}><LogOut className="h-4 w-4" />Sign out</Button></div>
        </header>
        <main className="flex-1 p-6"><Outlet /></main>
      </div></div></div>
}
