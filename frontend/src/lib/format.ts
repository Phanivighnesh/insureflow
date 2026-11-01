export const money = (n: number | null | undefined, digits = 2) =>
  n === null || n === undefined ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n)
export const num = (n: number | null | undefined) => (n === null || n === undefined ? '—' : new Intl.NumberFormat('en-US').format(n))
export const pct = (n: number | null | undefined) => (n === null || n === undefined ? 'n/a' : `${(n * 100).toFixed(1)}%`)
export function date(s: string | null | undefined) {
  if (!s) return '—'
  const d = new Date(s.length === 10 ? `${s}T00:00:00` : s)
  return isNaN(d.getTime()) ? s : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
export function dateTime(s: string | null | undefined) {
  if (!s) return '—'
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
export const title = (s: string | null | undefined) => (s ?? '—').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
export const PRODUCT_LABEL: Record<string, string> = { MOTOR: 'Motor Insurance', PROPERTY: 'Property Insurance', COMMERCIAL: 'Commercial Insurance' }
export const productLabel = (k: string | null | undefined) => PRODUCT_LABEL[k ?? ''] ?? title(k)
export const uuid = () => (globalThis.crypto?.randomUUID?.() ?? `k-${Date.now()}-${Math.random().toString(16).slice(2)}`).slice(0, 36)
