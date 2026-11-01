import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, HelpCircle, RefreshCw, XCircle } from 'lucide-react'
import { api, useAuth } from '../../auth/AuthContext'
import { Badge, Button, Card, CardBody, CardHeader, ConfirmDialog, DataTable, EmptyState, ErrorState, Field, KV, PageHeader, Pagination, Select, Spinner, StatusBadge, Textarea, useToast } from '../../components/ui'
import { AuditTimeline, DecisionList, EligibilityChecks, OutcomeBanner, PremiumCard, QuoteFacts, RiskPanel, usePaging } from '../../components/domain'
import { FilterBar, SearchBox, useDebounced } from '../../components/ops'
import { canLikelyAct } from '../../lib/authority'
import { date, dateTime, money, productLabel, title } from '../../lib/format'
import type { QuoteSummary } from '../../api/types'

const QUOTE_STATUSES = ['APPROVED', 'REFERRED', 'DECLINED', 'PENDING_INFORMATION', 'ACCEPTED', 'POLICY_ISSUED']

export function Applicants() {
  const nav = useNavigate(); const { page, setPage, pageSize } = usePaging(1, 20)
  const [q, setQ] = useState(''); const [status, setStatus] = useState(''); const [sort, setSort] = useState('applicant_id'); const [order, setOrder] = useState('asc')
  const dq = useDebounced(q)
  const r = useQuery({ queryKey: ['ops', 'applicants', page, dq, status, sort, order], queryFn: () => api.ops.applicants({ page, page_size: pageSize, q: dq, status, sort, order }), placeholderData: (p) => p })
  return <div><PageHeader title="Applicant management" subtitle="Everyone who has applied, including customers from the portal." />
    <Card><FilterBar><SearchBox value={q} onChange={(v) => { setQ(v); setPage(1) }} placeholder="Search name, email, ID…" />
      <Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}><option value="">All statuses</option><option>ACTIVE</option><option>INACTIVE</option></Select>
      <Select aria-label="Sort by" value={sort} onChange={(e) => setSort(e.target.value)}><option value="applicant_id">Sort: ID</option><option value="name">Sort: Name</option><option value="created_at">Sort: Created</option><option value="location">Sort: Location</option></Select>
      <Select aria-label="Order" value={order} onChange={(e) => setOrder(e.target.value)}><option value="asc">Ascending</option><option value="desc">Descending</option></Select></FilterBar>
      {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <>
        <DataTable rows={r.data!.items} rowKey={(a) => a.applicant_id} onRowClick={(a) => nav(`/ops/applicants/${a.applicant_id}`)} columns={[
          { header: 'Applicant ID', cell: (a) => <span className="font-mono text-xs">{a.applicant_id}</span> }, { header: 'Name', cell: (a) => <b>{a.full_name}</b> }, { header: 'Type', cell: (a) => title(a.applicant_type) },
          { header: 'Location', cell: (a) => a.location ?? '—' }, { header: 'Assets', cell: (a) => a.asset_count }, { header: 'Quotes', cell: (a) => a.quote_count }, { header: 'Status', cell: (a) => <StatusBadge status={a.status} /> }]} />
        <Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card></div>
}

