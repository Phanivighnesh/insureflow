import { useState } from 'react'
import { CheckCircle2, CircleSlash, Clock, FileSearch, ShieldAlert, XCircle, MinusCircle } from 'lucide-react'
import type { AuditEvent, Decision, EligibilityCheck, PremiumBreakdown, QuoteDetail, RiskFactor } from '../api/types'
import { date, dateTime, money, productLabel, title } from '../lib/format'
import { Badge, Card, CardBody, CardHeader, KV, StatusBadge, cn } from './ui'

export function usePaging(initial = 1, size = 15) {
  const [page, setPage] = useState(initial)
  return { page, setPage, pageSize: size }
}

const OUTCOME = {
  APPROVED: { icon: CheckCircle2, cls: 'border-emerald-200 bg-emerald-50 text-emerald-900', head: 'Approved', sub: 'Your application met the underwriting rules. Review the offer below and accept it to continue.' },
  REFERRED: { icon: Clock, cls: 'border-amber-200 bg-amber-50 text-amber-900', head: 'Referred for manual review', sub: 'An underwriter must review this application before an offer can be made.' },
  DECLINED: { icon: XCircle, cls: 'border-red-200 bg-red-50 text-red-900', head: 'Declined', sub: 'This application cannot be offered cover under the configured product rules.' },
  PENDING_INFORMATION: { icon: FileSearch, cls: 'border-amber-200 bg-amber-50 text-amber-900', head: 'More information needed', sub: 'Mandatory risk information is missing. Provide it to continue — missing data is never treated as zero risk.' },
  ACCEPTED: { icon: CheckCircle2, cls: 'border-emerald-200 bg-emerald-50 text-emerald-900', head: 'Quote accepted', sub: 'Complete the DEMO payment to issue your policy.' },
  POLICY_ISSUED: { icon: CheckCircle2, cls: 'border-emerald-200 bg-emerald-50 text-emerald-900', head: 'Policy issued', sub: 'Your cover is active.' },
  EXPIRED: { icon: CircleSlash, cls: 'border-slate-200 bg-slate-50 text-slate-800', head: 'Quote expired', sub: 'This quote is no longer valid.' },
} as const

export function OutcomeBanner({ quote }: { quote: Pick<QuoteDetail, 'status' | 'quote_id'> }) {
  const o = OUTCOME[quote.status] ?? OUTCOME.EXPIRED
  const Icon = o.icon
  return <div data-testid="outcome-banner" data-status={quote.status} className={cn('flex items-start gap-3 rounded-xl border p-4', o.cls)}>
    <Icon className="mt-0.5 h-6 w-6 shrink-0" /><div><div className="text-lg font-semibold">{o.head}</div><p className="text-sm opacity-90">{o.sub}</p></div></div>
}

