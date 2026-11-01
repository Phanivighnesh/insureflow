import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, PlayCircle, ShieldAlert } from 'lucide-react'
import { api, useAuth } from '../../auth/AuthContext'
import type { ExceptionRow, ValidationRun } from '../../api/types'
import { Badge, Button, Card, CardBody, CardHeader, ConfirmDialog, DataTable, EmptyState, ErrorState, Field, Input, KV, Modal, PageHeader, Pagination, Select, Spinner, Stat, StatusBadge, Textarea, useToast } from '../../components/ui'
import { AuditTimeline, usePaging } from '../../components/domain'
import { FilterBar } from '../../components/ops'
import { date, dateTime, money, num, pct, title } from '../../lib/format'

const recordLink = (e: Pick<ExceptionRow, 'affected_entity' | 'affected_record_id'>): string | null => {
  const id = e.affected_record_id
  switch (e.affected_entity) {
    case 'Policy': return `/ops/policies/${id}`
    case 'Quote': return `/ops/quotes/${id}`
    case 'Renewal': { const m = id.match(/^REN-(POL-\d{4}-\d{6})-\d{4}$/); return m ? `/ops/policies/${m[1]}` : null }
    case 'Endorsement': { const m = id.match(/^END-(POL-\d{4}-\d{6})-\d{3}$/); return m ? `/ops/policies/${m[1]}` : null }
    default: return null
  }
}

