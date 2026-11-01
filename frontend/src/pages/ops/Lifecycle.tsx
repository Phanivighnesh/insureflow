import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../auth/AuthContext'
import type { Endorsement, Renewal } from '../../api/types'
import { Button, Card, CardHeader, ConfirmDialog, DataTable, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, Spinner, StatusBadge, Textarea, useToast } from '../../components/ui'
import { EndorsementModal, EndorsementTable, PolicyView, RenewalTable, type EndorseBody } from '../../components/PolicyView'
import { usePaging } from '../../components/domain'
import { FilterBar, SearchBox, useDebounced } from '../../components/ops'
import { date, money, productLabel, title } from '../../lib/format'

export function Policies() {
  const nav = useNavigate(); const { page, setPage, pageSize } = usePaging(1, 20)
  const [q, setQ] = useState(''); const [status, setStatus] = useState(''); const [product, setProduct] = useState(''); const dq = useDebounced(q)
  const r = useQuery({ queryKey: ['ops', 'policies', page, dq, status, product], queryFn: () => api.ops.policies({ page, page_size: pageSize, q: dq, status, product }), placeholderData: (p) => p })
  return <div><PageHeader title="Policy management" subtitle="Includes policies issued from the customer portal." /><Card><FilterBar>
    <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1) }} placeholder="Search policy, holder, asset…" />
    <Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}><option value="">All statuses</option>{['ACTIVE', 'CANCELLED', 'EXPIRED', 'RENEWED'].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
    <Select aria-label="Product" value={product} onChange={(e) => { setProduct(e.target.value); setPage(1) }}><option value="">All products</option><option value="MOTOR">Motor</option><option value="PROPERTY">Property</option><option value="COMMERCIAL">Commercial</option></Select></FilterBar>
    {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><DataTable rows={r.data!.items} rowKey={(p) => p.policy_id} onRowClick={(p) => nav(`/ops/policies/${p.policy_id}`)} columns={[
      { header: 'Policy', cell: (p) => <span className="font-mono text-xs">{p.policy_id}</span> }, { header: 'Applicant', cell: (p) => p.applicant_name }, { header: 'Product', cell: (p) => productLabel(p.product_key) },
      { header: 'Coverage', cell: (p) => money(p.coverage_amount, 0) }, { header: 'Premium', cell: (p) => money(p.premium) }, { header: 'Start', cell: (p) => date(p.start_date) }, { header: 'Expiry', cell: (p) => date(p.expiry_date) },
      { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }]} /><Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card></div>
}

export function OpsPolicyDetail() {
  const { id = '' } = useParams(); const qc = useQueryClient(); const toast = useToast()
  const [cancel, setCancel] = useState(false); const [reason, setReason] = useState(''); const [endorse, setEndorse] = useState(false); const [gen, setGen] = useState(false); const [asOf, setAsOf] = useState('')
  const [decide, setDecide] = useState<{ e: Endorsement; approve: boolean } | null>(null); const [why, setWhy] = useState('')
  const q = useQuery({ queryKey: ['ops', 'policy', id], queryFn: () => api.ops.policy(id) })
  const done = () => qc.invalidateQueries({ queryKey: ['ops'] })
  const can = useMutation({ mutationFn: () => api.ops.cancelPolicy(id, reason), onSuccess: () => { toast.success('Policy cancelled'); setCancel(false); done() }, onError: (e) => { toast.error(e); setCancel(false) } })
  const end = useMutation({ mutationFn: (b: EndorseBody) => api.ops.createEndorsement(id, b), onSuccess: (e) => { if (e.status === 'REJECTED') toast.error(new Error(`Auto-rejected: ${e.decision_reason}`)); else toast.success(`Endorsement ${e.endorsement_id} created`); setEndorse(false); done() }, onError: (e) => toast.error(e) })
  const dec = useMutation({ mutationFn: () => api.ops.decideEndorsement(decide!.e.endorsement_id, decide!.approve, why), onSuccess: () => { toast.success('Endorsement decision recorded'); setDecide(null); setWhy(''); done() }, onError: (e) => { toast.error(e); setDecide(null) } })
  const ren = useMutation({ mutationFn: () => api.ops.generateRenewal(id, asOf || undefined), onSuccess: (r) => { toast.success(`Renewal ${r.renewal_id}: ${title(r.status)}`); setGen(false); done() }, onError: (e) => toast.error(e) })
  const respond = useMutation({ mutationFn: (v: { r: Renewal; accept: boolean }) => v.accept ? api.ops.acceptRenewal(v.r.renewal_id) : api.ops.declineRenewal(v.r.renewal_id, 'Declined by operations on behalf of customer'), onSuccess: () => { toast.success('Renewal updated'); done() }, onError: (e) => toast.error(e) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const p = q.data!
  return <div><PageHeader title="Policy" subtitle={p.applicant_name} actions={<div className="flex gap-2"><Link to={`/ops/copilot?type=policy&id=${p.policy_id}`}><Button variant="secondary" size="sm">Ask Copilot</Button></Link><Link to={p.quote_id ? `/ops/quotes/${p.quote_id}` : '#'}>{p.quote_id && <Button variant="secondary" size="sm">Origin quote {p.quote_id}</Button>}</Link></div>} />
    <PolicyView policy={p} linkBase="/ops/policies" actions={<div className="flex gap-2">{p.status === 'ACTIVE' && <><Button size="sm" variant="secondary" onClick={() => setEndorse(true)}>New endorsement</Button>
      <Button size="sm" variant="secondary" onClick={() => { setAsOf(new Date(new Date(p.expiry_date).getTime() - 20 * 86400000).toISOString().slice(0, 10)); setGen(true) }}>Generate renewal</Button>
      <Button size="sm" variant="danger" onClick={() => setCancel(true)}>Cancel policy</Button></>}</div>}
      endorsementActions={(e) => e.status === 'PENDING' ? <div className="flex gap-1"><Button size="sm" variant="success" onClick={() => setDecide({ e, approve: true })}>Approve</Button><Button size="sm" variant="danger" onClick={() => setDecide({ e, approve: false })}>Reject</Button></div> : null}
      renewalActions={(r) => r.status === 'OFFERED' ? <div className="flex gap-1"><Button size="sm" onClick={() => respond.mutate({ r, accept: true })}>Accept (demo pay)</Button><Button size="sm" variant="secondary" onClick={() => respond.mutate({ r, accept: false })}>Decline</Button></div> : null} />
    {endorse && <EndorsementModal open onClose={() => setEndorse(false)} policy={p} loading={end.isPending} onSubmit={(b) => end.mutate(b)} />}
    <ConfirmDialog open={cancel} onClose={() => setCancel(false)} danger title="Cancel policy?" confirmLabel="Cancel policy" loading={can.isPending} onConfirm={() => can.mutate()}>
      <Field label="Reason" required><Textarea aria-label="Cancellation reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field></ConfirmDialog>
    <ConfirmDialog open={!!decide} onClose={() => setDecide(null)} danger={decide?.approve === false} title={`${decide?.approve ? 'Approve' : 'Reject'} endorsement?`} confirmLabel={decide?.approve ? 'Approve' : 'Reject'} loading={dec.isPending} onConfirm={() => dec.mutate()}>
      <p className="mb-2 text-sm text-slate-600">{decide?.e.endorsement_id}: cover {money(decide?.e.coverage_before, 0)} → {money(decide?.e.coverage_after, 0)}. Approval authority for the new coverage band is enforced by the backend.</p><Field label="Reason (optional)"><Input aria-label="Decision reason" value={why} onChange={(e) => setWhy(e.target.value)} /></Field></ConfirmDialog>
    <Modal open={gen} onClose={() => setGen(false)} title="Generate renewal offer" footer={<><Button variant="secondary" onClick={() => setGen(false)}>Cancel</Button><Button loading={ren.isPending} onClick={() => ren.mutate()}>Generate</Button></>}>
      <Field label="As-of date" hint="Staff-only demo convenience: choose a date inside the 60-day renewal window to see the renewal rules apply. Cancelled policies are always refused."><Input aria-label="As-of date" type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></Field></Modal></div>
}

export function Endorsements() {
  const qc = useQueryClient(); const toast = useToast(); const { page, setPage, pageSize } = usePaging(1, 20)
  const [status, setStatus] = useState(''); const [decide, setDecide] = useState<{ e: Endorsement; approve: boolean } | null>(null); const [why, setWhy] = useState('')
  const r = useQuery({ queryKey: ['ops', 'endorsements', page, status], queryFn: () => api.ops.endorsements({ page, page_size: pageSize, status }), placeholderData: (p) => p })
  const dec = useMutation({ mutationFn: () => api.ops.decideEndorsement(decide!.e.endorsement_id, decide!.approve, why), onSuccess: () => { toast.success('Decision recorded'); setDecide(null); setWhy(''); qc.invalidateQueries({ queryKey: ['ops'] }) }, onError: (e) => { toast.error(e); setDecide(null) } })
  return <div><PageHeader title="Endorsements" subtitle="Mid-term changes. Limit breaches are auto-rejected and recorded; the original policy is never overwritten." />
    <Card><FilterBar><Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}><option value="">All statuses</option><option>PENDING</option><option>APPROVED</option><option>REJECTED</option></Select></FilterBar>
      {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><EndorsementTable rows={r.data!.items} actions={(e) => <div className="flex gap-1"><Link to={`/ops/policies/${e.policy_id}`}><Button size="sm" variant="ghost">Policy</Button></Link>
        {e.status === 'PENDING' && <><Button size="sm" variant="success" onClick={() => setDecide({ e, approve: true })}>Approve</Button><Button size="sm" variant="danger" onClick={() => setDecide({ e, approve: false })}>Reject</Button></>}</div>} />
        <Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card>
    <ConfirmDialog open={!!decide} onClose={() => setDecide(null)} danger={decide?.approve === false} title={`${decide?.approve ? 'Approve' : 'Reject'} ${decide?.e.endorsement_id}?`} confirmLabel={decide?.approve ? 'Approve' : 'Reject'} loading={dec.isPending} onConfirm={() => dec.mutate()}>
      <Field label="Reason (optional)"><Input aria-label="Decision reason" value={why} onChange={(e) => setWhy(e.target.value)} /></Field></ConfirmDialog></div>
}

export function Renewals() {
  const qc = useQueryClient(); const toast = useToast(); const { page, setPage, pageSize } = usePaging(1, 20)
  const [status, setStatus] = useState(''); const [gen, setGen] = useState(false); const [pid, setPid] = useState(''); const [asOf, setAsOf] = useState('')
  const r = useQuery({ queryKey: ['ops', 'renewals', page, status], queryFn: () => api.ops.renewals({ page, page_size: pageSize, status }), placeholderData: (p) => p })
  const done = () => qc.invalidateQueries({ queryKey: ['ops'] })
  const g = useMutation({ mutationFn: () => api.ops.generateRenewal(pid.trim(), asOf || undefined), onSuccess: (x) => { toast.success(`Renewal ${x.renewal_id}: ${title(x.status)}`); setGen(false); done() }, onError: (e) => toast.error(e) })
  const respond = useMutation({ mutationFn: (v: { r: Renewal; accept: boolean }) => v.accept ? api.ops.acceptRenewal(v.r.renewal_id) : api.ops.declineRenewal(v.r.renewal_id, 'Declined by operations'), onSuccess: () => { toast.success('Renewal updated'); done() }, onError: (e) => toast.error(e) })
  return <div><PageHeader title="Renewals" subtitle="Cancelled policies can never receive a valid renewal offer." actions={<Button onClick={() => setGen(true)}>Generate renewal</Button>} />
    <Card><FilterBar><Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}><option value="">All statuses</option>{['OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELLED'].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select></FilterBar>
      {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><RenewalTable rows={r.data!.items} linkBase="/ops/policies" actions={(x) => x.status === 'OFFERED' ? <div className="flex gap-1"><Button size="sm" onClick={() => respond.mutate({ r: x, accept: true })}>Accept</Button><Button size="sm" variant="secondary" onClick={() => respond.mutate({ r: x, accept: false })}>Decline</Button></div> : null} />
        <Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card>
    <Modal open={gen} onClose={() => setGen(false)} title="Generate renewal offer" footer={<><Button variant="secondary" onClick={() => setGen(false)}>Cancel</Button><Button loading={g.isPending} disabled={!pid.trim()} onClick={() => g.mutate()}>Generate</Button></>}>
      <div className="space-y-3"><Field label="Policy ID" required><Input aria-label="Policy ID" placeholder="POL-2026-000001" value={pid} onChange={(e) => setPid(e.target.value)} /></Field>
        <Field label="As-of date (optional)" hint="Must fall inside the 60-day window before expiry."><Input aria-label="As-of date" type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></Field></div></Modal></div>
}