export function EligibilityChecks({ checks }: { checks: EligibilityCheck[] }) {
  return <ul className="divide-y divide-slate-100 text-sm">{checks.map((c, i) => <li key={i} className="flex items-start gap-3 py-2">
    {c.passed === true ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : c.passed === false ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" /> : <MinusCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />}
    <div className="flex-1"><div className="font-medium text-slate-800">{c.name} <span className="font-normal text-slate-400">· {c.rule_id}</span></div><div className="text-slate-600">{c.message}</div></div></li>)}</ul>
}

export function RiskPanel({ risk }: { risk: NonNullable<QuoteDetail['risk']> }) {
  const max = Math.max(...risk.factors.map((f: RiskFactor) => f.contribution), 1)
  return <div>
    <div className="mb-3 flex items-center gap-3"><div className="text-3xl font-semibold">{risk.score.toFixed(1)}</div><StatusBadge status={risk.category} /><span className="text-sm text-slate-500">of 100</span></div>
    <p className="mb-3 text-sm text-slate-600">{risk.explanation}</p>
    <div className="space-y-2">{risk.factors.map((f) => <div key={f.rsk_id} className="text-sm">
      <div className="flex justify-between"><span className="text-slate-700">{f.label}{f.penalised_missing && <Badge tone="amber" className="ml-2">missing — penalised</Badge>}</span>
        <span className="text-slate-500">{String(f.input_value ?? '—')} · w{f.weight} · <b className="text-slate-800">{f.contribution.toFixed(1)}</b></span></div>
      <div className="mt-1 h-1.5 rounded bg-slate-100"><div className={cn('h-1.5 rounded', f.penalised_missing ? 'bg-amber-500' : 'bg-brand-500')} style={{ width: `${(f.contribution / max) * 100}%` }} /></div></div>)}</div></div>
}

export function PremiumCard({ pb, title: t = 'Premium breakdown' }: { pb: PremiumBreakdown; title?: string }) {
  const f = pb.factors
  return <Card data-testid="premium-card"><CardHeader title={t} subtitle={`Formula ${pb.formula_version} · rules ${pb.rules_version} · all amounts in ${pb.currency}`} />
    <CardBody><dl className="divide-y divide-slate-100">
      <KV k={<>Base premium <span className="text-slate-400">(coverage × {pb.base_rate} × {pb.coverage_rate_multiplier})</span></>} v={money(pb.base_premium)} />
      <KV k="Age factor" v={`× ${f.age.toFixed(2)}`} /><KV k="Location factor" v={`× ${f.location.toFixed(2)}`} />
      <KV k="Claims factor" v={`× ${f.claims.toFixed(2)}`} /><KV k="Risk factor" v={`× ${f.risk.toFixed(2)}`} />
      <KV k="Adjusted premium" v={money(pb.adjusted_premium)} />
      {Object.entries(pb.charges).map(([k, v]) => <KV key={k} k={title(k)} v={money(v)} />)}
      <div className="flex justify-between pt-3 text-base font-semibold"><dt>Total annual premium</dt><dd data-testid="final-premium">{money(pb.final_premium)}</dd></div></dl>
      <p className="mt-3 text-xs text-slate-500">Calculated deterministically from the stored inputs; independently re-verifiable.</p></CardBody></Card>
}

export function DecisionList({ decisions }: { decisions: Decision[] }) {
  return <ol className="space-y-3">{decisions.map((d) => <li key={d.decision_id} className="rounded-lg border border-slate-200 p-3 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><span className="font-mono text-xs text-slate-500">#{d.sequence} {d.decision_id}</span><StatusBadge status={d.outcome} /><Badge>{d.decision_type}</Badge></div><span className="text-xs text-slate-500">{dateTime(d.decided_at)}</span></div>
    <ul className="mt-2 list-disc space-y-0.5 pl-5 text-slate-700">{d.reasons.map((r, i) => <li key={i}><code className="rounded bg-slate-100 px-1 text-xs">{r.rule_id}</code> {r.message}</li>)}</ul>
    <div className="mt-2 text-xs text-slate-500">Authority: {title(d.approval_authority)} · by {d.decided_by} ({title(d.decided_role)}) · engine {d.rule_engine_version}{d.notes ? ` · note: ${d.notes}` : ''}</div></li>)}</ol>
}

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  if (!events.length) return <p className="text-sm text-slate-500">No audit events.</p>
  return <ol className="relative space-y-3 border-l border-slate-200 pl-5">{events.map((e) => <li key={e.audit_id} className="text-sm">
    <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-brand-500" />
    <div className="flex flex-wrap items-center gap-2"><b>{title(e.event_type)}</b><span className="text-xs text-slate-500">{e.entity_type} {e.entity_id}</span><span className="text-xs text-slate-400">{dateTime(e.occurred_at)}</span></div>
    <div className="text-xs text-slate-500">{e.actor} ({title(e.actor_role)}){e.payload && Object.keys(e.payload).length ? ` · ${JSON.stringify(e.payload).slice(0, 160)}` : ''}</div></li>)}</ol>
}

export function QuoteFacts({ q }: { q: QuoteDetail }) {
  return <Card><CardHeader title="Application details" /><CardBody><dl className="divide-y divide-slate-100">
    <KV k="Quote" v={<span className="font-mono">{q.quote_id}</span>} /><KV k="Product" v={productLabel(q.product_key)} />
    <KV k="Applicant" v={`${q.applicant.full_name}${q.applicant.age ? `, ${q.applicant.age}` : ''}`} /><KV k="Asset" v={<span className="font-mono">{q.asset.asset_id}</span>} />
    <KV k="Declared value" v={money(q.asset.declared_value, 0)} /><KV k="Requested coverage" v={`${money(q.requested_coverage, 0)} · ${title(q.coverage_code)}`} />
    <KV k="Eligibility" v={<StatusBadge status={q.eligibility_status} />} /><KV k="Risk" v={q.risk_score === null ? '—' : <span>{q.risk_score.toFixed(1)} <StatusBadge status={q.risk_category} /></span>} />
    <KV k="Quote valid until" v={date(q.valid_until)} /><KV k="Submitted" v={dateTime(q.created_at)} /></dl></CardBody></Card>
}

export function ErrorIcon() { return <ShieldAlert className="h-5 w-5" /> }
