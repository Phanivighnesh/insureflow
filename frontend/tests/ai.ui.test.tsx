import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import App from '../src/App'
import { AuthProvider } from '../src/auth/AuthContext'
import { ToastProvider } from '../src/components/ui'
import { STAFF_CODE } from './globalSetup'

function renderApp(initialPath = '/ops/copilot') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const T = { timeout: 15000 }

describe('AI Copilot UI', () => {
  it('redirects unauthorized users away from /ops/copilot', async () => {
    sessionStorage.clear()
    renderApp('/ops/copilot')
    const signInBtn = await screen.findByRole('button', { name: /sign in/i }, T)
    expect(signInBtn).toBeInTheDocument()
  })

  it('renders copilot page with template mode indicator for operations analyst', async () => {
    sessionStorage.clear()
    const user = userEvent.setup()
    renderApp('/ops/login')

    // Sign in as Operations Analyst
    await screen.findByRole('heading', { name: /operations console/i }, T)
    const roleRadio = screen.getByRole('radio', { name: /operations analyst/i })
    await user.click(roleRadio)
    const codeInput = screen.getByLabelText(/staff access code/i)
    await user.type(codeInput, STAFF_CODE)
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    // Navigate to AI Copilot
    const copilotLinks = await screen.findAllByRole('link', { name: /ai copilot/i }, T)
    await user.click(copilotLinks[0])

    // Verify Copilot header and indicator
    await screen.findByRole('heading', { name: /underwriting ai copilot/i }, T)
    await screen.findByText(/template mode/i, undefined, T)
    expect(screen.getByText(/suggested questions/i)).toBeInTheDocument()

    // Click suggested question
    const chip = await screen.findByRole('button', { name: /what is the auto-approval limit for property/i }, T)
    await user.click(chip)

    // Verify structured response rendered
    await screen.findByText(/business rules summary/i, undefined, T)
    expect(screen.getByText(/supporting rules/i)).toBeInTheDocument()
    expect(screen.getByText(/detailed explanation/i)).toBeInTheDocument()
  })
})
