// Types mirror backend/app/api/serializers.py and docs/openapi.json (request bodies use extra="forbid").
export type Role = 'CUSTOMER' | 'OPERATIONS_ANALYST' | 'RISK_REVIEWER' | 'ADMINISTRATOR'
export const STAFF_ROLES: Role[] = ['OPERATIONS_ANALYST', 'RISK_REVIEWER', 'ADMINISTRATOR']

export interface Session { token: string; role: Role; user_id: string; customer_key: string | null; display_name: string | null }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export type Query = Record<string, string | number | boolean | undefined | null>

export interface FormField { name: string; label: string; type: 'select' | 'number' | 'location'; required: boolean
  options?: { value: string; label: string }[]; min?: number; max?: number }
export interface CoverageOption { coverage_id: string; code: string; name: string; min_limit: number; max_limit: number }
export interface ProductInfo {
  product_key: 'MOTOR' | 'PROPERTY' | 'COMMERCIAL'; product_id: string; name: string; coverage_options: CoverageOption[]
  eligibility: { applicant_age: [number, number]; insured_value: [number, number]; max_asset_age: number | null
    allowed_values: Record<string, string[]>; max_coverage_to_value_ratio: number }
  asset_fields: FormField[]; locations: string[]; auto_approval_limit: number
}
export interface ProductsResponse { products: ProductInfo[]; currency: string; rules_version: string; demo_notice: string }

export interface QuoteRequest {
  product_key: string; coverage_code?: string | null; requested_coverage?: number | null
  applicant: { full_name: string; email?: string | null; phone?: string | null; age?: number | null; location?: string | null; applicant_type?: 'INDIVIDUAL' | 'BUSINESS' }
  asset: { declared_value?: number | null; location?: string | null; attributes: Record<string, unknown> }
}
export interface Scenario { id: string; title: string; intent: string; payload: QuoteRequest }

export type QuoteStatus = 'APPROVED' | 'REFERRED' | 'DECLINED' | 'PENDING_INFORMATION' | 'ACCEPTED' | 'POLICY_ISSUED' | 'EXPIRED'
export interface Reason { rule_id: string; message: string }
export interface QuoteSummary {
  quote_id: string; applicant_id: string; asset_id: string; product_key: string; product_id: string
  coverage_code: string | null; requested_coverage: number | null; status: QuoteStatus
  eligibility_status: string | null; risk_score: number | null; risk_category: string | null; premium: number | null
  valid_until: string; created_at: string; applicant_name?: string; decision_outcome?: string; required_authority?: string
  decision_id?: string; referral_reasons?: Reason[]; can_act?: boolean
}
export interface EligibilityCheck { rule_id: string; name: string; passed: boolean | null; severity: string; message: string }
export interface RiskFactor { rsk_id: string; code: string; label: string; input: string; input_value: unknown; weight: number; sub_score: number; contribution: number; penalised_missing: boolean }
export interface PremiumBreakdown {
  formula_version: string; rules_version: string; currency: string; base_rate: number; coverage_rate_multiplier: number
  base_premium: number; factors: { age: number; location: number; claims: number; risk: number }
  adjusted_premium: number; charges: Record<string, number>; final_premium: number; formula: string
  inputs: Record<string, unknown>
}
export interface Decision {
  decision_id: string; quote_id: string; sequence: number; outcome: string; decision_type: string; risk_score: number | null
  reasons: Reason[]; rule_ids: string[]; approval_authority: string; decided_by: string; decided_role: string
  notes: string | null; decided_at: string; rule_engine_version: string
}
export interface Payment { payment_id: string; quote_id: string | null; policy_id: string | null; renewal_id: string | null; amount: number | null; status: 'SUCCESS' | 'FAILED' | 'PENDING'; method: string; is_demo: boolean; created_at: string }
export interface QuoteDetail extends QuoteSummary {
  applicant: { applicant_id: string; full_name: string; email: string | null; phone: string | null; age: number | null; location: string | null }
  asset: { asset_id: string; asset_type: string; declared_value: number | null; location: string | null; attributes: Record<string, unknown> }
  eligibility: { status: string; checks: EligibilityCheck[]; missing_fields: string[] } | null
  risk: { score: number; category: string; factors: RiskFactor[]; missing_info: { rsk_id: string; input: string; reason: string; mandatory: boolean }[]; explanation: string; assessed_at: string } | null
  premium_breakdown: PremiumBreakdown | null
  decision: Decision | null; decision_history: Decision[]
  acceptance: { acceptance_id: string; accepted_at: string; accepted_by: string; terms_version: string } | null
  payments: Payment[]; policy_id: string | null; next_steps: string[]; rules_version: string; demo_notice: string
}
export interface PolicySummary {
  policy_id: string; quote_id: string | null; applicant_id: string; asset_id: string; product_key: string; coverage_id: string
  coverage_amount: number; premium: number; status: string; start_date: string; expiry_date: string
  cancelled_at: string | null; renewal_of_policy_id: string | null; applicant_name?: string
}
export interface Endorsement {
  endorsement_id: string; policy_id: string; endorsement_type: string; requested_changes: Record<string, unknown>
  coverage_before: number; coverage_after: number; declared_value_before: number; declared_value_after: number
  premium_before: number; premium_after: number | null; status: 'PENDING' | 'APPROVED' | 'REJECTED'; effective_date: string
  requested_by: string; requested_at: string; decided_by: string | null; decided_at: string | null; decision_reason: string | null
}
export interface Renewal {
  renewal_id: string; policy_id: string; renewal_year: number; new_start_date: string; new_expiry_date: string
  coverage_amount: number; offered_premium: number | null; risk_score: number | null; eligibility_status: string
  reasons: string[]; status: string; new_policy_id: string | null; generated_at: string; responded_at: string | null
  response_reason: string | null; policy_expiry_date?: string
}
export interface PolicyDetail extends PolicySummary {
  coverage_name: string | null
  snapshot: { premium_breakdown?: PremiumBreakdown; risk_score?: number; risk_category?: string; product_key: string; coverage_code: string
    asset?: { declared_value: number; location: string | null; attributes: Record<string, unknown> }; [k: string]: unknown }
  issued_at: string; cancellation_reason: string | null; overlap_reason: string | null
  status_history: { from_status: string | null; to_status: string; changed_at: string; changed_by: string; reason: string | null }[]
  endorsements: Endorsement[]; renewals: Renewal[]; payments: Payment[]
  renewal_eligibility: { eligible: boolean; reasons: string[]; window_start: string; window_end: string; renewal_id: string | null }
}
export interface AuditEvent { audit_id: string; entity_type: string; entity_id: string; event_type: string; actor: string; actor_role: string; payload: Record<string, unknown> | null; occurred_at: string }
export interface ApplicantRow { applicant_id: string; full_name: string; email: string | null; applicant_type: string; location: string | null; age: number | null; status: string; quote_count: number; asset_count: number }
export interface AssetInfo { asset_id: string; asset_type: string; declared_value: number | null; location: string | null; attributes: Record<string, unknown> }
export interface ApplicantDetail { applicant_id: string; full_name: string; email: string | null; phone: string | null; age: number | null; location: string | null; applicant_type: string; status: string; created_at: string
  assets: AssetInfo[]; quotes: QuoteSummary[]; policies: PolicySummary[] }
