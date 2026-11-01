import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type ReactNode, type InputHTMLAttributes, type SelectHTMLAttributes } from 'react'
import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Info, Loader2, X, Inbox } from 'lucide-react'
import { ApiError } from '../api/client'
import { title } from '../lib/format'

export const cn = clsx

export function Button({ variant = 'primary', size = 'md', loading, className, children, disabled, ...p }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success'; size?: 'sm' | 'md'; loading?: boolean }) {
  const v = { primary: 'bg-brand-600 text-white hover:bg-brand-700', secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50',
    danger: 'bg-red-600 text-white hover:bg-red-700', ghost: 'text-slate-600 hover:bg-slate-100', success: 'bg-emerald-600 text-white hover:bg-emerald-700' }[variant]
  return <button {...p} disabled={disabled || loading} className={cn('inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-brand-500/40',
    size === 'sm' ? 'px-3 py-1.5 text-sm' : 'px-4 py-2 text-sm', v, className)}>{loading && <Loader2 className="h-4 w-4 animate-spin" />}{children}</button>
}
export const Card = ({ children, className, ...p }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) =>
  <div {...p} className={cn('rounded-xl border border-slate-200 bg-white shadow-card', className)}>{children}</div>
export const CardHeader = ({ title: t, subtitle, action }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode }) =>
  <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4"><div><h3 className="font-semibold text-slate-900">{t}</h3>{subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}</div>{action}</div>
export const CardBody = ({ children, className }: { children: ReactNode; className?: string }) => <div className={cn('p-5', className)}>{children}</div>

const TONES: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20', amber: 'bg-amber-50 text-amber-800 ring-amber-600/20', red: 'bg-red-50 text-red-700 ring-red-600/20',
  blue: 'bg-blue-50 text-blue-700 ring-blue-600/20', slate: 'bg-slate-100 text-slate-700 ring-slate-500/20', purple: 'bg-violet-50 text-violet-700 ring-violet-600/20',
}
const STATUS_TONE: Record<string, string> = {
  APPROVED: 'green', ACTIVE: 'green', SUCCESS: 'green', ACCEPTED: 'green', ELIGIBLE: 'green', LOW: 'green', RESOLVED: 'green', POLICY_ISSUED: 'green', COMPLETED: 'green', LOW_RISK: 'green',
  REFERRED: 'amber', PENDING: 'amber', PENDING_INFORMATION: 'amber', MEDIUM: 'amber', OFFERED: 'amber', ACKNOWLEDGED: 'amber', NEEDS_INFORMATION: 'amber', RUNNING: 'blue', OPEN: 'red',
  DECLINED: 'red', REJECTED: 'red', FAILED: 'red', CANCELLED: 'red', INELIGIBLE: 'red', HIGH: 'red', CRITICAL: 'red',
  EXPIRED: 'slate', RENEWED: 'blue', GENERATED: 'blue',
}
export const Badge = ({ children, tone = 'slate', className }: { children: ReactNode; tone?: string; className?: string }) =>
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap', TONES[tone] ?? TONES.slate, className)}>{children}</span>
export const StatusBadge = ({ status }: { status: string | null | undefined }) => status ? <Badge tone={STATUS_TONE[status] ?? 'slate'}>{title(status)}</Badge> : <span className="text-slate-400">—</span>

export const Spinner = ({ label = 'Loading…' }: { label?: string }) => <div role="status" className="flex items-center justify-center gap-2 py-12 text-slate-500"><Loader2 className="h-5 w-5 animate-spin" />{label}</div>
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error as ApiError
  return <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
    <div className="flex items-center gap-2 font-medium"><AlertTriangle className="h-4 w-4" />{e?.status === 403 ? 'Not permitted' : e?.status === 404 ? 'Not found' : 'Something went wrong'}</div>
    <p className="mt-1">{e?.message ?? String(error)}</p>
    {e?.details?.length ? <ul className="mt-2 list-disc pl-5">{e.details.map((d, i) => <li key={i}>{d}</li>)}</ul> : null}
    {onRetry && <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>Retry</Button>}
  </div>
}
export const EmptyState = ({ text, hint, action }: { text: string; hint?: string; action?: ReactNode }) =>
  <div className="flex flex-col items-center gap-2 px-6 py-12 text-center text-slate-500"><Inbox className="h-8 w-8 text-slate-300" /><p className="font-medium text-slate-700">{text}</p>{hint && <p className="text-sm">{hint}</p>}{action}</div>