export function ApplicantDetail() {
  const { id = '' } = useParams(); const nav = useNavigate()
  const r = useQuery({ queryKey: ['ops', 'applicant', id], queryFn: () => api.ops.applicant(id) })
  if (r.isLoading) return <Spinner />
  if (r.error) return <ErrorState error={r.error} onRetry={() => r.refetch()} />
  const a = r.data!
  return <div className="space-y-6"><PageHeader title={a.full_name} subtitle={<span className="font-mono">{a.applicant_id}</span>} />
    <Card><CardBody><dl className="grid gap-x-10 md:grid-cols-2"><div className="divide-y divide-slate-100"><KV k="Email" v={a.email ?? '—'} /><KV k="Phone" v={a.phone ?? '—'} /><KV k="Age" v={a.age ?? '—'} /></div>
      <div className="divide-y divide-slate-100"><KV k="Location" v={a.location ?? '—'} /><KV k="Type" v={title(a.applicant_type)} /><KV k="Status" v={<StatusBadge status={a.status} />} /><KV k="Created" v={dateTime(a.created_at)} /></div></dl></CardBody></Card>
    <Card><CardHeader title="Insured assets" /><DataTable rows={a.assets} rowKey={(x) => x.asset_id} onRowClick={(x) => nav(`/ops/assets/${x.asset_id}`)} columns={[{ header: 'Asset', cell: (x) => <span className="font-mono text-xs">{x.asset_id}</span> }, { header: 'Type', cell: (x) => title(x.asset_type) }, { header: 'Value', cell: (x) => money(x.declared_value, 0) }, { header: 'Location', cell: (x) => x.location ?? '—' }]} /></Card>
    <Card><CardHeader title="Quotes" /><QuoteTable rows={a.quotes} /></Card>
    <Card><CardHeader title="Policies" /><DataTable rows={a.policies} rowKey={(p) => p.policy_id} onRowClick={(p) => nav(`/ops/policies/${p.policy_id}`)} columns={[{ header: 'Policy', cell: (p) => <span className="font-mono text-xs">{p.policy_id}</span> }, { header: 'Product', cell: (p) => productLabel(p.product_key) }, { header: 'Premium', cell: (p) => money(p.premium) }, { header: 'Expiry', cell: (p) => date(p.expiry_date) }, { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }]} /></Card></div>
}

