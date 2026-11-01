import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { makeApi, type Api } from '../api/client'
import { STAFF_ROLES, type Role, type Session } from '../api/types'

const KEY = 'insureflow.session'
// sessionStorage = per-tab, so a customer and an operations user can be signed in side by side in separate tabs.
const load = (): Session | null => { try { const s = sessionStorage.getItem(KEY); return s ? (JSON.parse(s) as Session) : null } catch { return null } }
let current: Session | null = load()
let onExpire: (() => void) | null = null

/** App-wide API instance bound to the persisted demo session. */
export const api: Api = makeApi({ getToken: () => current?.token ?? null, onUnauthorized: () => onExpire?.() })

interface Ctx { session: Session | null; isStaff: boolean; login: (role: Role, opt?: { name?: string; code?: string }) => Promise<Session>; logout: () => void; expired: boolean }
const AuthCtx = createContext<Ctx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(current)
  const [expired, setExpired] = useState(false)
  const set = (s: Session | null) => { current = s; if (s) sessionStorage.setItem(KEY, JSON.stringify(s)); else sessionStorage.removeItem(KEY); setSession(s) }
  const logout = useCallback(() => { set(null); setExpired(false) }, [])
  onExpire = () => { set(null); setExpired(true) }
  const login: Ctx['login'] = useCallback(async (role, opt) => {
    const r = await api.auth.demoSession({ role, display_name: opt?.name || undefined, access_code: role === 'CUSTOMER' ? undefined : opt?.code })
    const s: Session = { token: r.token, role: r.role, user_id: r.user_id, customer_key: r.customer_key, display_name: r.display_name }
    set(s); setExpired(false)
    return s
  }, [])
  const value = useMemo(() => ({ session, isStaff: !!session && STAFF_ROLES.includes(session.role), login, logout, expired }), [session, login, logout, expired])
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}
export function useAuth() { const c = useContext(AuthCtx); if (!c) throw new Error('AuthProvider missing'); return c }

/** Route guard. Backend remains the authority; this only avoids showing screens the role cannot use. */
export function RequireRole({ area, roles, children }: { area: 'customer' | 'ops'; roles?: Role[]; children: ReactNode }) {
  const { session, isStaff } = useAuth()
  const loc = useLocation()
  if (!session) return <Navigate to={area === 'ops' ? '/ops/login' : '/login'} state={{ from: loc.pathname + loc.search }} replace />
  if (area === 'ops' && !isStaff) return <Navigate to="/ops/login" state={{ wrongArea: true }} replace />
  if (area === 'customer' && isStaff) return <Navigate to="/login" state={{ wrongArea: true }} replace />
  if (roles && !roles.includes(session.role)) return <Navigate to={area === 'ops' ? '/ops' : '/dashboard'} replace />
  return <>{children}</>
}
