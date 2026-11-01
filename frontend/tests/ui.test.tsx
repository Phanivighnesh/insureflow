/** Drives the REAL React app (jsdom) against the REAL FastAPI backend with user events. */
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '../src/App'
import { AuthProvider } from '../src/auth/AuthContext'
import { ToastProvider } from '../src/components/ui'
import { makeApi } from '../src/api/client'
import { money } from '../src/lib/format'

const BASE = 'http://127.0.0.1:8791'
const T = { timeout: 20000 }
const tag = `UI${Date.now().toString(36)}`
const shared: { quoteId?: string; policyId?: string; name?: string } = {}
const sessionToken = () => (JSON.parse(sessionStorage.getItem('insureflow.session') ?? '{}') as { token?: string }).token ?? null
const apiAs = (t: string | null) => makeApi({ baseUrl: BASE, getToken: () => t })

function renderApp(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><AuthProvider><ToastProvider><App /></ToastProvider></AuthProvider></MemoryRouter></QueryClientProvider>)
}
async function opsLogin(user: ReturnType<typeof userEvent.setup>, role?: RegExp) {
  await screen.findByRole('heading', { name: /Operations console/ }, T)
  if (role) await user.click(screen.getByRole('radio', { name: role }))
  await user.type(screen.getByLabelText('Staff access code'), 'fe-test-code')
  await user.click(screen.getByTestId('ops-login'))
  await screen.findByLabelText('Operations navigation', undefined, T)           // post-login landing = the page originally requested
}
const signOut = async (user: ReturnType<typeof userEvent.setup>) => { await user.click(await screen.findByRole('button', { name: /Sign out/ })) }

