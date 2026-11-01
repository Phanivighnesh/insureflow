import type { QuoteRequest } from '../api/types'
const KEY = 'insureflow.prefill'
export const savePrefill = (p: QuoteRequest) => sessionStorage.setItem(KEY, JSON.stringify(p))
export const takePrefill = (product: string): QuoteRequest | null => {
  try { const s = sessionStorage.getItem(KEY); if (!s) return null; const p = JSON.parse(s) as QuoteRequest; return p.product_key === product ? p : null } catch { return null }
}
export const clearPrefill = () => sessionStorage.removeItem(KEY)
