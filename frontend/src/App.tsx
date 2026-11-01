import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireRole } from './auth/AuthContext'
import CustomerLayout from './layouts/CustomerLayout'
import OpsLayout from './layouts/OpsLayout'
import { CustomerLogin, Landing, ProductsPage } from './pages/customer/Public'
import Apply from './pages/customer/Apply'
import QuotePage from './pages/customer/Quote'
import { Spinner } from './components/ui'

// Charts (recharts) and the operations console are code-split so first paint of the customer portal stays light.
const named = <T extends Record<string, any>>(load: () => Promise<T>, key: keyof T) => lazy(() => load().then((m) => ({ default: m[key] })))
const acct = () => import('./pages/customer/Account')
const Dashboard = named(acct, 'Dashboard'), MyQuotes = named(acct, 'MyQuotes'), MyPolicies = named(acct, 'MyPolicies'), MyRenewals = named(acct, 'MyRenewals'), CustomerPolicyDetail = named(acct, 'CustomerPolicyDetail')
const ov = () => import('./pages/ops/Overview'), rec = () => import('./pages/ops/Records'), life = () => import('./pages/ops/Lifecycle'), gov = () => import('./pages/ops/Governance'), cop = () => import('./pages/ops/Copilot')
const OpsLogin = named(ov, 'OpsLogin'), Overview = named(ov, 'Overview')
const Applicants = named(rec, 'Applicants'), ApplicantDetail = named(rec, 'ApplicantDetail'), Assets = named(rec, 'Assets'), AssetDetail = named(rec, 'AssetDetail'), Quotes = named(rec, 'Quotes'), OpsQuoteDetail = named(rec, 'OpsQuoteDetail'), Underwriting = named(rec, 'Underwriting')
const Policies = named(life, 'Policies'), OpsPolicyDetail = named(life, 'OpsPolicyDetail'), Endorsements = named(life, 'Endorsements'), Renewals = named(life, 'Renewals')
const Exceptions = named(gov, 'Exceptions'), AuditLog = named(gov, 'AuditLog'), DataValidation = named(gov, 'DataValidation'), Copilot = named(cop, 'Copilot')

const C = ({ children }: { children: React.ReactNode }) => <RequireRole area="customer">{children}</RequireRole>
const O = ({ children }: { children: React.ReactNode }) => <RequireRole area="ops">{children}</RequireRole>

export default function App() {
  return <Suspense fallback={<Spinner />}><Routes>
    <Route path="/ops/login" element={<OpsLogin />} />
    <Route path="/ops" element={<O><OpsLayout /></O>}>
      <Route index element={<Overview />} />
      <Route path="applicants" element={<Applicants />} /><Route path="applicants/:id" element={<ApplicantDetail />} />
      <Route path="assets" element={<Assets />} /><Route path="assets/:id" element={<AssetDetail />} />
      <Route path="quotes" element={<Quotes />} /><Route path="quotes/:id" element={<OpsQuoteDetail />} />
      <Route path="underwriting" element={<Underwriting />} />
      <Route path="copilot" element={<Copilot />} />
      <Route path="policies" element={<Policies />} /><Route path="policies/:id" element={<OpsPolicyDetail />} />
      <Route path="endorsements" element={<Endorsements />} /><Route path="renewals" element={<Renewals />} />
      <Route path="exceptions" element={<Exceptions />} /><Route path="audit" element={<AuditLog />} /><Route path="data" element={<DataValidation />} />
    </Route>
    <Route element={<CustomerLayout />}>
      <Route path="/" element={<Landing />} /><Route path="/login" element={<CustomerLogin />} /><Route path="/products" element={<ProductsPage />} />
      <Route path="/apply/:product" element={<C><Apply /></C>} />
      <Route path="/quotes/:id" element={<C><QuotePage /></C>} />
      <Route path="/dashboard" element={<C><Dashboard /></C>} />
      <Route path="/my/quotes" element={<C><MyQuotes /></C>} /><Route path="/my/policies" element={<C><MyPolicies /></C>} /><Route path="/my/renewals" element={<C><MyRenewals /></C>} />
      <Route path="/policies/:id" element={<C><CustomerPolicyDetail /></C>} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Suspense>
}