export function Assets() {
  const nav = useNavigate(); const { page, setPage, pageSize } = usePaging(1, 20)
  const [q, setQ] = useState(''); const [type, setType] = useState(''); const dq = useDebounced(q)
  const r = useQuery({ queryKey: ['ops', 'assets', page, dq, type], queryFn: () => api.ops.assets({ page, page_size: pageSize, q: dq, asset_type: type }), placeholderData: (p) => p })
  return <div><PageHeader title="Insured asset management" /><Card><FilterBar><SearchBox value={q} onChange={(v) => { setQ(v); setPage(1) }} placeholder="Search asset, owner, location…" />
    <Select aria-label="Asset type" value={type} onChange={(e) => { setType(e.target.value); setPage(1) }}><option value="">All asset types</option><option value="VEHICLE">Vehicle</option><option value="PROPERTY">Property</option><option value="COMMERCIAL_ASSET">Commercial asset</option></Select></FilterBar>
    {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><DataTable rows={r.data!.items} rowKey={(a) => a.asset_id} onRowClick={(a) => nav(`/ops/assets/${a.asset_id}`)} columns={[
      { header: 'Asset ID', cell: (a) => <span className="font-mono text-xs">{a.asset_id}</span> }, { header: 'Owner', cell: (a) => a.owner }, { header: 'Type', cell: (a) => title(a.asset_type) }, { header: 'Declared value', cell: (a) => money(a.declared_value, 0) },
      { header: 'Location', cell: (a) => a.location ?? '—' }, { header: 'Policies', cell: (a) => a.policy_count }]} /><Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card></div>
}

export function AssetDetail() {
  const { id = '' } = useParams(); const nav = useNavigate()
  const r = useQuery({ queryKey: ['ops', 'asset', id], queryFn: () => api.ops.asset(id) })
  if (r.isLoading) return <Spinner />
  if (r.error) return <ErrorState error={r.error} onRetry={() => r.refetch()} />
  const a = r.data!
  return <div className="space-y-6"><PageHeader title={<span className="font-mono">{a.asset_id}</span>} subtitle={`${title(a.asset_type)} · owner ${a.applicant_id} · ${money(a.declared_value, 0)} · ${a.location ?? '—'}`} />
    <Card><CardHeader title="Attributes" /><CardBody><dl className="grid gap-x-10 md:grid-cols-2">{Object.entries(a.attributes).map(([k, v]) => <KV key={k} k={title(k)} v={String(v)} />)}</dl></CardBody></Card>
    <Card><CardHeader title="Quotes" /><QuoteTable rows={a.quotes} /></Card>
    <Card><CardHeader title="Policies" /><DataTable rows={a.policies} rowKey={(p) => p.policy_id} onRowClick={(p) => nav(`/ops/policies/${p.policy_id}`)} columns={[{ header: 'Policy', cell: (p) => <span className="font-mono text-xs">{p.policy_id}</span> }, { header: 'Premium', cell: (p) => money(p.premium) }, { header: 'Term', cell: (p) => `${date(p.start_date)} – ${date(p.expiry_date)}` }, { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }]} empty={<EmptyState text="No policies on this asset" />} /></Card></div>
}

export function QuoteTable({ rows }: { rows: QuoteSummary[] }) {
  const nav = useNavigate()
  return <DataTable rows={rows} rowKey={(q) => q.quote_id} onRowClick={(q) => nav(`/ops/quotes/${q.quote_id}`)} columns={[
    { header: 'Quote', cell: (q) => <span className="font-mono text-xs">{q.quote_id}</span> }, ...(rows[0]?.applicant_name !== undefined ? [{ header: 'Applicant', cell: (q: QuoteSummary) => q.applicant_name }] : []),
    { header: 'Product', cell: (q) => productLabel(q.product_key) }, { header: 'Cover', cell: (q) => money(q.requested_coverage, 0) }, { header: 'Premium', cell: (q) => money(q.premium) },
    { header: 'Eligibility', cell: (q) => <StatusBadge status={q.eligibility_status} /> }, { header: 'Risk', cell: (q) => q.risk_score === null ? '—' : <span>{q.risk_score.toFixed(1)} <StatusBadge status={q.risk_category} /></span> },
    { header: 'Status', cell: (q) => <StatusBadge status={q.status} /> }, { header: 'Submitted', cell: (q) => date(q.created_at) }]} />
}

export function Quotes() {
  const { page, setPage, pageSize } = usePaging(1, 20)
  const [q, setQ] = useState(''); const [status, setStatus] = useState(''); const [product, setProduct] = useState(''); const [risk, setRisk] = useState(''); const dq = useDebounced(q)
  const r = useQuery({ queryKey: ['ops', 'quotes', page, dq, status, product, risk], queryFn: () => api.ops.quotes({ page, page_size: pageSize, q: dq, status, product, risk_category: risk }), placeholderData: (p) => p })
  const reset = <T,>(f: (v: T) => void) => (v: T) => { f(v); setPage(1) }
  return <div><PageHeader title="Quote management" subtitle="Includes every customer-portal submission, immediately after it is made." />
    <Card><FilterBar><SearchBox value={q} onChange={reset(setQ)} placeholder="Search quote ID, applicant, email…" />
      <Select aria-label="Status" value={status} onChange={(e) => reset(setStatus)(e.target.value)}><option value="">All statuses</option>{QUOTE_STATUSES.map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
      <Select aria-label="Product" value={product} onChange={(e) => reset(setProduct)(e.target.value)}><option value="">All products</option><option value="MOTOR">Motor</option><option value="PROPERTY">Property</option><option value="COMMERCIAL">Commercial</option></Select>
      <Select aria-label="Risk category" value={risk} onChange={(e) => reset(setRisk)(e.target.value)}><option value="">All risk levels</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></Select></FilterBar>
      {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><QuoteTable rows={r.data!.items} /><Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card></div>
}

export function Underwriting() {
  const nav = useNavigate(); const { page, setPage, pageSize } = usePaging(1, 20); const { session } = useAuth()
  const [withInfo, setWithInfo] = useState(false)
  const r = useQuery({ queryKey: ['ops', 'pending', page, withInfo], queryFn: () => api.ops.pending({ page, page_size: pageSize, include_pending_information: withInfo }), placeholderData: (p) => p, refetchInterval: 15000 })
  return <div><PageHeader title="Underwriting review queue" subtitle="Referred applications awaiting a decision, oldest first. The required authority is set by the rules engine." />
    <Card><FilterBar><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={withInfo} onChange={(e) => { setWithInfo(e.target.checked); setPage(1) }} />Include “pending information”</label>
      <span className="text-sm text-slate-500">Signed in as <Badge tone="purple">{title(session?.role)}</Badge></span></FilterBar>
      {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><DataTable rows={r.data!.items} rowKey={(q) => q.quote_id} onRowClick={(q) => nav(`/ops/quotes/${q.quote_id}`)}
        empty={<EmptyState text="Queue is empty" hint="No applications are awaiting review." />} columns={[
          { header: 'Quote', cell: (q) => <span className="font-mono text-xs">{q.quote_id}</span> }, { header: 'Applicant', cell: (q) => q.applicant_name }, { header: 'Product', cell: (q) => productLabel(q.product_key) },
          { header: 'Cover', cell: (q) => money(q.requested_coverage, 0) }, { header: 'Risk', cell: (q) => q.risk_score === null ? '—' : <span>{q.risk_score.toFixed(1)} <StatusBadge status={q.risk_category} /></span> },
          { header: 'Referral reason', cell: (q) => <span className="text-xs text-slate-600">{q.referral_reasons?.map((x) => x.message).join('; ')}</span>, className: 'max-w-sm' },
          { header: 'Required authority', cell: (q) => title(q.required_authority) }, { header: 'You can act', cell: (q) => q.decision_outcome !== 'REFERRED' ? <Badge>n/a</Badge> : q.can_act ? <Badge tone="green">Yes</Badge> : <Badge tone="red">No — escalate</Badge> },
          { header: 'Age', cell: (q) => date(q.created_at) }]} /><Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card></div>
}

export function OpsQuoteDetail() {
  const { id = '' } = useParams(); const qc = useQueryClient(); const toast = useToast(); const { session } = useAuth()
  const [notes, setNotes] = useState(''); const [action, setAction] = useState<null | 'approve' | 'reject' | 'request-information'>(null); const [reeval, setReeval] = useState(false)
  const q = useQuery({ queryKey: ['ops', 'quote', id], queryFn: () => api.ops.quote(id) })
  const audit = useQuery({ queryKey: ['ops', 'quote', id, 'audit'], queryFn: () => api.ops.quoteAudit(id) })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['ops'] }) }
  const review = useMutation({ mutationFn: (a: 'approve' | 'reject' | 'request-information') => api.ops.review(q.data!.decision!.decision_id, a, notes),
    onSuccess: (r) => { toast.success(`Decision recorded: ${title(r.decision.outcome)}`); setAction(null); setNotes(''); qc.setQueryData(['ops', 'quote', id], r.quote); refresh() }, onError: (e) => { toast.error(e); setAction(null) } })
  const re = useMutation({ mutationFn: () => api.ops.reevaluate(id), onSuccess: () => { toast.success('Re-evaluated; a new decision was appended'); setReeval(false); refresh() }, onError: (e) => { toast.error(e); setReeval(false) } })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const quote = q.data!; const dec = quote.decision
  const referred = quote.status === 'REFERRED' && dec?.outcome === 'REFERRED'
  const likely = canLikelyAct(session?.role, dec?.approval_authority)
  const LABEL = { approve: 'Approve', reject: 'Reject', 'request-information': 'Request information' } as const
  return <div data-testid="ops-quote-detail" data-quote-id={quote.quote_id} className="space-y-6">
    <PageHeader title={<>Quote <span className="font-mono">{quote.quote_id}</span></>} subtitle={`${quote.applicant.full_name} · ${productLabel(quote.product_key)}`}
      actions={<div className="flex gap-2"><Link to={`/ops/copilot?type=quote&id=${quote.quote_id}`}><Button variant="secondary" size="sm">Ask Copilot</Button></Link>{quote.policy_id && <Link to={`/ops/policies/${quote.policy_id}`}><Button variant="secondary" size="sm">View policy {quote.policy_id}</Button></Link>}
        {!['ACCEPTED', 'POLICY_ISSUED'].includes(quote.status) && <Button variant="secondary" size="sm" onClick={() => setReeval(true)}><RefreshCw className="h-4 w-4" />Re-evaluate</Button>}</div>} />
    <OutcomeBanner quote={quote} />
    {referred && <Card className="border-amber-300" data-testid="review-panel"><CardHeader title="Underwriting review" subtitle={`Required authority: ${title(dec!.approval_authority)} · your role: ${title(session?.role)}`} action={likely ? <Badge tone="green">Within your authority</Badge> : <Badge tone="red">Above your authority</Badge>} />
      <CardBody className="space-y-3"><ul className="list-disc pl-5 text-sm text-slate-700">{dec!.reasons.map((r, i) => <li key={i}><code className="rounded bg-slate-100 px-1 text-xs">{r.rule_id}</code> {r.message}</li>)}</ul>
        <Field label="Reviewer notes"><Textarea aria-label="Reviewer notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <div className="flex flex-wrap gap-2"><Button variant="success" onClick={() => setAction('approve')} data-testid="approve"><CheckCircle2 className="h-4 w-4" />Approve</Button>
          <Button variant="danger" onClick={() => setAction('reject')} data-testid="reject"><XCircle className="h-4 w-4" />Reject</Button>
          <Button variant="secondary" onClick={() => setAction('request-information')}><HelpCircle className="h-4 w-4" />Request information</Button></div>
        {!likely && <p className="text-xs text-red-600">The backend will refuse approve/reject from a role below the required authority (403). Escalate to a higher role.</p>}</CardBody></Card>}
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card><CardHeader title="Decision history" subtitle="Append-only; earlier decisions are never overwritten." /><CardBody><DecisionList decisions={quote.decision_history} /></CardBody></Card>
        {quote.eligibility && <Card><CardHeader title="Eligibility checks" action={<StatusBadge status={quote.eligibility.status} />} /><CardBody><EligibilityChecks checks={quote.eligibility.checks} /></CardBody></Card>}
        {quote.risk && <Card><CardHeader title="Risk factors" /><CardBody><RiskPanel risk={quote.risk} /></CardBody></Card>}
        <Card><CardHeader title="Audit trail" subtitle="Quote, payments, policy, endorsements and renewals." /><CardBody>{audit.isLoading ? <Spinner /> : audit.error ? <ErrorState error={audit.error} /> : <AuditTimeline events={audit.data!.events} />}</CardBody></Card></div>
      <div className="space-y-6">{quote.premium_breakdown && <PremiumCard pb={quote.premium_breakdown} title={quote.status === 'DECLINED' ? 'Indicative premium (not offered)' : 'Premium breakdown'} />}
        <QuoteFacts q={quote} />
        <Card><CardHeader title="Asset attributes" /><CardBody><dl className="divide-y divide-slate-100">{Object.entries(quote.asset.attributes).map(([k, v]) => <KV key={k} k={title(k)} v={String(v)} />)}</dl></CardBody></Card>
        {quote.acceptance && <Card><CardHeader title="Customer acceptance" /><CardBody><dl><KV k="Accepted" v={dateTime(quote.acceptance.accepted_at)} /><KV k="By" v={quote.acceptance.accepted_by} /><KV k="Terms" v={quote.acceptance.terms_version} /></dl></CardBody></Card>}</div></div>
    <ConfirmDialog open={!!action} onClose={() => setAction(null)} loading={review.isPending} danger={action === 'reject'} title={`${action ? LABEL[action] : ''} this application?`} confirmLabel={action ? LABEL[action] : 'Confirm'} onConfirm={() => action && review.mutate(action)}>
      <p className="text-sm text-slate-600">This records a new <b>manual</b> underwriting decision for <span className="font-mono">{quote.quote_id}</span> under your name and role. It is permanent and appears in the audit trail.{notes && <> Notes: “{notes}”.</>}</p></ConfirmDialog>
    <ConfirmDialog open={reeval} onClose={() => setReeval(false)} loading={re.isPending} onConfirm={() => re.mutate()} title="Re-run the underwriting engine?" confirmLabel="Re-evaluate"><p className="text-sm text-slate-600">The deterministic engine will re-evaluate this quote and append a new decision. Existing decisions are kept.</p></ConfirmDialog></div>
}
