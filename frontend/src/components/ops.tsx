import { useEffect, useState, type ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Search } from 'lucide-react'
import { Card, CardBody, CardHeader, EmptyState, Input } from './ui'

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
const toRows = (o: Record<string, number>) => Object.entries(o).map(([name, value]) => ({ name: name.replace(/_/g, ' '), value }))

export function BarCard({ title, data, horizontal, height = 240 }: { title: string; data: Record<string, number> | { name: string; value: number }[]; horizontal?: boolean; height?: number }) {
  const rows = Array.isArray(data) ? data : toRows(data)
  return <Card><CardHeader title={title} /><CardBody>{rows.length === 0 ? <EmptyState text="No data" /> : <div style={{ height }}><ResponsiveContainer>
    <BarChart data={rows} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ left: horizontal ? 60 : 0 }}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
      {horizontal ? <><XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} /></> : <><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /></>}
      <Tooltip /><Bar dataKey="value" radius={3}>{rows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart></ResponsiveContainer></div>}</CardBody></Card>
}
export function PieCard({ title, data }: { title: string; data: Record<string, number> }) {
  const rows = toRows(data)
  return <Card><CardHeader title={title} /><CardBody>{rows.length === 0 ? <EmptyState text="No data" /> : <div className="h-60"><ResponsiveContainer><PieChart>
    <Pie data={rows} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} label={(d) => d.value}>{rows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer></div>}</CardBody></Card>
}
export function LineCard({ title, data }: { title: string; data: { month: string; count: number }[] }) {
  return <Card><CardHeader title={title} /><CardBody>{data.length === 0 ? <EmptyState text="No data" /> : <div className="h-60"><ResponsiveContainer><LineChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="month" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip />
    <Line type="monotone" dataKey="count" stroke="#2a54d8" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>}</CardBody></Card>
}
