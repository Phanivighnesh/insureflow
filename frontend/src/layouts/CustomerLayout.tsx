import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LogOut, ShieldCheck, UserCircle2 } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { Button, DemoBanner, cn } from '../components/ui'

const links = [['/products', 'Products'], ['/dashboard', 'Dashboard'], ['/my/quotes', 'My applications'], ['/my/policies', 'My policies'], ['/my/renewals', 'Renewals']] as const

export default function CustomerLayout() {
  const { session, isStaff, logout } = useAuth()
  const nav = useNavigate()
  return <div className="flex min-h-screen flex-col">
    <DemoBanner />
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <NavLink to="/" className="flex items-center gap-2 text-lg font-semibold text-brand-700"><ShieldCheck className="h-6 w-6" />InsureFlow</NavLink>
        <nav className="flex flex-1 flex-wrap items-center gap-1 text-sm" aria-label="Customer navigation">
          {links.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => cn('rounded-md px-3 py-1.5 font-medium', isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100')}>{label}</NavLink>)}
        </nav>
        {session && !isStaff ? <div className="flex items-center gap-3 text-sm"><span className="flex items-center gap-1 text-slate-600"><UserCircle2 className="h-4 w-4" />{session.display_name || session.user_id}</span>
          <Button variant="ghost" size="sm" onClick={() => { logout(); nav('/') }}><LogOut className="h-4 w-4" />Sign out</Button></div>
          : <div className="flex items-center gap-2"><NavLink to="/ops/login" className="text-sm text-slate-500 hover:text-slate-800">Operations</NavLink><Button size="sm" onClick={() => nav('/login')}>Get demo access</Button></div>}
      </div></header>
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8"><Outlet /></main>
    <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">InsureFlow demo · synthetic products & data · DEMO PAYMENT only — no real payment is processed</footer>
  </div>
}
