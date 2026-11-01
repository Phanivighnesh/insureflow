import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, useAuth } from '../../auth/AuthContext'
import type { Role } from '../../api/types'
import { Button, Card, CardBody, ErrorState, Field, Input, PageHeader, Spinner, Stat, useToast } from '../../components/ui'
import { BarCard, LineCard, PieCard } from '../../components/ops'
import { money, num, title } from '../../lib/format'

const ROLES: [Role, string, string][] = [['OPERATIONS_ANALYST', 'Operations analyst', 'Reviews referrals within analyst authority'], ['RISK_REVIEWER', 'Risk / compliance reviewer', 'Higher authority; can run validation & exports'], ['ADMINISTRATOR', 'Administrator (senior underwriting)', 'Highest authority; can regenerate data']]

export function OpsLogin() {
  const { login, expired } = useAuth(); const nav = useNavigate(); const loc = useLocation(); const toast = useToast()
  const [role, setRole] = useState<Role>('OPERATIONS_ANALYST'); const [name, setName] = useState(''); const [code, setCode] = useState(''); const [busy, setBusy] = useState(false)
  const st = loc.state as { from?: string; wrongArea?: boolean } | null
  const go = async () => { setBusy(true); try { await login(role, { name: name.trim() || title(role), code }); nav(st?.from?.startsWith('/ops') ? st.from : '/ops', { replace: true }) } catch (e) { toast.error(e) } finally { setBusy(false) } }
  return <div className="flex min-h-[80vh] items-center justify-center p-4"><div className="w-full max-w-lg"><PageHeader title="Operations console — demo sign-in" subtitle="Internal view of the same persisted records customers create." />
    <Card><CardBody className="space-y-4">
      {expired && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Your session expired. Please sign in again.</p>}
      {st?.wrongArea && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">This area is for operations staff. Customers use the customer portal.</p>}
      <fieldset><legend className="mb-2 text-sm font-medium">Role</legend><div className="space-y-2">{ROLES.map(([r, l, d]) => <label key={r} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm ${role === r ? 'border-brand-500 bg-brand-50' : 'border-slate-200'}`}>
        <input type="radio" name="role" checked={role === r} onChange={() => setRole(r)} aria-label={l} className="mt-1" /><span><b>{l}</b><br /><span className="text-slate-500">{d}</span></span></label>)}</div></fieldset>
      <Field label="Display name (optional)"><Input aria-label="Display name" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Staff access code" required hint="Demo environment: default code is insureflow-demo"><Input aria-label="Staff access code" type="password" value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && go()} /></Field>
      <Button className="w-full" loading={busy} onClick={go} data-testid="ops-login">Sign in</Button>
      <p className="text-xs text-slate-500">Demo-session authentication, not production auth. Customer? <Link className="text-brand-600 underline" to="/login">Go to the customer portal</Link></p></CardBody></Card></div></div>
}

export function Overview() {
  const s = useQuery({ queryKey: ['ops', 'summary'], queryFn: () => api.ops.summary(), refetchInterval: 15000 })
  const u = useQuery({ queryKey: ['ops', 'uw'], queryFn: () => api.ops.uwDashboard() })
  const r = useQuery({ queryKey: ['ops', 'ren'], queryFn: () => api.ops.renewalDashboard() })
  const e = useQuery({ queryKey: ['ops', 'exc'], queryFn: () => api.ops.exceptionDashboard() })
  if (s.isLoading || u.isLoading || r.isLoading || e.isLoading) return <Spinner />
  const err = s.error || u.error || r.error || e.error
  if (err) return <ErrorState error={err} onRetry={() => { s.refetch(); u.refetch(); r.refetch(); e.refetch() }} />
  const S = s.data!, U = u.data!, X = e.data!
  return <div className="space-y-6" data-testid="ops-overview"><PageHeader title="Overview" subtitle="All figures are computed by the backend from persisted records." />
    <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
      <Stat label="Applicants" value={num(S.total_applicants)} /><Stat label="Quotes" value={num(S.total_quotes)} /><Stat label="Issued policies" value={num(S.issued_policies)} />
      <Stat label="Active policies" value={num(S.active_policies)} /><Stat label="Renewals" value={num(S.renewals)} />
      <Link to="/ops/underwriting"><Stat label="Pending reviews" value={num(S.pending_underwriting_reviews)} tone="text-amber-600" hint="Referred, awaiting underwriter" /></Link>
      <Stat label="Approved" value={num(S.approved_applications)} tone="text-emerald-600" /><Stat label="Declined" value={num(S.declined_applications)} tone="text-red-600" />
      <Stat label="Pending information" value={num(S.pending_information)} /><Link to="/ops/exceptions"><Stat label="Exceptions" value={num(S.exception_count)} tone="text-red-600" hint={S.last_validation_run ? `Run ${S.last_validation_run}` : 'No validation run yet'} /></Link></div>
    <div className="grid gap-6 lg:grid-cols-3"><BarCard title="Underwriting decisions (current)" data={U.decision_distribution} /><PieCard title="Risk categories" data={U.risk_distribution} /><PieCard title="Applications by product" data={U.product_volume} /></div>
    <div className="grid gap-6 lg:grid-cols-3"><BarCard title={`Premium distribution (avg ${money(U.average_premium)})`} data={U.premium_distribution.map((b) => ({ name: b.bucket, value: b.count }))} />
      <BarCard title="Policy lifecycle" data={U.policy_lifecycle} /><BarCard title="Renewal outcomes" data={r.data!.outcomes} /></div>
    <div className="grid gap-6 lg:grid-cols-2"><BarCard title="Exceptions by type" data={X.by_issue_type} horizontal height={300} /><LineCard title="Exception trend (by record month)" data={X.trend} /></div>
    <div className="flex justify-end"><Button variant="secondary" size="sm" onClick={() => { s.refetch(); u.refetch(); r.refetch(); e.refetch() }}>Refresh</Button></div></div>
}
