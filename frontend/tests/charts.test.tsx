import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '../src/auth/AuthContext'
import { ToastProvider } from '../src/components/ui'
import { OpsLogin } from '../src/pages/ops/Overview'
import {
  BarCard,
  LineCard,
  PieCard,
  formatCategoryLabel,
  formatMonthLabel,
  formatMonthFull,
} from '../src/components/ops'

describe('Chart label formatting and X-axis rendering', () => {
  it('formats category labels correctly preserving ranges and title casing identifiers', () => {
    expect(formatCategoryLabel('APPROVED')).toBe('Approved')
    expect(formatCategoryLabel('DECLINED')).toBe('Declined')
    expect(formatCategoryLabel('PENDING_INFORMATION')).toBe('Pending Information')
    expect(formatCategoryLabel('REFERRED')).toBe('Referred')
    expect(formatCategoryLabel('<500')).toBe('<500')
    expect(formatCategoryLabel('500-999')).toBe('500-999')
    expect(formatCategoryLabel('1,000-2,499')).toBe('1,000-2,499')
    expect(formatCategoryLabel('10,000+')).toBe('10,000+')
    expect(formatCategoryLabel('ACTIVE')).toBe('Active')
    expect(formatCategoryLabel('AUTO_RENEWED')).toBe('Auto Renewed')
    expect(formatCategoryLabel('ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT')).toBe(
      'Endorsement Exceeds Product Limit'
    )
  })

  it('formats month labels for X-axis and full tooltips', () => {
    expect(formatMonthLabel('2025-01')).toBe("Jan '25")
    expect(formatMonthLabel('2025-12')).toBe("Dec '25")
    expect(formatMonthLabel('2026-11')).toBe("Nov '26")
    expect(formatMonthLabel('unknown')).toBe('Unknown')
    expect(formatMonthLabel('Unknown')).toBe('Unknown')

    expect(formatMonthFull('2025-01')).toBe('January 2025')
    expect(formatMonthFull('2026-11')).toBe('November 2026')
    expect(formatMonthFull('unknown')).toBe('Unknown Date')
  })

  it('renders all 4 underwriting decisions in BarCard', () => {
    const data = {
      APPROVED: 3027,
      DECLINED: 640,
      PENDING_INFORMATION: 265,
      REFERRED: 70,
    }
    const { container } = render(<BarCard title="Underwriting decisions" data={data} />)
    expect(screen.getByText('Underwriting decisions')).toBeInTheDocument()
    // Check that SVG container rendered
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })

  it('renders all 6 premium distribution buckets in BarCard', () => {
    const data = [
      { name: '<500', value: 751 },
      { name: '500-999', value: 1112 },
      { name: '1,000-2,499', value: 1200 },
      { name: '2,500-4,999', value: 418 },
      { name: '5,000-9,999', value: 124 },
      { name: '10,000+', value: 31 },
    ]
    const { container } = render(<BarCard title="Premium distribution" data={data} />)
    expect(screen.getByText('Premium distribution')).toBeInTheDocument()
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })

  it('renders horizontal BarCard with exceptions', () => {
    const data = {
      DUPLICATE_TRANSACTION: 10,
      ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT: 20,
      INVALID_DATE_SEQUENCE: 10,
    }
    const { container } = render(
      <BarCard title="Exceptions by type" data={data} horizontal height={300} />
    )
    expect(screen.getByText('Exceptions by type')).toBeInTheDocument()
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })

  it('renders LineCard with trend data without errors', () => {
    const trend = [
      { month: '2025-01', count: 6 },
      { month: '2025-02', count: 10 },
      { month: '2025-03', count: 6 },
      { month: '2025-04', count: 8 },
      { month: '2025-05', count: 3 },
      { month: '2025-06', count: 5 },
      { month: '2025-07', count: 10 },
      { month: '2025-08', count: 6 },
      { month: '2025-09', count: 7 },
      { month: '2025-10', count: 13 },
      { month: '2025-11', count: 13 },
      { month: '2025-12', count: 4 },
      { month: '2026-01', count: 3 },
      { month: '2026-02', count: 5 },
      { month: '2026-03', count: 1 },
      { month: '2026-04', count: 2 },
      { month: '2026-05', count: 3 },
      { month: '2026-06', count: 5 },
      { month: '2026-07', count: 1 },
      { month: '2026-08', count: 1 },
      { month: '2026-09', count: 1 },
      { month: '2026-10', count: 6 },
      { month: '2026-11', count: 1 },
      { month: 'unknown', count: 10 },
    ]
    const { container } = render(<LineCard title="Exception trend" data={trend} />)
    expect(screen.getByText('Exception trend')).toBeInTheDocument()
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })

  it('renders empty states cleanly when data is empty', () => {
    render(<BarCard title="Empty Bar" data={{}} />)
    expect(screen.getByText('Empty Bar')).toBeInTheDocument()
    expect(screen.getByText('No data')).toBeInTheDocument()

    render(<LineCard title="Empty Line" data={[]} />)
    expect(screen.getByText('Empty Line')).toBeInTheDocument()

    render(<PieCard title="Empty Pie" data={{}} />)
    expect(screen.getByText('Empty Pie')).toBeInTheDocument()
  })

  it('renders operations login with exact demo access code hint text without parenthetical note', () => {
    const qc = new QueryClient()

    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AuthProvider>
            <ToastProvider>
              <OpsLogin />
            </ToastProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(
      screen.getByText('Demo environment: default code is insureflow-demo')
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/set STAFF_ACCESS_CODE on the server/i)
    ).not.toBeInTheDocument()
  })
})

