/**
 * End-to-end journey through the REAL backend using the SAME centralised API client the UI uses.
 * Customer submits -> ops sees the identical record -> ops reviews referral -> customer accepts ->
 * failed demo payment issues nothing -> successful demo payment issues policy -> both sides see it.
 */
import { describe, expect, it } from 'vitest'
import { makeApi, ApiError } from '../src/api/client'
import type { QuoteRequest } from '../src/api/types'

const BASE = 'http://127.0.0.1:8791'
const STAFF_CODE = 'fe-test-code'
const client = (token?: string) => makeApi({ baseUrl: BASE, getToken: () => token ?? null })
const anon = client()
const login = async (role: 'CUSTOMER' | 'OPERATIONS_ANALYST' | 'RISK_REVIEWER' | 'ADMINISTRATOR', name = 'tester') => {
  const s = await anon.auth.demoSession({ role, display_name: name, access_code: role === 'CUSTOMER' ? undefined : STAFF_CODE })
  return client(s.token)
}
const uniq = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
async function scenario(id: string, tag: string): Promise<QuoteRequest> {
  const { scenarios } = await anon.customer.scenarios()
  const p = JSON.parse(JSON.stringify(scenarios.find((s) => s.id === id)!.payload)) as QuoteRequest
  p.applicant.full_name = `${p.applicant.full_name} ${tag}`; p.applicant.email = `${tag}.${p.applicant.email}`
  return p
}
const expectStatus = async (p: Promise<unknown>, status: number) => { try { await p; throw new Error('expected failure') } catch (e) { expect(e).toBeInstanceOf(ApiError); expect((e as ApiError).status).toBe(status) } }

