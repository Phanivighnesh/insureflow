import type * as T from './types'

const BASE: string = ((import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_API_BASE ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: string[] = []) { super(message) }
  get isValidation() { return this.status === 422 }
}

export interface HttpOptions { getToken: () => string | null; onUnauthorized?: () => void; baseUrl?: string }

const qs = (q?: T.Query) => {
  const p = new URLSearchParams()
  Object.entries(q ?? {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)) })
  const s = p.toString()
  return s ? `?${s}` : ''
}

/** Centralised HTTP layer: bearer token, JSON, uniform error envelope -> ApiError, 401 hook. */
export function makeApi(opt: HttpOptions) {
  const base = (opt.baseUrl ?? BASE).replace(/\/$/, '')
  async function raw(method: string, path: string, body?: unknown, query?: T.Query): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json' }
    const token = opt.getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    let res: Response
    try {
      res = await fetch(`${base}/api${path}${qs(query)}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
    } catch {
      throw new ApiError(0, 'NETWORK', 'Cannot reach the InsureFlow API. Is the backend running?')
    }
    if (!res.ok) {
      let code = 'HTTP_ERROR', message = `Request failed (${res.status})`, details: string[] = []
      try { const j = await res.json(); if (j?.error) { code = j.error.code; message = j.error.message; details = j.error.details ?? [] } } catch { /* non-JSON */ }
      if (res.status === 401 && token) opt.onUnauthorized?.()
      throw new ApiError(res.status, code, message, details)
    }
    return res
  }
  const req = async <R>(method: string, path: string, body?: unknown, query?: T.Query) => (await raw(method, path, body, query)).json() as Promise<R>
  const get = <R>(path: string, query?: T.Query) => req<R>('GET', path, undefined, query)
  const post = <R>(path: string, body: unknown = {}, query?: T.Query) => req<R>('POST', path, body, query)
  type P<R> = Promise<T.Page<R>>
  type EndorseBody = { endorsement_type: string; effective_date: string; new_coverage_amount?: number; new_declared_value?: number; changes?: Record<string, unknown> }

  return {
    auth: {
      demoSession: (b: { role: T.Role; display_name?: string; access_code?: string }) => post<T.Session & { notice: string }>('/auth/demo-session', b),
      me: () => get<{ user_id: string; role: T.Role; customer_key: string | null }>('/auth/me'),
    },
    health: () => get<{ status: string; ai_provider: string; demo_environment: boolean }>('/health'),
    customer: {
      products: () => get<T.ProductsResponse>('/customer/products'),
      scenarios: () => get<{ scenarios: T.Scenario[] }>('/customer/demo-scenarios'),
      submitQuote: (b: T.QuoteRequest) => post<T.QuoteDetail>('/customer/quotes', b),
      quotes: (q?: T.Query): P<T.QuoteSummary> => get('/customer/quotes', q),
      quote: (id: string) => get<T.QuoteDetail>(`/customer/quotes/${id}`),
      provideInfo: (id: string, b: { attributes?: Record<string, unknown>; declared_value?: number; location?: string }) => post<T.QuoteDetail>(`/customer/quotes/${id}/information`, b),
      accept: (id: string) => post<{ acceptance_id: string; accepted_at: string; quote: T.QuoteDetail }>(`/customer/quotes/${id}/accept`),
      pay: (id: string, b: { outcome: T.Payment['status']; idempotency_key?: string }) =>
        post<{ demo_payment: boolean; duplicate_request: boolean; payment: T.Payment; policy: T.PolicySummary | null; quote: T.QuoteDetail }>(`/customer/quotes/${id}/payment`, b),
      resolvePayment: (pid: string, outcome: 'SUCCESS' | 'FAILED') => post<{ payment: T.Payment; policy: T.PolicySummary | null }>(`/customer/payments/${pid}/resolve`, { outcome }),
      policies: (q?: T.Query): P<T.PolicySummary> => get('/customer/policies', q),
      policy: (id: string) => get<T.PolicyDetail>(`/customer/policies/${id}`),
      cancelPolicy: (id: string, reason: string) => post<T.PolicyDetail>(`/customer/policies/${id}/cancel`, { reason }),
      requestEndorsement: (id: string, b: EndorseBody) => post<T.Endorsement>(`/customer/policies/${id}/endorsements`, b),
      requestRenewal: (id: string) => post<T.Renewal>(`/customer/policies/${id}/renewals`),
      renewals: (q?: T.Query): P<T.Renewal> => get('/customer/renewals', q),
      acceptRenewal: (id: string, payment_outcome: T.Payment['status']) =>
        post<{ demo_payment: boolean; renewal: T.Renewal; new_policy: T.PolicySummary | null }>(`/customer/renewals/${id}/accept`, { payment_outcome }),
      declineRenewal: (id: string, reason?: string) => post<{ renewal: T.Renewal }>(`/customer/renewals/${id}/decline`, { reason: reason || null }),
    },
    ops: {
      summary: () => get<T.Summary>('/dashboard/summary'),
      uwDashboard: () => get<T.UwDashboard>('/dashboard/underwriting'),
      renewalDashboard: () => get<{ outcomes: Record<string, number> }>('/dashboard/renewals'),
      exceptionDashboard: () => get<T.ExcDashboard>('/dashboard/exceptions'),
      applicants: (q?: T.Query): P<T.ApplicantRow> => get('/applicants', q),
      applicant: (id: string) => get<T.ApplicantDetail>(`/applicants/${id}`),
      assets: (q?: T.Query): P<T.AssetRow> => get('/assets', q),
      asset: (id: string) => get<T.AssetDetail>(`/assets/${id}`),
      quotes: (q?: T.Query): P<T.QuoteSummary> => get('/quotes', q),
      quote: (id: string) => get<T.QuoteDetail>(`/quotes/${id}`),
      quoteAudit: (id: string) => get<{ quote_id: string; events: T.AuditEvent[] }>(`/quotes/${id}/audit`),
      reevaluate: (id: string) => post<T.QuoteDetail>(`/quotes/${id}/evaluate`),
      audit: (q?: T.Query): P<T.AuditEvent> => get('/audit', q),
      pending: (q?: T.Query): P<T.QuoteSummary> => get('/underwriting/pending', q),
      decisions: (q?: T.Query): P<T.Decision> => get('/underwriting/decisions', q),
      review: (decisionId: string, action: 'approve' | 'reject' | 'request-information', notes?: string) =>
        post<{ decision: T.Decision; quote: T.QuoteDetail }>(`/underwriting/${decisionId}/${action}`, { notes: notes || null }),
      policies: (q?: T.Query): P<T.PolicySummary> => get('/policies', q),
      policy: (id: string) => get<T.PolicyDetail>(`/policies/${id}`),
      cancelPolicy: (id: string, reason: string) => post<T.PolicyDetail>(`/policies/${id}/cancel`, { reason }),
      endorsements: (q?: T.Query): P<T.Endorsement> => get('/endorsements', q),
      createEndorsement: (policy_id: string, b: EndorseBody) => post<T.Endorsement>('/endorsements', b, { policy_id }),
      decideEndorsement: (id: string, approve: boolean, reason?: string) => post<T.Endorsement>(`/endorsements/${id}/${approve ? 'approve' : 'reject'}`, { reason: reason || null }),
      renewals: (q?: T.Query): P<T.Renewal> => get('/renewals', q),
      generateRenewal: (policy_id: string, as_of_date?: string) => post<T.Renewal>('/renewals/generate', as_of_date ? { policy_id, as_of_date } : { policy_id }),
      acceptRenewal: (id: string, payment_outcome: T.Payment['status'] = 'SUCCESS') => post<{ renewal: T.Renewal; new_policy: T.PolicySummary | null }>(`/renewals/${id}/accept`, { payment_outcome }),
      declineRenewal: (id: string, reason?: string) => post<{ renewal: T.Renewal }>(`/renewals/${id}/decline`, { reason: reason || null }),
      exceptions: (q?: T.Query): P<T.ExceptionRow> => get('/exceptions', q),
      resolveException: (id: string, resolution_status: T.ExceptionRow['resolution_status'], note?: string) =>
        post<T.ExceptionRow>(`/exceptions/${id}/resolution`, { resolution_status, note: note || null }),
      dataStatus: () => get<T.DataStatus>('/data/status'),
      generate: (b: { seed: number; scale: 'starter' | 'full'; anomalies: boolean; confirm: boolean; background: boolean }) => post<{ run_id: string; status: string; message: string }>('/data/generate', b),
      runValidation: () => post<T.ValidationRun>('/validation/run'),
      latestValidation: () => get<T.ValidationRun>('/data/validation'),
      reproReport: () => get<T.ReproReport>('/data/reproducibility'),
      runRepro: (b: { seed: number; scale: 'starter' | 'full'; anomalies: boolean }) => post<unknown>('/data/reproducibility-check', { ...b, confirm: false, background: true }),
      exportList: () => get<T.ExportInfo>('/data/export'),
      exportDownload: async (kind: string, name: string) => (await raw('GET', `/data/export/${kind}/${name}`)).blob(),
      ai: {
        chat: (b: T.ChatRequest) => post<T.ChatResponse>('/ai/chat', b),
        explainDecision: (quote_id: string) => post<T.ChatResponse>('/ai/explain-decision', { quote_id }),
        explainException: (exception_id: string) => post<T.ChatResponse>('/ai/explain-exception', { exception_id }),
        status: () => get<T.AiStatus>('/ai/status'),
      },
    },
  }
}
export type Api = ReturnType<typeof makeApi>
