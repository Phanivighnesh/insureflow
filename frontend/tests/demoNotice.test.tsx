import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '../src/auth/AuthContext'
import { ToastProvider } from '../src/components/ui'
import CustomerLayout from '../src/layouts/CustomerLayout'
import OpsLayout from '../src/layouts/OpsLayout'
import { DemoNoticeModal } from '../src/components/DemoNoticeModal'

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>
          <ToastProvider>{ui}</ToastProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DemoNoticeModal component', () => {
  it('renders custom title, body content, and button text', () => {
    const handleClose = vi.fn()
    render(
      <DemoNoticeModal
        open={true}
        onClose={handleClose}
        title="Custom Demo Title"
        buttonText="Acknowledge"
        buttonTestId="custom-dismiss-btn"
      >
        <p>Custom demo description text</p>
      </DemoNoticeModal>
    )

    expect(screen.getByText('Custom Demo Title')).toBeInTheDocument()
    expect(screen.getByText('Custom demo description text')).toBeInTheDocument()
    const btn = screen.getByTestId('custom-dismiss-btn')
    expect(btn).toHaveTextContent('Acknowledge')

    fireEvent.click(btn)
    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('does not render when open is false', () => {
    const handleClose = vi.fn()
    render(
      <DemoNoticeModal
        open={false}
        onClose={handleClose}
        title="Hidden Modal"
      >
        <p>Hidden body</p>
      </DemoNoticeModal>
    )

    expect(screen.queryByText('Hidden Modal')).not.toBeInTheDocument()
    expect(screen.queryByText('Hidden body')).not.toBeInTheDocument()
  })
})

describe('Customer Portal Demo Notice Popup', () => {
  it('displays the demo notice popup on initial load and dismisses on clicking Got it', () => {
    renderWithProviders(<CustomerLayout />)

    // Modal is initially open
    expect(screen.getByText('Welcome to the InsureFlow Demo')).toBeInTheDocument()
    expect(
      screen.getByText(/This is an interactive demonstration environment/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/Synthetic products & data:/i)).toBeInTheDocument()
    expect(screen.getByText(/Simulated payments:/i)).toBeInTheDocument()
    expect(screen.getByText(/Isolated session:/i)).toBeInTheDocument()

    // Dismiss button exists
    const dismissBtn = screen.getByTestId('dismiss-customer-demo-notice')
    expect(dismissBtn).toHaveTextContent('Got it')

    // Click dismiss
    fireEvent.click(dismissBtn)

    // Modal is now dismissed
    expect(screen.queryByText('Welcome to the InsureFlow Demo')).not.toBeInTheDocument()
  })
})

describe('Operations Portal Demo Notice Popup', () => {
  it('displays the demo environment modal on initial load and dismisses on clicking Got it', () => {
    renderWithProviders(<OpsLayout />)

    // Modal is initially open
    expect(screen.getByText('Demo Environment')).toBeInTheDocument()
    expect(
      screen.getByText(/DEMO ENVIRONMENT — operations console over synthetic data/i)
    ).toBeInTheDocument()

    const dismissBtn = screen.getByTestId('dismiss-ops-demo-notice')
    expect(dismissBtn).toHaveTextContent('Got it')

    // Click dismiss
    fireEvent.click(dismissBtn)

    // Modal is now dismissed
    expect(screen.queryByText('Demo Environment')).not.toBeInTheDocument()
  })
})