export const PageHeader = ({ title: t, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) =>
  <div className="mb-6 flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t}</h1>{subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}</div>{actions}</div>
export const Stat = ({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: string }) =>
  <Card className="p-4"><div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div><div className={cn('mt-1 text-2xl font-semibold', tone)}>{value}</div>{hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}</Card>
export const KV = ({ k, v }: { k: ReactNode; v: ReactNode }) => <div className="flex justify-between gap-4 py-1.5 text-sm"><dt className="text-slate-500">{k}</dt><dd className="text-right font-medium text-slate-900">{v}</dd></div>
export const DemoBanner = ({ text = 'DEMO ENVIRONMENT — synthetic rules and data, demo payments only. Not a real insurer.' }: { text?: string }) =>
  <div className="bg-amber-100 px-4 py-1.5 text-center text-xs font-medium text-amber-900">{text}</div>

const inputCls = 'block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-slate-50'
export const Field = ({ label, error, hint, required, children }: { label: string; error?: string; hint?: string; required?: boolean; children: ReactNode }) =>
  <label className="block text-sm"><span className="mb-1 block font-medium text-slate-700">{label}{required && <span className="text-red-500"> *</span>}</span>{children}{hint && !error && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}{error && <span className="mt-1 block text-xs text-red-600">{error}</span>}</label>
export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={cn(inputCls, p.className)} />
export const Select = ({ children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} className={cn(inputCls, p.className)}>{children}</select>
export const Textarea = (p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...p} className={cn(inputCls, p.className)} />

export function Modal({ open, onClose, title: t, children, footer }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => { if (!open) return; const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h) }, [open, onClose])
  if (!open) return null
  return <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={typeof t === 'string' ? t : 'dialog'}>
    <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
    <div className="relative max-h-[90vh] w-full max-w-lg overflow-auto rounded-xl bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><h3 className="font-semibold">{t}</h3><button aria-label="Close" onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100"><X className="h-4 w-4" /></button></div>
      <div className="p-5">{children}</div>{footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
    </div></div>
}
export function ConfirmDialog({ open, onClose, onConfirm, title: t, children, confirmLabel = 'Confirm', danger, loading }:
  { open: boolean; onClose: () => void; onConfirm: () => void; title: string; children: ReactNode; confirmLabel?: string; danger?: boolean; loading?: boolean }) {
  return <Modal open={open} onClose={onClose} title={t} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant={danger ? 'danger' : 'primary'} loading={loading} onClick={onConfirm}>{confirmLabel}</Button></>}>{children}</Modal>
}

export interface Column<T> { header: string; cell: (row: T) => ReactNode; className?: string }
export function DataTable<T>({ columns, rows, rowKey, onRowClick, empty }: { columns: Column<T>[]; rows: T[]; rowKey: (r: T) => string; onRowClick?: (r: T) => void; empty?: ReactNode }) {
  if (!rows.length) return <>{empty ?? <EmptyState text="No records found" hint="Try adjusting your search or filters." />}</>
  return <div className="overflow-x-auto"><table className="min-w-full text-sm">
    <thead><tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{columns.map((c) => <th key={c.header} className={cn('px-4 py-2.5', c.className)}>{c.header}</th>)}</tr></thead>
    <tbody className="divide-y divide-slate-100">{rows.map((r) => <tr key={rowKey(r)} onClick={onRowClick ? () => onRowClick(r) : undefined} className={cn(onRowClick && 'cursor-pointer hover:bg-slate-50')}>
      {columns.map((c) => <td key={c.header} className={cn('px-4 py-3 align-middle', c.className)}>{c.cell(r)}</td>)}</tr>)}</tbody></table></div>
}
export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-600">
    <span>{total === 0 ? 'No results' : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total.toLocaleString()}`}</span>
    <div className="flex items-center gap-2"><Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
      <span>Page {page} / {pages}</span><Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button></div></div>
}

// ---- toasts
type Toast = { id: number; kind: 'success' | 'error' | 'info'; text: string }
const ToastCtx = createContext<{ push: (kind: Toast['kind'], text: string) => void } | null>(null)
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const push = useCallback((kind: Toast['kind'], text: string) => {
    const id = Date.now() + Math.random(); setItems((i) => [...i, { id, kind, text }]); setTimeout(() => setItems((i) => i.filter((t) => t.id !== id)), 5000)
  }, [])
  return <ToastCtx.Provider value={{ push }}>{children}
    <div className="fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2" aria-live="polite">{items.map((t) =>
      <div key={t.id} role="status" className={cn('flex items-start gap-2 rounded-lg border bg-white p-3 text-sm shadow-lg', t.kind === 'error' ? 'border-red-200' : t.kind === 'success' ? 'border-emerald-200' : 'border-slate-200')}>
        {t.kind === 'error' ? <AlertTriangle className="mt-0.5 h-4 w-4 text-red-600" /> : t.kind === 'success' ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> : <Info className="mt-0.5 h-4 w-4 text-blue-600" />}
        <span>{t.text}</span></div>)}</div></ToastCtx.Provider>
}
export function useToast() {
  const c = useContext(ToastCtx); if (!c) throw new Error('ToastProvider missing')
  return { success: (t: string) => c.push('success', t), error: (e: unknown) => c.push('error', e instanceof ApiError ? (e.details.length ? `${e.message}: ${e.details.join('; ')}` : e.message) : String(e)), info: (t: string) => c.push('info', t) }
}
