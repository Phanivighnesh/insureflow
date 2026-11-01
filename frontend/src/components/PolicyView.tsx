import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Endorsement, PolicyDetail, Renewal } from '../api/types'
import { date, dateTime, money, productLabel, title } from '../lib/format'
import { PremiumCard } from './domain'
import { Badge, Button, Card, CardBody, CardHeader, DataTable, EmptyState, Field, Input, KV, Modal, Select, StatusBadge, Textarea } from './ui'

export const ENDORSEMENT_TYPES = [['COVERAGE_ADJUSTMENT', 'Coverage adjustment'], ['DECLARED_VALUE_CHANGE', 'Change in declared value'], ['ASSET_MODIFICATION', 'Asset modification'], ['INSURED_INFO_CHANGE', 'Change in insured information']] as const
export type EndorseBody = { endorsement_type: string; effective_date: string; new_coverage_amount?: number; new_declared_value?: number; changes?: Record<string, unknown> }

export function EndorsementModal({ open, onClose, policy, onSubmit, loading }: { open: boolean; onClose: () => void; policy: PolicyDetail; onSubmit: (b: EndorseBody) => void; loading?: boolean }) {
  const today = new Date().toISOString().slice(0, 10)
  const clamp = (d: string) => (d < policy.start_date ? policy.start_date : d > policy.expiry_date ? policy.expiry_date : d)
  const [type, setType] = useState('COVERAGE_ADJUSTMENT'); const [cov, setCov] = useState(''); const [dv, setDv] = useState('')
  const [eff, setEff] = useState(clamp(today)); const [note, setNote] = useState('')
  const submit = () => onSubmit({ endorsement_type: type, effective_date: eff,
    ...(cov.trim() ? { new_coverage_amount: Number(cov) } : {}), ...(dv.trim() ? { new_declared_value: Number(dv) } : {}), ...(note.trim() ? { changes: { note: note.trim() } } : {}) })
  const needsAmounts = type !== 'INSURED_INFO_CHANGE'
  return <Modal open={open} onClose={onClose} title="Request a mid-term change (endorsement)" footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={loading} onClick={submit} data-testid="submit-endorsement">Submit request</Button></>}>
    <div className="space-y-3"><p className="text-xs text-slate-500">Current cover {money(policy.coverage_amount, 0)}. Requests beyond the product limit are rejected automatically and recorded. Your original policy is never overwritten.</p>
      <Field label="Type of change"><Select aria-label="Endorsement type" value={type} onChange={(e) => setType(e.target.value)}>{ENDORSEMENT_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
      {needsAmounts && <div className="grid grid-cols-2 gap-3"><Field label="New coverage (USD)"><Input aria-label="New coverage" type="number" value={cov} onChange={(e) => setCov(e.target.value)} /></Field>
        <Field label="New declared value (USD)"><Input aria-label="New declared value" type="number" value={dv} onChange={(e) => setDv(e.target.value)} /></Field></div>}
      <Field label="Effective date" hint={`Within policy period ${date(policy.start_date)} – ${date(policy.expiry_date)}`}><Input aria-label="Effective date" type="date" value={eff} min={policy.start_date} max={policy.expiry_date} onChange={(e) => setEff(e.target.value)} /></Field>
      <Field label="Details / note"><Textarea aria-label="Note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></Field></div></Modal>
}

export function EndorsementTable({ rows, actions }: { rows: Endorsement[]; actions?: (e: Endorsement) => ReactNode }) {
  return <DataTable rows={rows} rowKey={(e) => e.endorsement_id} empty={<EmptyState text="No endorsements" hint="Mid-term changes will appear here with full before/after history." />}
    columns={[{ header: 'Endorsement', cell: (e) => <span className="font-mono text-xs">{e.endorsement_id}</span> }, { header: 'Type', cell: (e) => title(e.endorsement_type) },
      { header: 'Coverage before → after', cell: (e) => `${money(e.coverage_before, 0)} → ${money(e.coverage_after, 0)}` },
      { header: 'Premium', cell: (e) => `${money(e.premium_before)} → ${e.premium_after === null ? '—' : money(e.premium_after)}` },
      { header: 'Effective', cell: (e) => date(e.effective_date) }, { header: 'Status', cell: (e) => <div><StatusBadge status={e.status} />{e.decision_reason && <div className="mt-1 max-w-xs text-xs text-slate-500">{e.decision_reason}</div>}</div> },
      ...(actions ? [{ header: '', cell: actions }] : [])]} />
}