describe('customer portal UI against the real backend', () => {
  it('login -> scenario -> wizard -> result -> accept -> failed payment -> successful payment -> policy', async () => {
    const user = userEvent.setup()
    renderApp('/dashboard')                                                              // protected: no session -> login
    await screen.findByRole('heading', { name: 'Customer demo access' }, T)
    await user.type(screen.getByPlaceholderText('Demo Customer'), `Tester ${tag}`)
    await user.click(screen.getByTestId('customer-login'))
    await screen.findByTestId('customer-dashboard', undefined, T)
    expect(screen.getByText(/No applications yet/)).toBeInTheDocument()                  // new customer: real empty state

    await user.click(screen.getByRole('link', { name: 'Products' }))
    await screen.findByTestId('product-MOTOR', undefined, T); expect(screen.getByTestId('product-PROPERTY')).toBeInTheDocument(); expect(screen.getByTestId('product-COMMERCIAL')).toBeInTheDocument()
    await user.click(await screen.findByTestId('scenario-LOW_RISK_AUTO_APPROVE', undefined, T))
    await screen.findByTestId('prefill-notice', undefined, T)
    const name = screen.getByLabelText('Full name'); await user.clear(name); await user.type(name, `Asha ${tag}`); shared.name = `Asha ${tag}`
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole('button', { name: /Continue/ }))
    await user.click(screen.getByTestId('submit-application'))

    const page = await screen.findByTestId('quote-page', undefined, T)
    shared.quoteId = page.getAttribute('data-quote-id')!
    expect(screen.getByTestId('outcome-banner')).toHaveAttribute('data-status', 'APPROVED')
    const real = await apiAs(sessionToken()).customer.quote(shared.quoteId)              // what the UI shows == what the backend stored
    expect(real.status).toBe('APPROVED')
    expect(screen.getByTestId('offer-premium')).toHaveTextContent(money(real.premium))
    expect(screen.getByTestId('final-premium')).toHaveTextContent(money(real.premium_breakdown!.final_premium))
    expect(screen.getByTestId('premium-card')).toBeInTheDocument()

    await user.click(screen.getByTestId('accept-quote'))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Accept quote' }))
    await screen.findByText('DEMO PAYMENT', undefined, T)
    expect(screen.getByTestId('outcome-banner')).toHaveAttribute('data-status', 'ACCEPTED')
    expect(screen.getByText(/No real payment is processed/)).toBeInTheDocument()

    await user.selectOptions(screen.getByTestId('payment-outcome'), 'FAILED')
    await user.click(screen.getByTestId('pay-demo'))
    await screen.findByText(/Demo payment FAILED/, undefined, T)
    expect(screen.getByTestId('outcome-banner')).toHaveAttribute('data-status', 'ACCEPTED')       // still no policy
    expect((await apiAs(sessionToken()).customer.policies()).items.filter((p) => p.quote_id === shared.quoteId)).toHaveLength(0)

    await user.selectOptions(screen.getByTestId('payment-outcome'), 'SUCCESS')
    await user.click(screen.getByTestId('pay-demo'))
    await waitFor(() => expect(screen.getByTestId('outcome-banner')).toHaveAttribute('data-status', 'POLICY_ISSUED'), T)
    await user.click(await screen.findByTestId('view-policy'))
    const pv = await screen.findByTestId('policy-view', undefined, T)
    shared.policyId = pv.getAttribute('data-policy-id')!
    expect(shared.policyId).toMatch(/^POL-2026-\d{6}$/)
    expect(within(pv).getAllByText('Active').length).toBeGreaterThan(0)
    expect(within(pv).getByText(/Premium breakdown \(at issue\)/)).toBeInTheDocument()
    expect(within(pv).getByText(/Endorsement history/)).toBeInTheDocument(); expect(within(pv).getByText('Renewal eligibility')).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'My policies' }))
    await screen.findByText(shared.policyId!, undefined, T)
  })

  it('customer requests mid-term changes: a valid one is queued, an over-limit one is auto-rejected with the reason', async () => {
    const user = userEvent.setup()
    renderApp(`/policies/${shared.policyId}`)                                            // customer session persists from the previous test
    await screen.findByTestId('policy-view', undefined, T)
    const request = async (amount: string) => {
      await user.click(screen.getByTestId('request-endorsement'))
      await user.type(within(screen.getByRole('dialog')).getByLabelText('New coverage'), amount)
      await user.click(screen.getByTestId('submit-endorsement'))
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument(), T)
    }
    await request('31000')                                                               // motor policy: 30,000 -> 31,000 (<= 32,000 declared value)
    const pv = screen.getByTestId('policy-view')
    await within(pv).findByText(new RegExp(`END-${shared.policyId}-001`), undefined, T)
    expect(within(pv).getByText('Pending')).toBeInTheDocument()
    await request('210000')                                                              // exceeds the 150,000 motor product limit
    expect(await within(pv).findByText(/ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT/, undefined, T)).toBeInTheDocument()
    expect(within(pv).getByText('Rejected')).toBeInTheDocument()
    const real = await apiAs(sessionToken()).customer.policy(shared.policyId!)         // UI == backend record; original terms untouched
    expect(real.endorsements.map((e) => [e.status, e.coverage_after])).toEqual([['PENDING', 31000], ['REJECTED', 210000]])
    expect(real.coverage_amount).toBe(30000)
  })

  it('decline shows reasons and no premium; submission with a missing field yields "More information needed"', async () => {
    const user = userEvent.setup()
    renderApp('/products')
    await user.click(await screen.findByTestId('scenario-HIGH_RISK_DECLINE', undefined, T))
    await screen.findByTestId('prefill-notice', undefined, T)
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole('button', { name: /Continue/ }))
    await user.click(screen.getByTestId('submit-application'))
    await screen.findByTestId('quote-page', undefined, T)
    expect(screen.getByTestId('outcome-banner')).toHaveAttribute('data-status', 'DECLINED')
    expect(screen.queryByTestId('premium-card')).not.toBeInTheDocument(); expect(screen.queryByTestId('accept-quote')).not.toBeInTheDocument()
    expect(screen.getAllByText(/UW-DEC-002/).length).toBeGreaterThan(0)

    await user.click(screen.getByRole('link', { name: 'Products' }))
    await user.click(await screen.findByTestId('scenario-MISSING_RISK_INFO', undefined, T))
    await screen.findByTestId('prefill-notice', undefined, T)
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole('button', { name: /Continue/ }))
    expect(screen.getByRole('note')).toHaveTextContent(/Fire exposure is required/)
    await user.click(screen.getByTestId('submit-application'))
    await screen.findByTestId('quote-page', undefined, T)
    expect(screen.getByTestId('outcome-banner')).toHaveAttribute('data-status', 'PENDING_INFORMATION')
    await user.selectOptions(await screen.findByLabelText('Fire exposure'), 'LOW')
    await user.click(screen.getByTestId('submit-info'))
    await waitFor(() => expect(screen.getByTestId('outcome-banner')).not.toHaveAttribute('data-status', 'PENDING_INFORMATION'), T)
    expect(screen.getByTestId('premium-card')).toBeInTheDocument()
    await signOut(user)
  })
})

