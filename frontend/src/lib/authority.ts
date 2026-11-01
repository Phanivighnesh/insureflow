import type { Role } from '../api/types'
// UX HINT ONLY - mirrors backend ROLE_AUTHORITY / AUTHORITY_LEVELS so the UI can show whether a role is likely to be allowed.
// The backend remains the single authority and re-checks every action.
const RANK: Record<string, number> = { AUTOMATED: 0, OPERATIONS_ANALYST: 1, RISK_REVIEWER: 2, SENIOR_UNDERWRITER: 3 }
const ROLE_MAX: Record<Role, number> = { CUSTOMER: -1, OPERATIONS_ANALYST: 1, RISK_REVIEWER: 2, ADMINISTRATOR: 3 }
export const canLikelyAct = (role: Role | undefined, required: string | undefined) => !!role && required !== undefined && ROLE_MAX[role] >= (RANK[required] ?? 99)
