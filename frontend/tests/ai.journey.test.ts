import { describe, expect, it } from 'vitest'
import { makeApi } from '../src/api/client'
import { PORT, STAFF_CODE } from './globalSetup'

const base = `http://127.0.0.1:${PORT}`

async function login(role: 'CUSTOMER' | 'OPERATIONS_ANALYST' | 'RISK_REVIEWER' | 'ADMINISTRATOR', key?: string) {
  let token: string | null = null
  const api = makeApi({ getToken: () => token, baseUrl: base })
  const body: any = { role, display_name: `${role}-User` }
  if (role !== 'CUSTOMER') body.access_code = STAFF_CODE
  const s = await api.auth.demoSession(body)
  token = s.token
  return api
}

describe('AI Copilot client journey (real backend in fallback mode)', () => {
  it('reports status as fallback-templates when no GROQ key', async () => {
    const ops = await login('OPERATIONS_ANALYST')
    const st = await ops.ops.ai.status()
    expect(st.configured).toBe(false)
    expect(st.provider).toBe('fallback-templates')
    expect(st.mode).toBe('fallback-templates')
  })

  it('answers questions grounded on real database records created in test', async () => {
    const cust = await login('CUSTOMER')
    const ops = await login('OPERATIONS_ANALYST')

    // Submit a property quote that gets referred (e.g. MEDIUM_RISK)
    const scenarios = await cust.customer.scenarios()
    const medRisk = scenarios.scenarios.find((s) => s.id === 'MEDIUM_RISK') || scenarios.scenarios[1]
    const quote = await cust.customer.submitQuote(medRisk.payload)
    expect(quote.status).toBe('REFERRED')

    // Ask Copilot about this referred quote
    const ans = await ops.ops.ai.chat({
      question: `Why was ${quote.quote_id} referred?`,
    })

    expect(ans.answer_id).toMatch(/^AIX-\d{6}$/)
    expect(ans.intent).toBe('explain_decision')
    expect(ans.used_fallback).toBe(true)
    expect(ans.provider).toBe('fallback-templates')
    expect(ans.summary).toContain(quote.quote_id)
    expect(ans.record_references.some((r) => r.id === quote.quote_id)).toBe(true)
    expect(ans.key_findings.length).toBeGreaterThan(0)
    expect(ans.supporting_rules.length).toBeGreaterThan(0)
  })

  it('returns graceful 200 not-found for unknown record IDs', async () => {
    const ops = await login('OPERATIONS_ANALYST')
    const ans = await ops.ops.ai.chat({
      question: 'Why was QTE-2026-999999 referred?',
    })
    expect(ans.answer_id).toBeDefined()
    expect(ans.confidence).toBe('low')
    expect(ans.summary.toLowerCase()).toContain('not found')
  })

  it('enforces customer 403 and anonymous 401 on /api/ai endpoints', async () => {
    const cust = await login('CUSTOMER')
    const anon = makeApi({ getToken: () => null, baseUrl: base })

    // Anonymous 401
    await expect(anon.ops.ai.status()).rejects.toThrow()

    // Customer 403
    await expect(cust.ops.ai.status()).rejects.toThrow()
    await expect(cust.ops.ai.chat({ question: 'Hello' })).rejects.toThrow()
  })
})

