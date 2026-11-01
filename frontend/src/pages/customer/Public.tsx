import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Building, Car, Home, PlayCircle, ShieldCheck, BadgeCheck, Gauge, Receipt } from 'lucide-react'
import { api, useAuth } from '../../auth/AuthContext'
import type { ProductInfo, Scenario } from '../../api/types'
import { Badge, Button, Card, CardBody, ErrorState, Field, Input, PageHeader, Spinner, useToast } from '../../components/ui'
import { money, productLabel } from '../../lib/format'
import { savePrefill } from '../../lib/prefill'

const ICON = { MOTOR: Car, PROPERTY: Home, COMMERCIAL: Building } as const
const BLURB = { MOTOR: 'Cover your car, motorbike or truck against accident, theft and fire.', PROPERTY: 'Protect your home — buildings, and optionally contents and flood.', COMMERCIAL: 'Property, business interruption and all-risks cover for your business.' } as const

export function useProducts() { return useQuery({ queryKey: ['products'], queryFn: () => api.customer.products(), staleTime: 300000 }) }

export function ScenarioPanel() {
  const nav = useNavigate()
  const q = useQuery({ queryKey: ['scenarios'], queryFn: () => api.customer.scenarios() })
  const load = (s: Scenario) => { savePrefill(s.payload); nav(`/apply/${s.payload.product_key}`) }
  return <section aria-labelledby="demo-scn" className="rounded-2xl border border-brand-200 bg-brand-50/60 p-6">
    <div className="mb-1 flex items-center gap-2"><PlayCircle className="h-5 w-5 text-brand-600" /><h2 id="demo-scn" className="text-lg font-semibold">Try Demo Scenarios</h2><Badge tone="blue">DEMO</Badge></div>
    <p className="mb-4 text-sm text-slate-600">Prefilled example applications. Submitting one runs the <b>real backend workflow</b> — the outcome is computed by the underwriting engine, not scripted.</p>
    {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      {q.data!.scenarios.map((s) => <Card key={s.id} className="flex flex-col p-4"><div className="font-medium">{s.title}</div><div className="mb-3 text-xs text-slate-500">{productLabel(s.payload.product_key)} · {s.intent}</div>
        <Button size="sm" variant="secondary" className="mt-auto" data-testid={`scenario-${s.id}`} onClick={() => load(s)}>Load into application <ArrowRight className="h-3.5 w-3.5" /></Button></Card>)}</div>}
  </section>
}

