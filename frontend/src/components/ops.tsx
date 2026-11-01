import { useEffect, useState, type ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Search } from 'lucide-react'
import { Card, CardBody, CardHeader, EmptyState, Input } from './ui'
import { num, title } from '../lib/format'

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}
export function SearchBox({ value, onChange, placeholder = 'Search…' }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <div className="relative"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input aria-label="Search" className="pl-9" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} /></div>
}
export const FilterBar = ({ children }: { children: ReactNode }) => <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 p-4 [&>*]:min-w-[11rem]">{children}</div>

export const COLORS = ['#2a54d8', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#64748b', '#ec4899']

export function formatCategoryLabel(label: string): string {
  if (!label) return ''
  // Preserve pre-formatted numeric / range labels like "<500", "500-999", "1,000-2,499"
  if (/^<?\d/.test(label)) return label
  return title(label)
}

export function formatMonthLabel(m: string): string {
  if (!m || m.toLowerCase() === 'unknown') return 'Unknown'
  const parts = m.split('-')
  if (parts.length === 2) {
    const year = parts[0]
    const monthNum = parseInt(parts[1], 10)
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    if (monthNum >= 1 && monthNum <= 12) {
      return `${monthNames[monthNum - 1]} '${year.slice(2)}`
    }
  }
  return m
}

export function formatMonthFull(m: string): string {
  if (!m || m.toLowerCase() === 'unknown') return 'Unknown Date'
  const parts = m.split('-')
  if (parts.length === 2) {
    const year = parts[0]
    const monthNum = parseInt(parts[1], 10)
    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ]
    if (monthNum >= 1 && monthNum <= 12) {
      return `${monthNames[monthNum - 1]} ${year}`
    }
  }
  return m
}

export function useWindowWidth() {
  const [width, setWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1200)
  useEffect(() => {
    if (typeof window === 'undefined') return
    const handleResize = () => setWidth(window.innerWidth)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])
  return width
}

const toRows = (o: Record<string, number>) =>
  Object.entries(o).map(([name, value]) => ({
    name: formatCategoryLabel(name),
    rawName: name,
    value,
  }))

export function BarCard({
  title: cardTitle,
  data,
  horizontal,
  height = 260,
}: {
  title: string
  data: Record<string, number> | { name: string; value: number }[]
  horizontal?: boolean
  height?: number
}) {
  const rows = Array.isArray(data)
    ? data.map((d) => ({ ...d, name: formatCategoryLabel(d.name) }))
    : toRows(data)

  return (
    <Card>
      <CardHeader title={cardTitle} />
      <CardBody>
        {rows.length === 0 ? (
          <EmptyState text="No data" />
        ) : (
          <div style={{ height, minHeight: height, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rows}
                layout={horizontal ? 'vertical' : 'horizontal'}
                margin={
                  horizontal
                    ? { top: 10, right: 25, left: 10, bottom: 20 }
                    : { top: 10, right: 15, left: 0, bottom: 25 }
                }
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                {horizontal ? (
                  <>
                    <XAxis
                      type="number"
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      tickLine={{ stroke: '#cbd5e1' }}
                      axisLine={{ stroke: '#cbd5e1' }}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={170}
                      tick={{ fontSize: 11, fill: '#334155' }}
                      tickLine={false}
                      axisLine={{ stroke: '#cbd5e1' }}
                    />
                  </>
                ) : (
                  <>
                    <XAxis
                      dataKey="name"
                      interval={0}
                      angle={-25}
                      textAnchor="end"
                      height={55}
                      tickMargin={6}
                      tick={{ fontSize: 11, fill: '#334155', textAnchor: 'end' }}
                      tickLine={{ stroke: '#cbd5e1' }}
                      axisLine={{ stroke: '#cbd5e1' }}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      tickLine={{ stroke: '#cbd5e1' }}
                      axisLine={{ stroke: '#cbd5e1' }}
                    />
                  </>
                )}
                <Tooltip
                  formatter={(val: number) => [num(val), 'Count']}
                  labelFormatter={(lbl: string) => lbl}
                />
                <Bar dataKey="value" radius={3}>
                  {rows.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

export function PieCard({ title: cardTitle, data }: { title: string; data: Record<string, number> }) {
  const rows = toRows(data)
  return (
    <Card>
      <CardHeader title={cardTitle} />
      <CardBody>
        {rows.length === 0 ? (
          <EmptyState text="No data" />
        ) : (
          <div style={{ height: 260, minHeight: 260, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={rows}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={45}
                  outerRadius={80}
                  label={(d) => d.value}
                >
                  {rows.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(val: number) => [num(val), 'Count']} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

export function LineCard({
  title: cardTitle,
  data,
  height = 300,
}: {
  title: string
  data: { month: string; count: number }[]
  height?: number
}) {
  const windowWidth = useWindowWidth()
  const rows = data.map((d) => ({
    ...d,
    formattedMonth: formatMonthLabel(d.month),
    fullMonth: formatMonthFull(d.month),
  }))

  // Responsive tick interval for dates:
  // - On desktop (width >= 1024): show all months if <= 24, else every 2nd
  // - On tablet (640 <= width < 1024): show every 2nd month
  // - On mobile (width < 640): show every 3rd month (quarterly)
  const interval =
    rows.length <= 8
      ? 0
      : windowWidth < 640
        ? 2
        : windowWidth < 1024
          ? 1
          : rows.length > 24
            ? 1
            : 0

  return (
    <Card>
      <CardHeader title={cardTitle} />
      <CardBody>
        {rows.length === 0 ? (
          <EmptyState text="No data" />
        ) : (
          <div style={{ height, minHeight: height, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={rows}
                margin={{ top: 10, right: 25, left: 0, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="formattedMonth"
                  interval={interval}
                  angle={-40}
                  textAnchor="end"
                  height={50}
                  tickMargin={6}
                  tick={{ fontSize: 10, fill: '#475569', textAnchor: 'end' }}
                  tickLine={{ stroke: '#cbd5e1' }}
                  axisLine={{ stroke: '#cbd5e1' }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickLine={{ stroke: '#cbd5e1' }}
                  axisLine={{ stroke: '#cbd5e1' }}
                />
                <Tooltip
                  formatter={(val: number) => [num(val), 'Exceptions']}
                  labelFormatter={(_label: string, payload) => {
                    const item = payload?.[0]?.payload
                    return item?.fullMonth ?? _label
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#2a54d8"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#2a54d8' }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  )
}
