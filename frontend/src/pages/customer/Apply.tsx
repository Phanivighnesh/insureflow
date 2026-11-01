import { useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Check, ChevronLeft, ChevronRight, Send } from 'lucide-react'
import { api } from '../../auth/AuthContext'
import { ApiError } from '../../api/client'
import type { FormField, ProductInfo, QuoteRequest } from '../../api/types'
import { Button, Card, CardBody, ErrorState, Field, Input, PageHeader, Select, Spinner, cn, useToast } from '../../components/ui'
import { money, productLabel, title } from '../../lib/format'
import { clearPrefill, takePrefill } from '../../lib/prefill'
import { ScenarioPanel, useProducts } from './Public'

const RULES_AS_OF_YEAR = 2026   // backend AS_OF_YEAR; only used to convert a prefilled year_built into the "property age" field

interface Form {
  full_name: string; email: string; phone: string; age: string; location: string
  declared_value: string; asset_location: string; attrs: Record<string, string>
  coverage_code: string; requested_coverage: string
}
const blank = (p: ProductInfo): Form => ({ full_name: '', email: '', phone: '', age: '', location: '', declared_value: '', asset_location: '', attrs: {},
  coverage_code: p.coverage_options[1]?.code ?? p.coverage_options[0].code, requested_coverage: '' })

function fromPayload(p: ProductInfo, r: QuoteRequest): Form {
  const attrs: Record<string, string> = {}
  const src = { ...(r.asset.attributes ?? {}) } as Record<string, unknown>
  if (p.product_key === 'PROPERTY' && src.year_built != null && src.property_age_years == null) src.property_age_years = RULES_AS_OF_YEAR - Number(src.year_built)
  p.asset_fields.forEach((f) => { if (src[f.name] != null) attrs[f.name] = String(src[f.name]) })
  return { full_name: r.applicant.full_name ?? '', email: r.applicant.email ?? '', phone: r.applicant.phone ?? '', age: r.applicant.age != null ? String(r.applicant.age) : '',
    location: r.applicant.location ?? '', declared_value: r.asset.declared_value != null ? String(r.asset.declared_value) : '', asset_location: r.asset.location ?? '', attrs,
    coverage_code: r.coverage_code ?? p.coverage_options[0].code, requested_coverage: r.requested_coverage != null ? String(r.requested_coverage) : '' }
}

function toPayload(p: ProductInfo, f: Form): QuoteRequest {
  const n = (s: string) => (s.trim() === '' ? null : Number(s))
  const attributes: Record<string, unknown> = {}
  p.asset_fields.forEach((fld) => { const v = (f.attrs[fld.name] ?? '').trim(); if (v !== '') attributes[fld.name] = fld.type === 'number' ? Number(v) : v })
  return { product_key: p.product_key, coverage_code: f.coverage_code || null, requested_coverage: n(f.requested_coverage),
    applicant: { full_name: f.full_name.trim(), email: f.email.trim() || null, phone: f.phone.trim() || null, age: n(f.age), location: f.location || null,
      applicant_type: p.product_key === 'COMMERCIAL' ? 'BUSINESS' : 'INDIVIDUAL' },
    asset: { declared_value: n(f.declared_value), location: f.asset_location || null, attributes } }
}

const STEPS = ['Applicant', 'Asset', 'Coverage', 'Review']

export default function Apply() {
  const { product = '' } = useParams()
  const loc = useLocation()
  const q = useProducts()
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const p = q.data!.products.find((x) => x.product_key === product.toUpperCase())
  if (!p) return <Navigate to="/products" replace />
  return <Wizard key={p.product_key + loc.key} p={p} />
}