export function RenewalTable({ rows, linkBase, actions }: { rows: Renewal[]; linkBase?: string; actions?: (r: Renewal) => ReactNode }) {
  return <DataTable rows={rows} rowKey={(r) => r.renewal_id} empty={<EmptyState text="No renewals" />}
    columns={[{ header: 'Renewal', cell: (r) => <span className="font-mono text-xs">{r.renewal_id}</span> }, { header: 'Policy', cell: (r) => linkBase ? <Link className="text-brand-600 hover:underline" to={`${linkBase}/${r.policy_id}`}>{r.policy_id}</Link> : r.policy_id },
      { header: 'New term', cell: (r) => `${date(r.new_start_date)} – ${date(r.new_expiry_date)}` }, { header: 'Offered premium', cell: (r) => money(r.offered_premium) },
      { header: 'Status', cell: (r) => <div><StatusBadge status={r.status} />{r.status === 'CANCELLED' && r.response_reason && <div className="max-w-xs text-xs text-slate-500">{r.response_reason}</div>}</div> },
      ...(actions ? [{ header: '', cell: actions }] : [])]} />
}

/** Read-only policy presentation shared by customer and operations; pages inject the action buttons. */
export function PolicyView({ policy, actions, renewalActions, endorsementActions, linkBase = '/policies' }:
  { policy: PolicyDetail; actions?: ReactNode; renewalActions?: (r: Renewal) => ReactNode; endorsementActions?: (e: Endorsement) => ReactNode; linkBase?: string }) {
  const re = policy.renewal_eligibility
  const pb = policy.snapshot.premium_breakdown
  return <div className="space-y-6" data-testid="policy-view" data-policy-id={policy.policy_id}>
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2"><CardHeader title={<span className="flex items-center gap-2"><span className="font-mono">{policy.policy_id}</span><StatusBadge status={policy.status} /></span>} subtitle={`${productLabel(policy.product_key)} · ${policy.coverage_name ?? title(policy.snapshot.coverage_code)}`} action={actions} />
        <CardBody><dl className="grid gap-x-10 md:grid-cols-2"><div className="divide-y divide-slate-100">
          <KV k="Policyholder" v={policy.applicant_name ?? '—'} /><KV k="Coverage amount" v={money(policy.coverage_amount, 0)} /><KV k="Annual premium" v={money(policy.premium)} />
          <KV k="Start date" v={date(policy.start_date)} /><KV k="Expiry date" v={date(policy.expiry_date)} /></div>
          <div className="divide-y divide-slate-100"><KV k="Asset" v={<span className="font-mono">{policy.asset_id}</span>} /><KV k="Origin quote" v={policy.quote_id ? <span className="font-mono">{policy.quote_id}</span> : '—'} />
            <KV k="Renewal of" v={policy.renewal_of_policy_id ?? '—'} /><KV k="Issued" v={dateTime(policy.issued_at)} />
            {policy.cancelled_at && <KV k="Cancelled" v={`${date(policy.cancelled_at)} — ${policy.cancellation_reason}`} />}</div></dl></CardBody></Card>
      <Card><CardHeader title="Renewal eligibility" /><CardBody className="space-y-2 text-sm">
        <div className="flex items-center gap-2">{re.eligible ? <Badge tone="green">Eligible now</Badge> : <Badge tone="slate">Not yet eligible</Badge>}</div>
        <p className="text-slate-600">Renewal window: {date(re.window_start)} – {date(re.window_end)}</p>
        {re.renewal_id && <p>Renewal on file: <span className="font-mono">{re.renewal_id}</span></p>}
        {!re.eligible && re.reasons.length > 0 && <ul className="list-disc pl-5 text-xs text-slate-500">{re.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}</CardBody></Card></div>
    <div className="grid gap-6 lg:grid-cols-2">
      {pb ? <PremiumCard pb={pb} title="Premium breakdown (at issue)" /> : <Card><CardBody><EmptyState text="No premium snapshot" /></CardBody></Card>}
      <Card><CardHeader title="Lifecycle timeline" /><CardBody><ol className="space-y-3 border-l border-slate-200 pl-5 text-sm">{policy.status_history.map((h, i) => <li key={i} className="relative">
        <span className="absolute -left-[26px] mt-1 h-3 w-3 rounded-full border-2 border-white bg-brand-500" /><div className="font-medium">{h.from_status ? `${title(h.from_status)} → ` : ''}{title(h.to_status)}</div>
        <div className="text-xs text-slate-500">{dateTime(h.changed_at)} · {h.changed_by}{h.reason ? ` · ${h.reason}` : ''}</div></li>)}</ol></CardBody></Card></div>
    <Card><CardHeader title="Endorsement history" subtitle="Original policy terms are preserved; effective terms follow the latest approved endorsement." /><EndorsementTable rows={policy.endorsements} actions={endorsementActions} /></Card>
    <Card><CardHeader title="Renewals" /><RenewalTable rows={policy.renewals} actions={renewalActions} linkBase={linkBase} /></Card>
    {policy.payments.length > 0 && <Card><CardHeader title="Payments (DEMO)" /><CardBody><ul className="divide-y divide-slate-100 text-sm">{policy.payments.map((p) => <li key={p.payment_id} className="flex justify-between py-2"><span className="font-mono text-xs">{p.payment_id}</span><span>{money(p.amount)}</span><StatusBadge status={p.status} /><span className="text-xs text-slate-500">{dateTime(p.created_at)}</span></li>)}</ul></CardBody></Card>}
  </div>
}