export interface AssetRow extends AssetInfo { applicant_id: string; owner: string; policy_count: number }
export interface AssetDetail extends AssetInfo { applicant_id: string; policies: PolicySummary[]; quotes: QuoteSummary[] }
export interface ExceptionRow {
  exception_id: string; run_id: string; issue_type: string; affected_entity: string; affected_record_id: string; severity: string
  record_date: string | null; detected_at: string; expected_outcome: string; actual_outcome: string; details: Record<string, unknown> | null
  resolution_status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'; resolution_note: string | null; resolved_by: string | null
}
export interface Summary { total_applicants: number; total_quotes: number; issued_policies: number; active_policies: number; renewals: number
  pending_underwriting_reviews: number; approved_applications: number; declined_applications: number; pending_information: number
  exception_count: number; last_validation_run: string | null }
export interface UwDashboard { decision_distribution: Record<string, number>; premium_distribution: { bucket: string; count: number }[]; average_premium: number | null
  product_volume: Record<string, number>; risk_distribution: Record<string, number>; policy_lifecycle: Record<string, number> }
export interface ExcDashboard { run_id: string | null; by_issue_type: Record<string, number>; by_severity: Record<string, number>; by_resolution?: Record<string, number>; trend: { month: string; count: number }[] }
export interface DatasetRun { run_id: string; seed: number; scale: string; anomaly_injection: boolean; status: string; config: Record<string, unknown>
  row_counts: Record<string, number> | null; checksums: Record<string, string> | null; reproducibility: unknown; notes: string[] | null; error: string | null
  generator_version: string; started_at: string; finished_at: string | null; triggered_by: string }
export interface DataStatus { latest_run: DatasetRun | null; running: boolean; live_row_counts: Record<string, number> }
export interface EvalReport { ground_truth_anomalies: number; detected: number; true_positives: number; false_positives: number; false_negatives: number
  precision: number | null; recall: number | null; f1: number | null
  per_issue_type: Record<string, { tp: number; fp: number; fn: number; precision: number | null; recall: number | null }>; edge_case_labels: Record<string, number> }
export interface ValidationRun { run_id: string; triggered_by: string; started_at: string; finished_at: string
  checks: Record<string, { checked: number; failed: number }>; metrics: Record<string, any>; evaluation: EvalReport | null; finding_count: number }
export interface ExportInfo { directory: string; config: Record<string, unknown>; row_counts: Record<string, number>; files: { name: string; kind: string; sha256: string; size_bytes: number }[]; notice: string }
export interface ReproReport { identical: boolean; runs: number; files_compared: number; mismatches: string[]; config: Record<string, unknown>; verified_at: string }

export interface RecordRef { type: string; id: string; label: string; ui_route?: string | null }
export interface SupportingRule { rule_id: string; text: string }
export interface ChatResponse {
  answer_id: string
  intent: string
  summary: string
  record_references: RecordRef[]
  key_findings: string[]
  supporting_rules: SupportingRule[]
  explanation: string
  recommended_action: string
  confidence: 'high' | 'medium' | 'low'
  limitations: string[]
  provider: string
  model: string | null
  used_fallback: boolean
  fallback_reason?: string | null
  ai_available: boolean
  disclaimer: string
}
export interface AiStatus {
  configured: boolean
  provider: string
  model: string | null
  mode: 'llm' | 'fallback-templates'
  last_call?: {
    last_success_at: number | null
    last_failure_at: number | null
    last_failure_code: string | null
  } | null
}
export interface ChatRequest {
  question: string
  context_record?: { type: string; id: string }
  history?: { role: 'user' | 'assistant'; content: string }[]
}
