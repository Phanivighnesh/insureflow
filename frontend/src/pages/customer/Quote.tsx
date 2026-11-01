import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, CreditCard, RefreshCw } from 'lucide-react'
import { api } from '../../auth/AuthContext'
import type { Payment, QuoteDetail } from '../../api/types'
import { Badge, Button, Card, CardBody, CardHeader, ConfirmDialog, ErrorState, Field, Input, KV, PageHeader, Select, Spinner, StatusBadge, cn, useToast } from '../../components/ui'
import { DecisionList, EligibilityChecks, OutcomeBanner, PremiumCard, QuoteFacts, RiskPanel } from '../../components/domain'
import { date, dateTime, money, uuid } from '../../lib/format'
import { useProducts } from './Public'

export default function QuotePage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['my', 'quote', id], queryFn: () => api.customer.quote(id),
    refetchInterval: (query) => (['REFERRED'].includes(query.state.data?.status ?? '') ? 6000 : false) })   // pick up the underwriter's decision
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const quote = q.data!
  const refresh = (nq?: QuoteDetail) => { if (nq) qc.setQueryData(['my', 'quote', id], nq); qc.invalidateQueries({ queryKey: ['my'] }) }
  return <div data-testid="quote-page" data-quote-id={quote.quote_id}>
    <PageHeader title={<>Quote <span className="font-mono">{quote.quote_id}</span></>} subtitle={`${quote.demo_notice} · rules ${quote.rules_version}`}
      actions={<Button variant="secondary" size="sm" onClick={() => q.refetch()}><RefreshCw className={cn('h-4 w-4', q.isFetching && 'animate-spin')} />Refresh</Button>} />
    <OutcomeBanner quote={quote} />
    {quote.status === 'REFERRED' && <p className="mt-2 text-sm text-slate-500">This page refreshes automatically — an underwriter will decide shortly.</p>}
    <div className="mt-6 grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card><CardHeader title="Underwriting decision" subtitle="Every rule that applied is listed with its ID." /><CardBody>
          {quote.decision && <DecisionList decisions={quote.decision_history} />}
          <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-slate-700">{quote.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul></CardBody></Card>
        {quote.eligibility && <Card><CardHeader title="Eligibility checks" action={<StatusBadge status={quote.eligibility.status} />} /><CardBody><EligibilityChecks checks={quote.eligibility.checks} /></CardBody></Card>}
        {quote.risk && <Card><CardHeader title="Risk assessment" /><CardBody><RiskPanel risk={quote.risk} /></CardBody></Card>}
        {quote.payments.length > 0 && <Card><CardHeader title="Payments (DEMO)" /><CardBody><PaymentList payments={quote.payments} /></CardBody></Card>}
      </div>
      <div className="space-y-6">
        {quote.premium !== null && quote.premium_breakdown && <PremiumCard pb={quote.premium_breakdown} />}
        <Actions quote={quote} onChange={refresh} />
        <QuoteFacts q={quote} />
      </div></div></div>
}

function PaymentList({ payments }: { payments: Payment[] }) {
  return <ul className="divide-y divide-slate-100 text-sm">{payments.map((p) => <li key={p.payment_id} className="flex items-center justify-between py-2">
    <span className="font-mono text-xs text-slate-500">{p.payment_id}</span><span>{money(p.amount)}</span><StatusBadge status={p.status} /><span className="text-xs text-slate-500">{dateTime(p.created_at)}</span></li>)}</ul>
}

function Actions({ quote, onChange }: { quote: QuoteDetail; onChange: (q?: QuoteDetail) => void }) {
  const toast = useToast()
  const [confirm, setConfirm] = useState(false)
  const accept = useMutation({ mutationFn: () => api.customer.accept(quote.quote_id),
    onSuccess: (r) => { toast.success('Quote accepted. Next: complete the demo payment.'); setConfirm(false); onChange(r.quote) }, onError: (e) => { toast.error(e); setConfirm(false) } })
  if (quote.status === 'APPROVED') return <Card><CardHeader title="Your offer" /><CardBody>
    <div className="text-3xl font-semibold" data-testid="offer-premium">{money(quote.premium)}<span className="text-sm font-normal text-slate-500"> / year</span></div>
    <p className="mt-1 text-sm text-slate-500">Valid until {date(quote.valid_until)}</p>
    <Button className="mt-4 w-full" onClick={() => setConfirm(true)} data-testid="accept-quote">Accept this quote<ArrowRight className="h-4 w-4" /></Button>
    <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => accept.mutate()} loading={accept.isPending} title="Accept this quote?" confirmLabel="Accept quote">
      <p className="text-sm text-slate-600">You are accepting a {money(quote.premium)} annual premium for {money(quote.requested_coverage, 0)} of cover. Acceptance is recorded with a timestamp. You will then complete a <b>demo</b> payment.</p></ConfirmDialog></CardBody></Card>
  if (quote.status === 'ACCEPTED') return <DemoPayment quote={quote} onChange={onChange} />
  if (quote.status === 'POLICY_ISSUED' && quote.policy_id) return <Card><CardHeader title="Policy issued" /><CardBody><p className="text-sm text-slate-600">Policy <b className="font-mono">{quote.policy_id}</b> is active.</p>
    <Link to={`/policies/${quote.policy_id}`}><Button className="mt-3 w-full" data-testid="view-policy">View policy<ArrowRight className="h-4 w-4" /></Button></Link></CardBody></Card>
  if (quote.status === 'PENDING_INFORMATION') return <ProvideInfo quote={quote} onChange={onChange} />
  return null
}