describe('customer -> operations -> policy journey (real backend)', () => {
  it('runs all 12 steps', async () => {
    const tag = uniq()
    // 1. customer logs in
    const cust = await login('CUSTOMER', `Cust ${tag}`)
    expect((await cust.auth.me()).role).toBe('CUSTOMER')
    // 2-4. submits applications; backend persists and returns the real underwriting outcome
    const approved = await cust.customer.submitQuote(await scenario('END_TO_END_POLICY', tag))
    const referred = await cust.customer.submitQuote(await scenario('MEDIUM_RISK_REFERRAL', tag))
    expect(approved.status).toBe('APPROVED'); expect(approved.decision!.rule_ids).toEqual(['UW-APR-001'])
    expect(approved.premium).toBe(686.75); expect(approved.premium_breakdown!.final_premium).toBe(686.75)
    expect(approved.eligibility!.checks.length).toBeGreaterThan(5); expect(approved.risk!.factors.length).toBeGreaterThan(3)
    expect(referred.status).toBe('REFERRED'); expect(referred.decision!.approval_authority).toBe('OPERATIONS_ANALYST')
    // 5-6. operations logs in separately and sees exactly the same records
    const ops = await login('OPERATIONS_ANALYST', `Ann ${tag}`)
    const found = await ops.ops.quotes({ q: tag, page_size: 50 })
    expect(found.items.map((q) => q.quote_id).sort()).toEqual([approved.quote_id, referred.quote_id].sort())
    const opsView = await ops.ops.quote(approved.quote_id)
    expect(opsView.applicant.full_name).toBe(approved.applicant.full_name)
    expect(opsView.premium_breakdown).toEqual(approved.premium_breakdown)
    expect(opsView.decision_history).toEqual(approved.decision_history)
    // 7. operations reviews the referred application
    const pending = await ops.ops.pending({ page_size: 100 })
    const row = pending.items.find((q) => q.quote_id === referred.quote_id)!
    expect(row.can_act).toBe(true); expect(row.decision_id).toBe(referred.decision!.decision_id)
    await expectStatus(cust.ops.review(row.decision_id!, 'approve'), 403)                    // customers cannot review
    const rev = await ops.ops.review(row.decision_id!, 'approve', 'Survey satisfactory')
    expect(rev.quote.status).toBe('APPROVED'); expect(rev.decision.decision_type).toBe('MANUAL')
    expect((await cust.customer.quote(referred.quote_id)).decision_history.map((d) => d.outcome)).toEqual(['REFERRED', 'APPROVED'])
    // 8. customer accepts the approved quote
    const acc = await cust.customer.accept(approved.quote_id)
    expect(acc.quote.status).toBe('ACCEPTED'); expect(acc.quote.acceptance).not.toBeNull()
    // 9. failed demo payment does not issue a policy
    const failed = await cust.customer.pay(approved.quote_id, { outcome: 'FAILED', idempotency_key: `${tag}-1` })
    expect(failed.payment.status).toBe('FAILED'); expect(failed.payment.is_demo).toBe(true); expect(failed.policy).toBeNull(); expect(failed.quote.status).toBe('ACCEPTED')
    expect((await cust.customer.policies()).items.filter((p) => p.quote_id === approved.quote_id)).toHaveLength(0)
    // 10. successful demo payment issues the policy (idempotent on retry)
    const ok = await cust.customer.pay(approved.quote_id, { outcome: 'SUCCESS', idempotency_key: `${tag}-2` })
    expect(ok.policy!.status).toBe('ACTIVE'); expect(ok.quote.status).toBe('POLICY_ISSUED'); expect(ok.payment.amount).toBe(686.75)
    const retry = await cust.customer.pay(approved.quote_id, { outcome: 'SUCCESS', idempotency_key: `${tag}-2` })
    expect(retry.duplicate_request).toBe(true); expect(retry.policy!.policy_id).toBe(ok.policy!.policy_id)
    // 11. customer sees the issued policy
    const mine = await cust.customer.policies({ page_size: 50 })
    expect(mine.items.map((p) => p.policy_id)).toContain(ok.policy!.policy_id)
    const detail = await cust.customer.policy(ok.policy!.policy_id)
    expect(detail.snapshot.premium_breakdown!.final_premium).toBe(686.75); expect(detail.status_history[0].to_status).toBe('ACTIVE')
    // 12. operations sees the very same policy
    const opsPol = await ops.ops.policy(ok.policy!.policy_id)
    expect(opsPol.quote_id).toBe(approved.quote_id); expect(opsPol.premium).toBe(detail.premium); expect(opsPol.applicant_name).toBe(approved.applicant.full_name)
    expect((await ops.ops.policies({ q: ok.policy!.policy_id })).items).toHaveLength(1)
    const audit = (await ops.ops.quoteAudit(approved.quote_id)).events.map((e) => e.event_type)
    for (const t of ['QUOTE_SUBMITTED', 'UNDERWRITING_DECISION', 'QUOTE_ACCEPTED', 'DEMO_PAYMENT_FAILED', 'DEMO_PAYMENT_SUCCESS', 'POLICY_ISSUED']) expect(audit).toContain(t)
    // the reviewed quote can proceed too
    await cust.customer.accept(referred.quote_id)
    expect((await cust.customer.pay(referred.quote_id, { outcome: 'SUCCESS' })).policy).not.toBeNull()
  })

  it('exercises all three products incl. decline, pending-information and information resubmission', async () => {
    const cust = await login('CUSTOMER'); const tag = uniq()
    const motor = await cust.customer.submitQuote(await scenario('LOW_RISK_AUTO_APPROVE', tag))
    expect(motor.status).toBe('APPROVED'); expect(motor.premium).toBe(1118)
    const declined = await cust.customer.submitQuote(await scenario('HIGH_RISK_DECLINE', tag))
    expect(declined.status).toBe('DECLINED'); expect(declined.premium).toBeNull(); expect(declined.premium_breakdown).toBeNull()      // no offer shown to customers
    expect(declined.decision!.rule_ids).toContain('UW-DEC-002')
    const pend = await cust.customer.submitQuote(await scenario('MISSING_RISK_INFO', tag))
    expect(pend.status).toBe('PENDING_INFORMATION'); expect(pend.eligibility!.missing_fields).toContain('fire_exposure'); expect(pend.premium).toBeNull()
    await expectStatus(cust.customer.accept(pend.quote_id), 409)
    const fixed = await cust.customer.provideInfo(pend.quote_id, { attributes: { fire_exposure: 'LOW' } })
    expect(fixed.eligibility!.status).toBe('ELIGIBLE'); expect(fixed.premium).not.toBeNull(); expect(fixed.decision_history.length).toBe(2)
    expect((await cust.customer.products()).products.map((p) => p.product_key)).toEqual(['MOTOR', 'PROPERTY', 'COMMERCIAL'])
  })

  it('enforces authentication, isolation and role boundaries through the client', async () => {
    const a = await login('CUSTOMER'), b = await login('CUSTOMER'); const tag = uniq()
    const q = await a.customer.submitQuote(await scenario('LOW_RISK_AUTO_APPROVE', tag))
    await expectStatus(b.customer.quote(q.quote_id), 404)                                    // other customer: not found
    await expectStatus(b.customer.accept(q.quote_id), 404)
    expect((await b.customer.quotes()).total).toBe(0)
    await expectStatus(a.ops.summary(), 403)                                                // customer cannot use ops API
    await expectStatus(anon.ops.summary(), 401)                                             // unauthenticated
    await expectStatus(client('garbage').customer.quotes(), 401)
    const analyst = await login('OPERATIONS_ANALYST')
    await expectStatus(analyst.customer.submitQuote(await scenario('LOW_RISK_AUTO_APPROVE', tag)), 403)   // staff cannot use customer API
    await expectStatus(analyst.ops.generate({ seed: 1, scale: 'starter', anomalies: true, confirm: true, background: false }), 403)
    await expectStatus(analyst.ops.runValidation(), 403)
    await expectStatus(anon.auth.demoSession({ role: 'ADMINISTRATOR', access_code: 'wrong' }), 403)
    const bad = await a.customer.submitQuote({ product_key: 'BOAT', applicant: { full_name: 'x' }, asset: { attributes: {} } }).catch((e) => e as ApiError)
    expect(bad).toBeInstanceOf(ApiError); expect((bad as ApiError).status).toBe(422); expect((bad as ApiError).isValidation).toBe(true)
    expect((await new Promise<ApiError>((res) => makeApi({ baseUrl: 'http://127.0.0.1:1', getToken: () => null }).health().catch(res))).code).toBe('NETWORK')
  })

  it('ops can generate data, validate, and export through the client', async () => {
    const admin = await login('ADMINISTRATOR'); const reviewer = await login('RISK_REVIEWER')
    await expectStatus(admin.ops.generate({ seed: 20261022, scale: 'starter', anomalies: true, confirm: false, background: false }), 422)
    const g = await admin.ops.generate({ seed: 20261022, scale: 'starter', anomalies: true, confirm: true, background: false })
    expect(g.run_id).toMatch(/^GEN-/)
    const st = await admin.ops.dataStatus()
    expect(st.latest_run!.status).toBe('COMPLETED'); expect(st.live_row_counts.applicants).toBe(150); expect(st.live_row_counts.policies).toBe(100)
    const v = await reviewer.ops.runValidation()
    expect(v.finding_count).toBe(21); expect(v.evaluation!.precision).toBe(1); expect(v.evaluation!.recall).toBe(1)
    const exc = await reviewer.ops.exceptions({ issue_type: 'POLICY_WITHOUT_ACCEPTANCE' })
    expect(exc.total).toBe(3)
    const saved = await reviewer.ops.resolveException(exc.items[0].exception_id, 'RESOLVED', 'Re-captured acceptance')
    expect(saved.resolution_status).toBe('RESOLVED')
    expect((await reviewer.ops.exportList()).files.some((f) => f.name === 'csv/quotes.csv')).toBe(true)
    expect((await (await reviewer.ops.exportDownload('csv', 'quotes.csv')).text()).startsWith('quote_id,')).toBe(true)
    expect((await reviewer.ops.summary()).total_quotes).toBe(200)
  })

  it('policy lifecycle through the client: endorsement, limit breach, ops approval, renewal, cancellation', async () => {
    const cust = await login('CUSTOMER'); const ops = await login('OPERATIONS_ANALYST'); const tag = uniq()
    const q = await cust.customer.submitQuote(await scenario('END_TO_END_POLICY', tag))
    await cust.customer.accept(q.quote_id)
    const pol = (await cust.customer.pay(q.quote_id, { outcome: 'SUCCESS' })).policy!
    const detail = await cust.customer.policy(pol.policy_id)
    expect(detail.renewal_eligibility.eligible).toBe(false)                                  // outside the window today
    // valid endorsement -> PENDING -> ops approves; original policy snapshot is preserved
    const eff = detail.start_date
    const e1 = await cust.customer.requestEndorsement(pol.policy_id, { endorsement_type: 'COVERAGE_ADJUSTMENT', new_coverage_amount: 210000, effective_date: eff })
    expect(e1.status).toBe('PENDING'); expect(e1.premium_after!).toBeGreaterThan(e1.premium_before)
    await expectStatus(cust.ops.decideEndorsement(e1.endorsement_id, true), 403)
    expect((await ops.ops.decideEndorsement(e1.endorsement_id, true, 'ok')).status).toBe('APPROVED')
    // limit breach is auto-rejected with the exception code and recorded
    const e2 = await cust.customer.requestEndorsement(pol.policy_id, { endorsement_type: 'COVERAGE_ADJUSTMENT', new_coverage_amount: 2500000, new_declared_value: 3000000, effective_date: eff })
    expect(e2.status).toBe('REJECTED'); expect(e2.decision_reason).toContain('ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT')
    const after = await cust.customer.policy(pol.policy_id)
    expect(after.endorsements.map((e) => e.status)).toEqual(['APPROVED', 'REJECTED']); expect(after.coverage_amount).toBe(200000)
    // renewal: staff may pick an as-of date inside the window; customer accepts with demo payment
    await expectStatus(cust.customer.requestRenewal(pol.policy_id), 409)
    const asOf = new Date(new Date(`${after.expiry_date}T00:00:00Z`).getTime() - 20 * 86400000).toISOString().slice(0, 10)
    const ren = await ops.ops.generateRenewal(pol.policy_id, asOf)
    expect(ren.status).toBe('OFFERED'); expect(ren.coverage_amount).toBe(210000)             // renewal uses the approved endorsement terms
    const accepted = await cust.customer.acceptRenewal(ren.renewal_id, 'SUCCESS')
    expect(accepted.new_policy!.renewal_of_policy_id).toBe(pol.policy_id); expect((await ops.ops.policy(pol.policy_id)).status).toBe('RENEWED')
    // cancelled policies cannot be renewed
    const q2 = await cust.customer.submitQuote(await scenario('END_TO_END_POLICY', `${tag}b`))
    await cust.customer.accept(q2.quote_id)
    const p2 = (await cust.customer.pay(q2.quote_id, { outcome: 'SUCCESS' })).policy!
    expect((await cust.customer.cancelPolicy(p2.policy_id, 'Sold the property')).status).toBe('CANCELLED')
    const refused = await ops.ops.generateRenewal(p2.policy_id, asOf).catch((e) => e as ApiError)
    expect((refused as ApiError).status).toBe(409); expect((refused as ApiError).details.join(' ')).toContain('RENEWAL_FOR_CANCELLED_POLICY')
  })
})