describe('operations console UI against the real backend', () => {
  it('separate ops login sees the exact customer submission and policy', async () => {
    const user = userEvent.setup()
    renderApp('/ops/quotes')
    await opsLogin(user)
    await screen.findByRole('heading', { name: 'Quote management' }, T)
    await user.type(await screen.findByLabelText('Search', undefined, T), shared.quoteId!)
    const row = await screen.findByText(shared.quoteId!, undefined, T)
    await user.click(row)
    const detail = await screen.findByTestId('ops-quote-detail', undefined, T)
    expect(detail).toHaveAttribute('data-quote-id', shared.quoteId)
    expect(within(detail).getAllByText(new RegExp(shared.name!)).length).toBeGreaterThan(0)
    expect(within(detail).getByText('Decision history')).toBeInTheDocument(); expect(within(detail).getByText('Audit trail')).toBeInTheDocument()
    await waitFor(() => expect(within(detail).getByTestId('outcome-banner')).toHaveAttribute('data-status', 'POLICY_ISSUED'), T)
    expect(within(detail).getAllByText(/Policy issued/i).length).toBeGreaterThan(0)              // banner (+ audit event once loaded)
    await user.click(screen.getByRole('button', { name: new RegExp(`View policy ${shared.policyId}`) }).closest('a')!)
    const pv = await screen.findByTestId('policy-view', undefined, T)
    expect(pv).toHaveAttribute('data-policy-id', shared.policyId)
    await user.click(within(pv).getByRole('button', { name: 'Approve' }))                 // operations approves the customer's endorsement
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve' }))
    await within(pv).findByText('Approved', undefined, T)
    await user.click(screen.getAllByRole('link', { name: 'Policies' })[0])
    await user.type(await screen.findByLabelText('Search', undefined, T), shared.policyId!)
    expect(await screen.findByText(shared.policyId!, undefined, T)).toBeInTheDocument()
  })

  it('analyst reviews a referred application from the customer portal', async () => {
    const user = userEvent.setup()
    const c = apiAs((await makeApi({ baseUrl: BASE, getToken: () => null }).auth.demoSession({ role: 'CUSTOMER' })).token)
    const sc = (await c.customer.scenarios()).scenarios.find((s) => s.id === 'MEDIUM_RISK_REFERRAL')!.payload
    sc.applicant.full_name = `Daniel ${tag}`
    const q = await c.customer.submitQuote(sc)
    expect(q.status).toBe('REFERRED')
    renderApp('/ops/underwriting')                                                        // ops session persists from the previous test
    await screen.findByRole('heading', { name: /Underwriting review queue/ }, T)
    await screen.findByText(/Required authority/, undefined, T)
    await user.click(screen.getAllByRole('link', { name: 'Quotes' })[0])
    await user.type(await screen.findByLabelText('Search', undefined, T), q.quote_id)
    await user.click(await screen.findByText(q.quote_id, undefined, T))
    const panel = await screen.findByTestId('review-panel', undefined, T)
    expect(within(panel).getByText(/Required authority: Operations Analyst/)).toBeInTheDocument()
    await user.type(within(panel).getByLabelText('Reviewer notes'), 'Looks acceptable')
    await user.click(screen.getByTestId('approve'))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(screen.getByTestId('outcome-banner')).toHaveAttribute('data-status', 'APPROVED'), T)
    expect(screen.queryByTestId('review-panel')).not.toBeInTheDocument()
    const after = await c.customer.quote(q.quote_id)                                      // customer sees the manual decision
    expect(after.status).toBe('APPROVED'); expect(after.decision_history.map((d) => d.decision_type)).toEqual(['AUTOMATED', 'MANUAL'])
  })

  it('role-gated data page and route guards', async () => {
    const user = userEvent.setup()
    renderApp('/ops/data')
    await screen.findByRole('heading', { name: 'Data generation & validation' }, T)
    expect(screen.getByText(/Only the Administrator role can regenerate data/)).toBeInTheDocument()
    expect(screen.getByTestId('generate')).toBeDisabled(); expect(screen.queryByTestId('run-validation')).not.toBeInTheDocument()   // analyst cannot validate
    await signOut(user)
    await screen.findByRole('heading', { name: /Operations console/ }, T)
    await opsLogin(user, /Administrator/)
    await user.click(screen.getAllByRole('link', { name: 'Data & validation' })[0])
    await user.click(await screen.findByTestId('run-validation', undefined, T))
    const view = await screen.findByTestId('validation-view', undefined, T)
    expect(within(view).getByText('Validation checks')).toBeInTheDocument()
    expect(screen.getByTestId('generate')).toBeEnabled()
    await user.click(screen.getByTestId('generate'))                                      // destructive action requires explicit confirmation
    expect(within(screen.getByRole('dialog')).getByText(/cannot be undone/)).toBeInTheDocument()
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    await signOut(user)
    cleanup()
    renderApp('/ops/quotes')                                                               // guard: signed out -> ops login
    await screen.findByRole('heading', { name: /Operations console/ }, T)
  })

  it('customer session cannot enter the operations area', async () => {
    const user = userEvent.setup()
    renderApp('/login')
    await user.click(await screen.findByTestId('customer-login'))
    await screen.findByTestId('customer-dashboard', undefined, T)
    cleanup()
    renderApp('/ops')
    expect(await screen.findAllByText(/This area is for operations staff/, undefined, T)).not.toHaveLength(0)
  })
})