function DemoPayment({ quote, onChange }: { quote: QuoteDetail; onChange: (q?: QuoteDetail) => void }) {
  const toast = useToast()
  const [outcome, setOutcome] = useState<Payment['status']>('SUCCESS')
  const [key] = useState(uuid)
  const [attempt, setAttempt] = useState(0)
  const pending = quote.payments.find((p) => p.status === 'PENDING')
  const pay = useMutation({ mutationFn: () => api.customer.pay(quote.quote_id, { outcome, idempotency_key: `${key}-${attempt}` }),
    onSuccess: (r) => { setAttempt((a) => a + 1)
      if (r.policy) toast.success(`Payment successful — policy ${r.policy.policy_id} issued`)
      else if (r.payment.status === 'FAILED') toast.error(new Error('Demo payment FAILED — no policy was issued. You can try again.'))
      else toast.info('Demo payment is PENDING — resolve it below to continue.')
      onChange(r.quote) }, onError: (e) => toast.error(e) })
  const resolve = useMutation({ mutationFn: (o: 'SUCCESS' | 'FAILED') => api.customer.resolvePayment(pending!.payment_id, o),
    onSuccess: (r) => { toast[r.policy ? 'success' : 'info'](r.policy ? `Policy ${r.policy.policy_id} issued` : 'Pending payment marked failed'); onChange() }, onError: (e) => toast.error(e) })
  return <Card className="border-amber-300"><CardHeader title={<span className="flex items-center gap-2"><CreditCard className="h-4 w-4" />DEMO PAYMENT</span>} subtitle="No real payment is processed. No card details are collected." action={<Badge tone="amber">DEMO</Badge>} />
    <CardBody className="space-y-4"><KV k="Amount due" v={<span data-testid="amount-due">{money(quote.premium)}</span>} />
      {pending ? <div className="space-y-2 rounded-lg bg-amber-50 p-3 text-sm"><p>Payment <b className="font-mono">{pending.payment_id}</b> is pending. Simulate the bank's response:</p>
        <div className="flex gap-2"><Button size="sm" variant="success" loading={resolve.isPending} onClick={() => resolve.mutate('SUCCESS')} data-testid="resolve-success">Mark successful</Button>
          <Button size="sm" variant="danger" loading={resolve.isPending} onClick={() => resolve.mutate('FAILED')}>Mark failed</Button></div></div>
        : <><Field label="Simulate payment result"><Select value={outcome} onChange={(e) => setOutcome(e.target.value as Payment['status'])} data-testid="payment-outcome">
          <option value="SUCCESS">Successful payment</option><option value="FAILED">Failed payment</option><option value="PENDING">Pending payment</option></Select></Field>
          <Button className="w-full" loading={pay.isPending} onClick={() => pay.mutate()} data-testid="pay-demo">Pay {money(quote.premium)} (demo)</Button></>}
      <p className="text-xs text-slate-500">A policy is issued only after approval, your recorded acceptance and a successful payment.</p></CardBody></Card>
}

function ProvideInfo({ quote, onChange }: { quote: QuoteDetail; onChange: (q?: QuoteDetail) => void }) {
  const toast = useToast()
  const products = useProducts()
  const [vals, setVals] = useState<Record<string, string>>({})
  const prod = products.data?.products.find((p) => p.product_key === quote.product_key)
  const attrs = quote.asset.attributes ?? {}
  const missing = (prod?.asset_fields ?? []).filter((f) => attrs[f.name] == null && !(f.name === 'property_age_years' && attrs.year_built != null))
  const send = useMutation({ mutationFn: () => {
    const attributes: Record<string, unknown> = {}
    missing.forEach((f) => { const v = (vals[f.name] ?? '').trim(); if (v) attributes[f.name] = f.type === 'number' ? Number(v) : v })
    return api.customer.provideInfo(quote.quote_id, { attributes }) }, onSuccess: (r) => { toast.success('Information received — your application was re-evaluated'); onChange(r) }, onError: (e) => toast.error(e) })
  const missingNames = quote.eligibility?.missing_fields ?? []
  return <Card><CardHeader title="Provide missing information" subtitle={missingNames.length ? `Engine reports missing: ${missingNames.join(', ')}` : undefined} /><CardBody className="space-y-3">
    {!prod ? <Spinner /> : missing.length === 0 ? <p className="text-sm text-slate-600">All asset fields are on file. The remaining gap is applicant-level information; please contact support (demo: submit a new application).</p> :
      missing.map((f) => <Field key={f.name} label={f.label} required={f.required}>{f.type === 'number' ? <Input aria-label={f.label} type="number" value={vals[f.name] ?? ''} onChange={(e) => setVals({ ...vals, [f.name]: e.target.value })} />
        : <Select aria-label={f.label} value={vals[f.name] ?? ''} onChange={(e) => setVals({ ...vals, [f.name]: e.target.value })}><option value="">Select…</option>
          {(f.type === 'location' ? prod.locations.map((l) => ({ value: l, label: l })) : f.options!).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</Select>}</Field>)}
    {missing.length > 0 && <Button className="w-full" loading={send.isPending} onClick={() => send.mutate()} data-testid="submit-info">Submit information</Button>}</CardBody></Card>
}