export function Landing() {
  const { data } = useProducts()
  return <div className="space-y-12">
    <section className="rounded-3xl bg-gradient-to-br from-brand-700 to-brand-900 px-8 py-14 text-white">
      <Badge tone="blue" className="mb-4">Smart Insurance Operations Platform</Badge>
      <h1 className="max-w-2xl text-4xl font-semibold tracking-tight">Instant, explainable insurance quotes — from application to policy.</h1>
      <p className="mt-4 max-w-xl text-brand-100">Every decision is produced by a deterministic rules engine with a full audit trail. Underwriters review exactly what you submit.</p>
      <div className="mt-8 flex flex-wrap gap-3"><Link to="/products"><Button className="bg-white !text-brand-700 hover:!bg-brand-50">Get a quote <ArrowRight className="h-4 w-4" /></Button></Link>
        <Link to="/login"><Button variant="secondary" className="!border-white/30 !bg-white/10 !text-white hover:!bg-white/20">Try the demo</Button></Link></div></section>
    <section className="grid gap-4 md:grid-cols-3">{(['MOTOR', 'PROPERTY', 'COMMERCIAL'] as const).map((k) => { const I = ICON[k]; const p = data?.products.find((x) => x.product_key === k)
      return <Card key={k} className="p-6"><I className="mb-3 h-8 w-8 text-brand-600" /><h3 className="text-lg font-semibold">{productLabel(k)}</h3><p className="mt-1 text-sm text-slate-600">{BLURB[k]}</p>
        {p && <p className="mt-3 text-xs text-slate-500">Cover up to {money(Math.max(...p.coverage_options.map((c) => c.max_limit)), 0)}</p>}
        <Link to={`/apply/${k}`} className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">Get a quote <ArrowRight className="h-3.5 w-3.5" /></Link></Card> })}</section>
    <section className="grid gap-4 text-sm md:grid-cols-3">{[[BadgeCheck, 'Transparent decisions', 'Eligibility checks, risk factors and rule IDs are shown for every outcome.'], [Gauge, 'Reproducible premiums', 'Premium = rate × coverage × documented factors. Re-calculable from stored inputs.'], [Receipt, 'Demo payment', 'Payment is simulated (success / failed / pending). No card details are ever collected.']].map(([I, t, d]) => { const Icon = I as typeof BadgeCheck
      return <div key={t as string} className="flex gap-3"><Icon className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" /><div><div className="font-medium">{t as string}</div><div className="text-slate-600">{d as string}</div></div></div> })}</section>
  </div>
}

export function CustomerLogin() {
  const { login, session, isStaff, expired } = useAuth()
  const nav = useNavigate(); const loc = useLocation(); const toast = useToast()
  const [name, setName] = useState(''); const [busy, setBusy] = useState(false)
  const from = (loc.state as { from?: string; wrongArea?: boolean } | null)
  const go = async () => { setBusy(true); try { await login('CUSTOMER', { name: name.trim() || 'Demo Customer' }); nav(from?.from && !from.from.startsWith('/ops') ? from.from : '/dashboard', { replace: true }) } catch (e) { toast.error(e) } finally { setBusy(false) } }
  return <div className="mx-auto max-w-md"><PageHeader title="Customer demo access" subtitle="No password needed in this demo environment. Each session is isolated — you only ever see your own applications and policies." />
    <Card><CardBody className="space-y-4">
      {expired && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Your session expired. Please sign in again.</p>}
      {(from?.wrongArea || (session && isStaff)) && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">You are signed in as operations staff. Sign out of the console to use the customer portal as a customer.</p>}
      <Field label="Your name (optional)"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Demo Customer" onKeyDown={(e) => e.key === 'Enter' && go()} /></Field>
      <Button className="w-full" loading={busy} onClick={go} data-testid="customer-login">Continue as demo customer</Button>
      <p className="text-xs text-slate-500">This creates a signed demo session in this browser tab. It is <b>not production authentication</b>. Looking for the underwriter view? <Link to="/ops/login" className="text-brand-600 underline">Operations console</Link></p></CardBody></Card></div>
}

export function ProductsPage() {
  const q = useProducts()
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  return <div className="space-y-10"><PageHeader title="Choose your cover" subtitle={q.data!.demo_notice} />
    <div className="grid gap-5 lg:grid-cols-3">{q.data!.products.map((p) => <ProductCard key={p.product_key} p={p} />)}</div>
    <ScenarioPanel /></div>
}
function ProductCard({ p }: { p: ProductInfo }) {
  const I = ICON[p.product_key]; const e = p.eligibility
  return <Card className="flex flex-col p-6" data-testid={`product-${p.product_key}`}><I className="mb-3 h-8 w-8 text-brand-600" /><h3 className="text-lg font-semibold">{p.name}</h3>
    <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Coverage options</div>
    <ul className="mt-1 space-y-1 text-sm">{p.coverage_options.map((c) => <li key={c.code} className="flex justify-between"><span>{c.name}</span><span className="text-slate-500">{money(c.min_limit, 0)} – {money(c.max_limit, 0)}</span></li>)}</ul>
    <div className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Eligibility</div>
    <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-600"><li>Applicant age {e.applicant_age[0]}–{e.applicant_age[1]}</li><li>Insured value {money(e.insured_value[0], 0)} – {money(e.insured_value[1], 0)}</li>
      {e.max_asset_age !== null && <li>Asset age up to {e.max_asset_age} years</li>}<li>Coverage cannot exceed declared value</li>
      {Object.entries(e.allowed_values).filter(([, v]) => v.length <= 6 && !v.includes('NONE')).slice(0, 2).map(([k, v]) => <li key={k}>{k.replace(/_/g, ' ')}: {v.map((x) => x.toLowerCase()).join(', ')}</li>)}</ul>
    <p className="mt-3 text-xs text-slate-500">Quotes up to {money(p.auto_approval_limit, 0)} with low risk can be approved instantly.</p>
    <Link to={`/apply/${p.product_key}`} className="mt-auto pt-5"><Button className="w-full">Get a {p.name.split(' ')[0].toLowerCase()} quote<ArrowRight className="h-4 w-4" /></Button></Link></Card>
}
