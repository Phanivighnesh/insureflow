import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { FilePlus2, ShieldCheck } from 'lucide-react'
import { api, useAuth } from '../../auth/AuthContext'
import type { Payment, QuoteSummary, Renewal } from '../../api/types'
import { Badge, Button, Card, CardBody, CardHeader, ConfirmDialog, DataTable, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, Spinner, Stat, StatusBadge, Textarea, useToast } from '../../components/ui'
import { PolicyView, EndorsementModal, type EndorseBody } from '../../components/PolicyView'
import { usePaging } from '../../components/domain'
import { date, money, productLabel, title } from '../../lib/format'
import { ScenarioPanel } from './Public'

const quoteCols = (nav: (s: string) => void) => [
  { header: 'Quote', cell: (q: QuoteSummary) => <span className="font-mono text-xs">{q.quote_id}</span> }, { header: 'Product', cell: (q: QuoteSummary) => productLabel(q.product_key) },
  { header: 'Cover', cell: (q: QuoteSummary) => money(q.requested_coverage, 0) }, { header: 'Premium', cell: (q: QuoteSummary) => money(q.premium) },
  { header: 'Risk', cell: (q: QuoteSummary) => q.risk_category ? <StatusBadge status={q.risk_category} /> : '—' }, { header: 'Status', cell: (q: QuoteSummary) => <StatusBadge status={q.status} /> },
  { header: 'Submitted', cell: (q: QuoteSummary) => date(q.created_at) }, { header: '', cell: (q: QuoteSummary) => <Button size="sm" variant="secondary" onClick={() => nav(q.quote_id)}>Open</Button> }]