export function Exceptions() {
  const { page, setPage, pageSize } = usePaging(1, 20); const qc = useQueryClient(); const toast = useToast()
  const [type, setType] = useState(''); const [sev, setSev] = useState(''); const [res, setRes] = useState('')
  const [open, setOpen] = useState<ExceptionRow | null>(null); const [rs, setRs] = useState<ExceptionRow['resolution_status']>('ACKNOWLEDGED'); const [note, setNote] = useState('')
  const dash = useQuery({ queryKey: ['ops', 'exc'], queryFn: () => api.ops.exceptionDashboard() })
  const r = useQuery({ queryKey: ['ops', 'exceptions', page, type, sev, res], queryFn: () => api.ops.exceptions({ page, page_size: pageSize, issue_type: type, severity: sev, resolution_status: res }), placeholderData: (p) => p })
  const save = useMutation({ mutationFn: () => api.ops.resolveException(open!.exception_id, rs, note), onSuccess: () => { toast.success('Resolution saved'); setOpen(null); setNote(''); qc.invalidateQueries({ queryKey: ['ops'] }) }, onError: (e) => toast.error(e) })
  const types = Object.keys(dash.data?.by_issue_type ?? {})
  return <div><PageHeader title="Exceptions" subtitle={dash.data?.run_id ? `Findings from validation run ${dash.data.run_id}. Detected independently of ground truth.` : 'No validation run yet — run validation from Data & validation.'} />
    <Card><FilterBar><Select aria-label="Issue type" value={type} onChange={(e) => { setType(e.target.value); setPage(1) }}><option value="">All issue types</option>{types.map((t) => <option key={t} value={t}>{title(t)} ({dash.data!.by_issue_type[t]})</option>)}</Select>
      <Select aria-label="Severity" value={sev} onChange={(e) => { setSev(e.target.value); setPage(1) }}><option value="">All severities</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></Select>
      <Select aria-label="Resolution" value={res} onChange={(e) => { setRes(e.target.value); setPage(1) }}><option value="">All resolution states</option><option>OPEN</option><option>ACKNOWLEDGED</option><option>RESOLVED</option></Select></FilterBar>
      {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><DataTable rows={r.data!.items} rowKey={(e) => e.exception_id} onRowClick={(e) => { setOpen(e); setRs(e.resolution_status === 'OPEN' ? 'ACKNOWLEDGED' : e.resolution_status); setNote(e.resolution_note ?? '') }}
        empty={<EmptyState text="No exceptions" hint="Either none were detected or no validation has run." />} columns={[
          { header: 'Issue type', cell: (e) => <b>{title(e.issue_type)}</b> }, { header: 'Affected record', cell: (e) => <span className="font-mono text-xs">{e.affected_entity} {e.affected_record_id}</span> },
          { header: 'Severity', cell: (e) => <StatusBadge status={e.severity} /> }, { header: 'Record date', cell: (e) => date(e.record_date) }, { header: 'Detected', cell: (e) => dateTime(e.detected_at) },
          { header: 'Actual outcome', cell: (e) => <span className="text-xs text-slate-600">{e.actual_outcome}</span>, className: 'max-w-xs' }, { header: 'Resolution', cell: (e) => <StatusBadge status={e.resolution_status} /> }]} />
        <Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card>
    <Modal open={!!open} onClose={() => setOpen(null)} title={open ? `${title(open.issue_type)}` : ''} footer={<><Button variant="secondary" onClick={() => setOpen(null)}>Close</Button><Button loading={save.isPending} onClick={() => save.mutate()}>Save resolution</Button></>}>
      {open && <div className="space-y-3 text-sm"><dl className="divide-y divide-slate-100"><KV k="Record" v={<span className="font-mono">{open.affected_entity} {open.affected_record_id}</span>} /><KV k="Severity" v={<StatusBadge status={open.severity} />} /><KV k="Exception" v={<span className="font-mono text-xs">{open.exception_id}</span>} /></dl>
        <div><div className="font-medium">Expected</div><p className="text-slate-600">{open.expected_outcome}</p></div><div><div className="font-medium">Actual</div><p className="text-slate-600">{open.actual_outcome}</p></div>
        <div className="flex gap-4 text-xs">
          {recordLink(open) && <Link to={recordLink(open)!} className="text-brand-600 underline">Open affected record</Link>}
          <Link to={`/ops/copilot?type=exception&id=${open.exception_id}`} className="text-brand-600 underline">Ask Copilot about this</Link>
        </div>
        <Field label="Resolution status"><Select aria-label="Resolution status" value={rs} onChange={(e) => setRs(e.target.value as ExceptionRow['resolution_status'])}><option>OPEN</option><option>ACKNOWLEDGED</option><option>RESOLVED</option></Select></Field>
        <Field label="Note" hint="Required to mark RESOLVED."><Textarea aria-label="Resolution note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        {open.resolved_by && <p className="text-xs text-slate-500">Last updated by {open.resolved_by}</p>}</div>}</Modal></div>
}

export function AuditLog() {
  const { page, setPage, pageSize } = usePaging(1, 30); const [id, setId] = useState(''); const [type, setType] = useState('')
  const r = useQuery({ queryKey: ['ops', 'audit', page, id, type], queryFn: () => api.ops.audit({ page, page_size: pageSize, entity_id: id.trim(), entity_type: type }), placeholderData: (p) => p })
  return <div><PageHeader title="Audit history" subtitle="Append-only record of every state change." /><Card><FilterBar>
    <Input aria-label="Entity ID" placeholder="Exact entity ID, e.g. QTE-2026-000001" value={id} onChange={(e) => { setId(e.target.value); setPage(1) }} />
    <Select aria-label="Entity type" value={type} onChange={(e) => { setType(e.target.value); setPage(1) }}><option value="">All entity types</option>{['Applicant', 'Quote', 'Payment', 'Policy', 'Endorsement', 'Renewal', 'Exception'].map((t) => <option key={t}>{t}</option>)}</Select></FilterBar>
    {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} onRetry={() => r.refetch()} /> : <><CardBody><AuditTimeline events={r.data!.items} /></CardBody><Pagination page={r.data!.page} pageSize={r.data!.page_size} total={r.data!.total} onPage={setPage} /></>}</Card></div>
}

function ValidationView({ v }: { v: ValidationRun }) {
  const m = v.metrics; const ev = v.evaluation
  return <div className="space-y-6" data-testid="validation-view">
    <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6"><Stat label="Records processed" value={num(m.total_records_processed)} /><Stat label="Valid" value={num(m.valid_records)} tone="text-emerald-600" /><Stat label="Invalid" value={num(m.invalid_records)} tone="text-red-600" />
      <Stat label="Exceptions" value={num(v.finding_count)} /><Stat label="Avg premium" value={money(m.average_premium)} /><Stat label="Premium recon." value={pct(m.premium_reconciliation_accuracy)} /></div>
    <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6"><Stat label="Eligibility pass" value={pct(m.eligibility_pass_rate)} /><Stat label="Approval rate" value={pct(m.approval_rate)} /><Stat label="Rejection rate" value={pct(m.rejection_rate)} />
      <Stat label="Referral rate" value={pct(m.referral_rate)} /><Stat label="Issuance compliance" value={pct(m.policy_issuance_compliance)} /><Stat label="Renewal compliance" value={pct(m.renewal_eligibility_compliance)} /></div>
    <Card><CardHeader title="Validation checks" subtitle={`Run ${v.run_id} · ${dateTime(v.finished_at)} · by ${v.triggered_by}`} /><DataTable rows={Object.entries(v.checks)} rowKey={([k]) => k} columns={[{ header: 'Check', cell: ([k]) => title(k) }, { header: 'Checked', cell: ([, c]) => num(c.checked) }, { header: 'Failed', cell: ([, c]) => c.failed ? <Badge tone="red">{c.failed}</Badge> : <Badge tone="green">0</Badge> }]} /></Card>
    {ev ? <Card><CardHeader title="Detector vs ground truth (evaluation only)" subtitle="Ground truth is never an input to the detector." />
      <CardBody><div className="mb-4 grid gap-4 sm:grid-cols-3 lg:grid-cols-6"><Stat label="Precision" value={pct(ev.precision)} /><Stat label="Recall" value={pct(ev.recall)} /><Stat label="F1" value={ev.f1 ?? 'n/a'} /><Stat label="True positives" value={ev.true_positives} /><Stat label="False positives" value={ev.false_positives} /><Stat label="False negatives" value={ev.false_negatives} /></div>
        <DataTable rows={Object.entries(ev.per_issue_type)} rowKey={([k]) => k} columns={[{ header: 'Issue type', cell: ([k]) => title(k) }, { header: 'TP', cell: ([, x]) => x.tp }, { header: 'FP', cell: ([, x]) => x.fp }, { header: 'FN', cell: ([, x]) => x.fn }, { header: 'Precision', cell: ([, x]) => pct(x.precision) }, { header: 'Recall', cell: ([, x]) => pct(x.recall) }]} />
        <p className="mt-3 text-xs text-slate-500">Edge-case labels: {Object.entries(ev.edge_case_labels).map(([k, n]) => `${title(k)} ${n}`).join(' · ') || 'none'}</p></CardBody></Card> : <Card><CardBody><EmptyState text="No ground truth loaded" hint="Metrics against ground truth appear after a dataset with labels is generated." /></CardBody></Card>}
  </div>
}

export function DataValidation() {
  const { session } = useAuth(); const qc = useQueryClient(); const toast = useToast()
  const role = session!.role; const isAdmin = role === 'ADMINISTRATOR'; const canVal = role === 'ADMINISTRATOR' || role === 'RISK_REVIEWER'
  const [scale, setScale] = useState<'starter' | 'full'>('starter'); const [seed, setSeed] = useState('20261022'); const [anom, setAnom] = useState(true); const [confirm, setConfirm] = useState(false); const [ack, setAck] = useState(false)
  const status = useQuery({ queryKey: ['ops', 'dataStatus'], queryFn: () => api.ops.dataStatus(), refetchInterval: (q) => (q.state.data?.running ? 3000 : 20000) })
  const val = useQuery({ queryKey: ['ops', 'validation'], queryFn: () => api.ops.latestValidation(), retry: false })
  const exp = useQuery({ queryKey: ['ops', 'exports'], queryFn: () => api.ops.exportList(), enabled: canVal, retry: false })
  const repro = useQuery({ queryKey: ['ops', 'repro'], queryFn: () => api.ops.reproReport(), retry: false })
  const running = status.data?.running
  useEffect(() => { if (status.data && !status.data.running) { qc.invalidateQueries({ queryKey: ['ops', 'validation'] }); qc.invalidateQueries({ queryKey: ['ops', 'exports'] }) } }, [status.data?.running, status.data?.latest_run?.run_id, qc])
  const gen = useMutation({ mutationFn: () => api.ops.generate({ seed: Number(seed), scale, anomalies: anom, confirm: true, background: true }), onSuccess: (r) => { toast.info(r.message); setConfirm(false); setAck(false); qc.invalidateQueries({ queryKey: ['ops'] }) }, onError: (e) => { toast.error(e); setConfirm(false) } })
  const run = useMutation({ mutationFn: () => api.ops.runValidation(), onSuccess: (v) => { toast.success(`Validation ${v.run_id}: ${v.finding_count} findings`); qc.setQueryData(['ops', 'validation'], v); qc.invalidateQueries({ queryKey: ['ops'] }) }, onError: (e) => toast.error(e) })
  const rep = useMutation({ mutationFn: () => api.ops.runRepro({ seed: Number(seed), scale, anomalies: anom }), onSuccess: () => { toast.info('Reproducibility check started in the background; this page refreshes the report.'); setTimeout(() => repro.refetch(), scale === 'full' ? 240000 : 15000) }, onError: (e) => toast.error(e) })
  const download = async (kind: string, name: string) => { try { const b = await api.ops.exportDownload(kind, name); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = name; a.click(); URL.revokeObjectURL(a.href) } catch (e) { toast.error(e) } }
  const lr = status.data?.latest_run
  return <div className="space-y-6"><PageHeader title="Data generation & validation" subtitle="Synthetic dataset — no real customer information. Seed-driven and reproducible." />
    <Card><CardHeader title="Current dataset" action={lr && <StatusBadge status={lr.status} />} /><CardBody>{status.isLoading ? <Spinner /> : status.error ? <ErrorState error={status.error} /> : <div className="grid gap-6 lg:grid-cols-2">
      <dl className="divide-y divide-slate-100"><KV k="Latest run" v={lr ? `${lr.run_id} · ${lr.scale} · seed ${lr.seed}` : 'none (database holds only live records)'} /><KV k="Anomaly injection" v={lr ? (lr.anomaly_injection ? 'on' : 'off') : '—'} /><KV k="Started" v={dateTime(lr?.started_at)} /><KV k="Finished" v={dateTime(lr?.finished_at)} /><KV k="By" v={lr?.triggered_by ?? '—'} />
        {lr?.error && <KV k="Error" v={<span className="text-red-600">{lr.error}</span>} />}{lr?.notes?.length ? <KV k="Notes" v={lr.notes.join('; ')} /> : null}</dl>
      <div><div className="mb-1 text-xs font-semibold uppercase text-slate-500">Live row counts</div><dl className="grid grid-cols-2 gap-x-6 text-sm">{Object.entries(status.data!.live_row_counts).filter(([, n]) => n > 0).map(([k, n]) => <KV key={k} k={title(k)} v={num(n)} />)}</dl></div></div>}</CardBody></Card>
    <div className="grid gap-6 lg:grid-cols-2">
      <Card><CardHeader title="Generate dataset" subtitle="Destructive: replaces all applicants, quotes, policies and related records." /><CardBody className="space-y-3">
        {!isAdmin && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Only the Administrator role can regenerate data.</p>}
        <div className="grid grid-cols-2 gap-3"><Field label="Scale"><Select aria-label="Scale" value={scale} disabled={!isAdmin} onChange={(e) => setScale(e.target.value as 'starter' | 'full')}><option value="starter">Starter (~150 applicants, seconds)</option><option value="full">Full (3,000 / 4,000 / 2,000 / 1,200, ~2 min)</option></Select></Field>
          <Field label="Random seed"><Input aria-label="Seed" type="number" value={seed} disabled={!isAdmin} onChange={(e) => setSeed(e.target.value)} /></Field></div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={anom} disabled={!isAdmin} onChange={(e) => setAnom(e.target.checked)} />Inject labelled anomalies (ground truth stored separately)</label>
        <div className="flex gap-2"><Button variant="danger" disabled={!isAdmin || !!running} loading={!!running} onClick={() => setConfirm(true)} data-testid="generate">{running ? 'Generating…' : 'Generate dataset'}</Button>
          <Button variant="secondary" disabled={!isAdmin} loading={rep.isPending} onClick={() => rep.mutate()}>Check reproducibility</Button></div></CardBody></Card>
      <Card><CardHeader title="Reproducibility" subtitle="Regenerated twice in isolated memory; checksums compared." /><CardBody>{repro.data ? <dl className="divide-y divide-slate-100 text-sm"><KV k="Result" v={<Badge tone={repro.data.identical ? 'green' : 'red'}>{repro.data.identical ? 'IDENTICAL' : 'MISMATCH'}</Badge>} /><KV k="Files compared" v={repro.data.files_compared} /><KV k="Runs" v={repro.data.runs} /><KV k="Seed / scale" v={`${repro.data.config.seed} / ${repro.data.config.scale}`} /><KV k="Verified" v={dateTime(repro.data.verified_at)} />
        {repro.data.mismatches.length > 0 && <KV k="Mismatches" v={repro.data.mismatches.slice(0, 3).join(', ')} />}</dl> : <EmptyState text="No reproducibility report yet" hint="Run a check (administrators)." />}</CardBody></Card></div>
    <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Validation report</h2>{canVal ? <Button loading={run.isPending} onClick={() => run.mutate()} data-testid="run-validation"><PlayCircle className="h-4 w-4" />Run validation</Button> : <span className="text-sm text-slate-500"><ShieldAlert className="mr-1 inline h-4 w-4" />Risk reviewers / administrators can run validation</span>}</div>
    {val.isLoading ? <Spinner /> : val.data ? <ValidationView v={val.data} /> : <Card><CardBody><EmptyState text="No validation run yet" hint="Run validation to detect exceptions and compute metrics." /></CardBody></Card>}
    {canVal && <Card><CardHeader title="Exports" subtitle={exp.data?.notice} />{exp.isLoading ? <Spinner /> : exp.error ? <CardBody><EmptyState text="No export available" hint="Generate a dataset first." /></CardBody> :
      <DataTable rows={exp.data!.files.filter((f) => f.kind !== 'json')} rowKey={(f) => f.name} columns={[{ header: 'File', cell: (f) => <span className="font-mono text-xs">{f.name}</span> }, { header: 'Kind', cell: (f) => <Badge tone={f.kind === 'ground_truth' ? 'red' : 'slate'}>{f.kind}</Badge> },
        { header: 'Size', cell: (f) => `${(f.size_bytes / 1024).toFixed(0)} KB` }, { header: 'SHA-256', cell: (f) => <span className="font-mono text-xs text-slate-500">{f.sha256.slice(0, 12)}…</span> },
        { header: '', cell: (f) => { const [k, ...rest] = f.name.split('/'); return <Button size="sm" variant="secondary" onClick={() => download(rest.length ? k : 'root', rest.length ? rest.join('/') : f.name)}><Download className="h-3.5 w-3.5" />Download</Button> } }]} />}</Card>}
    <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} danger title="Replace all data?" confirmLabel="Delete & regenerate" loading={gen.isPending} onConfirm={() => ack && gen.mutate()}>
      <p className="text-sm text-slate-600">This permanently deletes every existing applicant, quote, policy, endorsement, renewal and audit record — <b>including customer demo submissions</b> — and regenerates a {scale} dataset with seed {seed}.</p>
      <label className="mt-3 flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} data-testid="ack-destructive" />I understand this cannot be undone</label></ConfirmDialog></div>
}