function Wizard({ p }: { p: ProductInfo }) {
  const nav = useNavigate(); const qc = useQueryClient(); const toast = useToast()
  const [prefilled] = useState(() => takePrefill(p.product_key))
  const [f, setF] = useState<Form>(() => (prefilled ? fromPayload(p, prefilled) : blank(p)))
  const [step, setStep] = useState(0)
  const [serverErr, setServerErr] = useState<ApiError | null>(null)
  const set = (patch: Partial<Form>) => setF((x) => ({ ...x, ...patch }))
  const setAttr = (k: string, v: string) => setF((x) => ({ ...x, attrs: { ...x.attrs, [k]: v } }))

  const submit = useMutation({
    mutationFn: () => api.customer.submitQuote(toPayload(p, f)),
    onSuccess: (quote) => { clearPrefill(); qc.invalidateQueries({ queryKey: ['my'] }); toast.success(`Application ${quote.quote_id} evaluated`); nav(`/quotes/${quote.quote_id}`) },
    onError: (e) => { setServerErr(e as ApiError); toast.error(e) },
  })

  const cov = p.coverage_options.find((c) => c.code === f.coverage_code)
  const req = f.requested_coverage.trim() === '' ? null : Number(f.requested_coverage)
  const dv = f.declared_value.trim() === '' ? null : Number(f.declared_value)
  const warnings = useMemo(() => {
    const w: string[] = []
    if (!f.age.trim()) w.push('Applicant age is required for eligibility.')
    if (!f.declared_value.trim()) w.push('Declared asset value is required.')
    if (!f.asset_location) w.push('Asset location is required.')
    p.asset_fields.filter((x) => x.required && !(f.attrs[x.name] ?? '').trim()).forEach((x) => w.push(`${x.label} is required — leaving it blank will result in “More information needed”.`))
    if (req === null) w.push('Requested coverage is required.')
    if (cov && req !== null && (req < cov.min_limit || req > cov.max_limit)) w.push(`Requested coverage is outside the ${cov.name} limits (${money(cov.min_limit, 0)}–${money(cov.max_limit, 0)}).`)
    if (req !== null && dv !== null && req > dv * p.eligibility.max_coverage_to_value_ratio) w.push('Requested coverage exceeds the declared asset value.')
    return w
  }, [f, p, cov, req, dv])
  const nameOk = f.full_name.trim().length > 0
  const numbersOk = [f.age, f.declared_value, f.requested_coverage, ...p.asset_fields.filter((x) => x.type === 'number').map((x) => f.attrs[x.name] ?? '')].every((s) => s.trim() === '' || !Number.isNaN(Number(s)))

  const Locations = ({ value, onChange, id, label }: { value: string; onChange: (v: string) => void; id: string; label: string }) =>
    <Field label={label}><Select id={id} value={value} onChange={(e) => onChange(e.target.value)}><option value="">Select location…</option>{p.locations.map((l) => <option key={l}>{l}</option>)}</Select></Field>

  const renderField = (fld: FormField) => {
    const v = f.attrs[fld.name] ?? ''; const miss = fld.required && !v.trim()
    const hint = miss ? 'Required' : undefined
    if (fld.type === 'select') return <Field key={fld.name} label={fld.label} required={fld.required} hint={hint}><Select aria-label={fld.label} value={v} onChange={(e) => setAttr(fld.name, e.target.value)}><option value="">Select…</option>{fld.options!.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</Select></Field>
    if (fld.type === 'location') return <Field key={fld.name} label={fld.label} required={fld.required} hint={hint}><Select aria-label={fld.label} value={v} onChange={(e) => setAttr(fld.name, e.target.value)}><option value="">Select location…</option>{p.locations.map((l) => <option key={l}>{l}</option>)}</Select></Field>
    return <Field key={fld.name} label={fld.label} required={fld.required} hint={hint}><Input aria-label={fld.label} type="number" min={fld.min} max={fld.max} value={v} onChange={(e) => setAttr(fld.name, e.target.value)} /></Field>
  }

  return <div>
    <PageHeader title={`${productLabel(p.product_key)} — application`} subtitle="Your answers are sent to the underwriting engine exactly as entered; the result is computed by the backend." />
    {prefilled && <p className="mb-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-900" data-testid="prefill-notice">Demo scenario loaded — review the prefilled details and submit to see the real backend decision.</p>}
    <ol className="mb-6 flex items-center gap-2 text-sm" aria-label="Progress">{STEPS.map((s, i) => <li key={s} className="flex items-center gap-2">
      <span className={cn('flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold', i < step ? 'bg-emerald-600 text-white' : i === step ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-600')}>{i < step ? <Check className="h-4 w-4" /> : i + 1}</span>
      <span className={cn('hidden sm:inline', i === step ? 'font-medium' : 'text-slate-500')}>{s}</span>{i < STEPS.length - 1 && <span className="h-px w-6 bg-slate-300" />}</li>)}</ol>
    <Card><CardBody>
      {step === 0 && <div className="grid gap-4 md:grid-cols-2">
        <Field label={p.product_key === 'COMMERCIAL' ? 'Business name' : 'Full name'} required error={!nameOk && step === 0 ? undefined : undefined}><Input aria-label="Full name" value={f.full_name} onChange={(e) => set({ full_name: e.target.value })} /></Field>
        <Field label="Email"><Input aria-label="Email" type="email" value={f.email} onChange={(e) => set({ email: e.target.value })} /></Field>
        <Field label="Phone"><Input aria-label="Phone" value={f.phone} onChange={(e) => set({ phone: e.target.value })} /></Field>
        <Field label="Age" required hint={`Eligible ages ${p.eligibility.applicant_age[0]}–${p.eligibility.applicant_age[1]}`}><Input aria-label="Age" type="number" value={f.age} onChange={(e) => set({ age: e.target.value })} /></Field>
        <Locations id="loc" label="Location" value={f.location} onChange={(v) => set({ location: v })} /></div>}
      {step === 1 && <div className="grid gap-4 md:grid-cols-2">
        <Field label="Declared asset value (USD)" required hint={`Insurable range ${money(p.eligibility.insured_value[0], 0)}–${money(p.eligibility.insured_value[1], 0)}`}><Input aria-label="Declared value" type="number" min={0} value={f.declared_value} onChange={(e) => set({ declared_value: e.target.value })} /></Field>
        <Locations id="aloc" label="Asset location" value={f.asset_location} onChange={(v) => set({ asset_location: v })} />
        {p.asset_fields.map(renderField)}</div>}
      {step === 2 && <div className="space-y-4"><fieldset><legend className="mb-2 text-sm font-medium">Coverage option</legend>
        <div className="grid gap-3 md:grid-cols-3">{p.coverage_options.map((c) => <label key={c.code} className={cn('cursor-pointer rounded-lg border p-3 text-sm', f.coverage_code === c.code ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500' : 'border-slate-200 hover:bg-slate-50')}>
          <input type="radio" name="coverage" className="sr-only" checked={f.coverage_code === c.code} onChange={() => set({ coverage_code: c.code })} aria-label={c.name} /><div className="font-medium">{c.name}</div><div className="text-slate-500">{money(c.min_limit, 0)} – {money(c.max_limit, 0)}</div></label>)}</div></fieldset>
        <Field label="Requested sum insured (USD)" required hint={cov ? `${cov.name} limits ${money(cov.min_limit, 0)}–${money(cov.max_limit, 0)}; cannot exceed declared value${dv ? ` (${money(dv, 0)})` : ''}` : undefined}>
          <Input aria-label="Requested coverage" type="number" min={0} value={f.requested_coverage} onChange={(e) => set({ requested_coverage: e.target.value })} /></Field></div>}
      {step === 3 && <div className="space-y-4 text-sm"><h3 className="text-base font-semibold">Review your application</h3>
        <dl className="grid gap-x-8 gap-y-1 md:grid-cols-2">{[['Applicant', f.full_name], ['Age', f.age || '—'], ['Email', f.email || '—'], ['Location', f.location || '—'], ['Declared value', money(dv, 0)], ['Asset location', f.asset_location || '—'],
          ...p.asset_fields.map((x) => [x.label, f.attrs[x.name] ? title(f.attrs[x.name]) : '—'] as [string, string]), ['Coverage', cov?.name ?? '—'], ['Requested cover', money(req, 0)]].map(([k, v]) =>
          <div key={k as string} className="flex justify-between border-b border-slate-100 py-1"><dt className="text-slate-500">{k}</dt><dd className="font-medium">{v}</dd></div>)}</dl>
        {warnings.length > 0 && <div role="note" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900"><div className="mb-1 flex items-center gap-2 font-medium"><AlertCircle className="h-4 w-4" />Heads-up (you can still submit)</div>
          <ul className="list-disc pl-5">{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul><p className="mt-1 text-xs">The backend is authoritative: it will either explain the failed rule or request the missing information.</p></div>}
        {serverErr && <ErrorState error={serverErr} />}</div>}
      <div className="mt-6 flex justify-between"><Button variant="secondary" disabled={step === 0} onClick={() => setStep(step - 1)}><ChevronLeft className="h-4 w-4" />Back</Button>
        {step < 3 ? <Button onClick={() => setStep(step + 1)} disabled={step === 0 && !nameOk}>Continue<ChevronRight className="h-4 w-4" /></Button>
          : <Button loading={submit.isPending} disabled={!nameOk || !numbersOk} onClick={() => { setServerErr(null); submit.mutate() }} data-testid="submit-application"><Send className="h-4 w-4" />Submit application</Button>}</div>
    </CardBody></Card>
    {!prefilled && <div className="mt-10"><ScenarioPanel /></div>}
  </div>
}