export function Dashboard() {
  const { session } = useAuth(); const nav = useNavigate()
  const quotes = useQuery({ queryKey: ['my', 'quotes', 'all'], queryFn: () => api.customer.quotes({ page_size: 100 }) })
  const policies = useQuery({ queryKey: ['my', 'policies', 'all'], queryFn: () => api.customer.policies({ page_size: 100 }) })
  const renewals = useQuery({ queryKey: ['my', 'renewals', 'all'], queryFn: () => api.customer.renewals({ page_size: 100 }) })
  if (quotes.isLoading || policies.isLoading || renewals.isLoading) return <Spinner />
  const err = quotes.error || policies.error || renewals.error
  if (err) return <ErrorState error={err} onRetry={() => { quotes.refetch(); policies.refetch(); renewals.refetch() }} />
  const Q = quotes.data!.items, P = policies.data!.items, R = renewals.data!.items.filter((r) => r.status === 'OFFERED')
  const active = P.filter((p) => p.status === 'ACTIVE')
  const action = Q.filter((q) => ['APPROVED', 'ACCEPTED', 'PENDING_INFORMATION'].includes(q.status))
  const byStatus = Object.entries(Q.reduce<Record<string, number>>((a, q) => ({ ...a, [q.status]: (a[q.status] ?? 0) + 1 }), {}))
  const COLORS = ['#2a54d8', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#64748b', '#06b6d4']
  return <div className="space-y-6" data-testid="customer-dashboard">
    <PageHeader title={`Welcome${session?.display_name ? `, ${session.display_name}` : ''}`} subtitle="Everything below is loaded live from your persisted applications and policies."
      actions={<Link to="/products"><Button><FilePlus2 className="h-4 w-4" />New application</Button></Link>} />
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Applications" value={quotes.data!.total} /><Stat label="Needs your action" value={action.length} tone={action.length ? 'text-amber-600' : undefined} hint="Approved, accepted or awaiting info" />
      <Stat label="Active policies" value={active.length} /><Stat label="Annual premium (active)" value={money(active.reduce((s, p) => s + p.premium, 0))} /></div>
    {Q.length === 0 ? <Card><EmptyState text="No applications yet" hint="Start a quote — or try a demo scenario below." action={<Link to="/products"><Button>Get a quote</Button></Link>} /></Card> :
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader title="Recent applications" action={<Link className="text-sm text-brand-600" to="/my/quotes">View all</Link>} />
          <DataTable rows={Q.slice(0, 5)} rowKey={(q) => q.quote_id} columns={quoteCols((id) => nav(`/quotes/${id}`)).filter((c) => !['Risk', 'Submitted'].includes(c.header))} /></Card>
        <Card><CardHeader title="Applications by status" /><CardBody><div className="h-48"><ResponsiveContainer><PieChart><Pie data={byStatus.map(([name, value]) => ({ name: title(name), value }))} dataKey="value" nameKey="name" outerRadius={70} label={(d) => d.value}>
          {byStatus.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div></CardBody></Card></div>}
    <div className="grid gap-6 lg:grid-cols-2">
      <Card><CardHeader title="My policies" action={<Link className="text-sm text-brand-600" to="/my/policies">View all</Link>} />{P.length === 0 ? <EmptyState text="No policies yet" hint="Accept an approved quote and complete the demo payment." /> :
        <ul className="divide-y divide-slate-100 text-sm">{P.slice(0, 4).map((p) => <li key={p.policy_id}><Link to={`/policies/${p.policy_id}`} className="flex items-center justify-between px-5 py-3 hover:bg-slate-50"><span><span className="font-mono text-xs">{p.policy_id}</span><br /><span className="text-slate-500">{productLabel(p.product_key)} · to {date(p.expiry_date)}</span></span><span className="text-right">{money(p.premium)}<br /><StatusBadge status={p.status} /></span></Link></li>)}</ul>}</Card>
      <Card><CardHeader title="Renewal offers" action={<Link className="text-sm text-brand-600" to="/my/renewals">Manage</Link>} />{R.length === 0 ? <EmptyState text="No open renewal offers" hint="Offers appear within 60 days of expiry." /> :
        <ul className="divide-y divide-slate-100 text-sm">{R.slice(0, 4).map((r) => <li key={r.renewal_id} className="flex items-center justify-between px-5 py-3"><span><span className="font-mono text-xs">{r.renewal_id}</span><br />{date(r.new_start_date)} – {date(r.new_expiry_date)}</span><b>{money(r.offered_premium)}</b></li>)}</ul>}</Card></div>
    {Q.length === 0 && <ScenarioPanel />}
  </div>
}

export function MyQuotes() {
  const nav = useNavigate(); const { page, setPage, pageSize } = usePaging()
  const [status, setStatus] = useState('')
  const q = useQuery({ queryKey: ['my', 'quotes', page], queryFn: () => api.customer.quotes({ page, page_size: pageSize }), placeholderData: (p) => p })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const rows = q.data!.items.filter((x) => !status || x.status === status)
  return <div><PageHeader title="My applications & quotes" actions={<Link to="/products"><Button><FilePlus2 className="h-4 w-4" />New application</Button></Link>} />
    <Card><div className="flex gap-3 border-b border-slate-100 p-4"><Select aria-label="Filter by status" className="max-w-xs" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>
      {['APPROVED', 'REFERRED', 'DECLINED', 'PENDING_INFORMATION', 'ACCEPTED', 'POLICY_ISSUED'].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select></div>
      <DataTable rows={rows} rowKey={(r) => r.quote_id} onRowClick={(r) => nav(`/quotes/${r.quote_id}`)} columns={quoteCols((id) => nav(`/quotes/${id}`))} empty={<EmptyState text="No applications found" hint="Start a new application to get a quote." action={<Link to="/products"><Button>Get a quote</Button></Link>} />} />
      <Pagination page={q.data!.page} pageSize={q.data!.page_size} total={q.data!.total} onPage={setPage} /></Card></div>
}

export function MyPolicies() {
  const nav = useNavigate(); const { page, setPage, pageSize } = usePaging()
  const q = useQuery({ queryKey: ['my', 'policies', page], queryFn: () => api.customer.policies({ page, page_size: pageSize }), placeholderData: (p) => p })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  return <div><PageHeader title="My policies" /><Card>
    <DataTable rows={q.data!.items} rowKey={(p) => p.policy_id} onRowClick={(p) => nav(`/policies/${p.policy_id}`)} empty={<EmptyState text="No policies yet" hint="Accept an approved quote and complete the demo payment to issue one." action={<Link to="/products"><Button>Get a quote</Button></Link>} />}
      columns={[{ header: 'Policy', cell: (p) => <span className="font-mono text-xs">{p.policy_id}</span> }, { header: 'Product', cell: (p) => productLabel(p.product_key) }, { header: 'Coverage', cell: (p) => money(p.coverage_amount, 0) },
        { header: 'Premium', cell: (p) => money(p.premium) }, { header: 'Start', cell: (p) => date(p.start_date) }, { header: 'Expiry', cell: (p) => date(p.expiry_date) }, { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }]} />
    <Pagination page={q.data!.page} pageSize={q.data!.page_size} total={q.data!.total} onPage={setPage} /></Card></div>
}

export function CustomerPolicyDetail() {
  const { id = '' } = useParams(); const qc = useQueryClient(); const toast = useToast()
  const [endorse, setEndorse] = useState(false); const [cancel, setCancel] = useState(false); const [reason, setReason] = useState('')
  const q = useQuery({ queryKey: ['my', 'policy', id], queryFn: () => api.customer.policy(id) })
  const done = () => { qc.invalidateQueries({ queryKey: ['my'] }) }
  const end = useMutation({ mutationFn: (b: EndorseBody) => api.customer.requestEndorsement(id, b),
    onSuccess: (e) => { if (e.status === 'REJECTED') toast.error(new Error(`Endorsement auto-rejected: ${e.decision_reason}`)); else toast.success(`Endorsement ${e.endorsement_id} submitted for approval`); setEndorse(false); done() },
    onError: (e) => toast.error(e) })
  const can = useMutation({ mutationFn: () => api.customer.cancelPolicy(id, reason), onSuccess: () => { toast.success('Policy cancelled'); setCancel(false); done() }, onError: (e) => toast.error(e) })
  const ren = useMutation({ mutationFn: () => api.customer.requestRenewal(id), onSuccess: (r) => { toast.success(`Renewal offer ${r.renewal_id} generated`); done() }, onError: (e) => toast.error(e) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const p = q.data!
  return <div><PageHeader title="Policy details" subtitle="Live from the policy record, including its immutable issue snapshot." />
    <PolicyView policy={p} linkBase="/policies" actions={p.status === 'ACTIVE' && <div className="flex gap-2">
      <Button size="sm" variant="secondary" onClick={() => setEndorse(true)} data-testid="request-endorsement">Request change</Button>
      {p.renewal_eligibility.eligible && <Button size="sm" loading={ren.isPending} onClick={() => ren.mutate()}>Request renewal</Button>}
      <Button size="sm" variant="danger" onClick={() => setCancel(true)}>Cancel policy</Button></div>}
      renewalActions={(r) => r.status === 'OFFERED' ? <Link to="/my/renewals"><Button size="sm" variant="secondary">Respond</Button></Link> : null} />
    {endorse && <EndorsementModal open onClose={() => setEndorse(false)} policy={p} loading={end.isPending} onSubmit={(b) => end.mutate(b)} />}
    <ConfirmDialog open={cancel} onClose={() => setCancel(false)} danger title="Cancel this policy?" confirmLabel="Cancel policy" loading={can.isPending} onConfirm={() => can.mutate()}>
      <p className="mb-3 text-sm text-slate-600">Cancellation ends cover and withdraws any open renewal offer. This cannot be undone.</p>
      <Field label="Reason" required><Textarea aria-label="Cancellation reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field></ConfirmDialog></div>
}

export function MyRenewals() {
  const qc = useQueryClient(); const toast = useToast()
  const [outcome, setOutcome] = useState<Payment['status']>('SUCCESS'); const [decline, setDecline] = useState<Renewal | null>(null); const [why, setWhy] = useState('')
  const q = useQuery({ queryKey: ['my', 'renewals', 'list'], queryFn: () => api.customer.renewals({ page_size: 100 }) })
  const done = () => qc.invalidateQueries({ queryKey: ['my'] })
  const acc = useMutation({ mutationFn: (id: string) => api.customer.acceptRenewal(id, outcome), onSuccess: (r) => { r.new_policy ? toast.success(`Renewed — new policy ${r.new_policy.policy_id}`) : toast.info(`Demo payment ${outcome.toLowerCase()} — renewal still open`); done() }, onError: (e) => toast.error(e) })
  const dec = useMutation({ mutationFn: (id: string) => api.customer.declineRenewal(id, why), onSuccess: () => { toast.success('Renewal declined'); setDecline(null); done() }, onError: (e) => toast.error(e) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const rows = q.data!.items
  return <div><PageHeader title="Renewals" subtitle="Offers are generated within 60 days of expiry. Accepting uses the same clearly-labelled DEMO payment." actions={<span className="flex items-center gap-2 text-sm"><Badge tone="amber">DEMO PAYMENT</Badge>
    <Select aria-label="Demo payment result" className="w-44" value={outcome} onChange={(e) => setOutcome(e.target.value as Payment['status'])}><option value="SUCCESS">Payment succeeds</option><option value="FAILED">Payment fails</option><option value="PENDING">Payment pending</option></Select></span>} />
    <Card><DataTable rows={rows} rowKey={(r) => r.renewal_id} empty={<EmptyState text="No renewals yet" hint="When a policy nears expiry you can request a renewal from its detail page." action={<Link to="/my/policies"><Button variant="secondary"><ShieldCheck className="h-4 w-4" />My policies</Button></Link>} />}
      columns={[{ header: 'Renewal', cell: (r) => <span className="font-mono text-xs">{r.renewal_id}</span> }, { header: 'Policy', cell: (r) => <Link className="text-brand-600 hover:underline" to={`/policies/${r.policy_id}`}>{r.policy_id}</Link> },
        { header: 'New term', cell: (r) => `${date(r.new_start_date)} – ${date(r.new_expiry_date)}` }, { header: 'Offered premium', cell: (r) => money(r.offered_premium) },
        { header: 'Status', cell: (r) => <StatusBadge status={r.status} /> }, { header: '', cell: (r) => r.status === 'OFFERED' ? <div className="flex gap-2"><Button size="sm" loading={acc.isPending} onClick={() => acc.mutate(r.renewal_id)}>Accept</Button><Button size="sm" variant="secondary" onClick={() => setDecline(r)}>Decline</Button></div> : r.new_policy_id ? <Link className="text-sm text-brand-600" to={`/policies/${r.new_policy_id}`}>{r.new_policy_id}</Link> : null }]} /></Card>
    <Modal open={!!decline} onClose={() => setDecline(null)} title="Decline renewal" footer={<><Button variant="secondary" onClick={() => setDecline(null)}>Keep offer</Button><Button variant="danger" loading={dec.isPending} onClick={() => decline && dec.mutate(decline.renewal_id)}>Decline</Button></>}>
      <Field label="Reason (optional)"><Input aria-label="Decline reason" value={why} onChange={(e) => setWhy(e.target.value)} /></Field></Modal></div>
}
