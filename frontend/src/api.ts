// Typed client for the FastAPI backend (backend/main.py).

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type BoardStatus = 'open' | 'resolved' | 'awaiting_approval' | 'blocked' | 'needs_human'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: BoardStatus
  notes: string | null
  created_at: string
  state: 'open' | 'resolved'
  running: boolean
}

export interface Finding {
  fact: string
  source_tool: string
  source_ids: string[]
}

export interface PaymentRecommendation {
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  payee: string
  amount: number
  pay_order: number
  reason: string
  approval_id: number | null
}

export interface BossDecision {
  ticket_id: number
  classification: string
  priority: string
  status: BoardStatus
  summary: string
  findings: Finding[]
  payment_recommendations: PaymentRecommendation[]
  cash_priority_note: string | null
  customer_draft_id: number | null
  next_steps: string[]
  escalation_reason: string | null
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'running' | 'finished' | 'failed'
  started_at: string
  finished_at: string | null
  decision: BossDecision | null
  error: string | null
  tool_calls_used?: number
  delegations_used?: number
}

export interface DeskEvent {
  cursor: number
  ts: string
  run_id: string | null
  ticket_id: number | null
  agent: string
  depth: number | null
  kind: string
  name: string
  said: string | null
  tools: string[]
  args: unknown
}

export interface Approval {
  id: number
  ticket_id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  payee: string
  amount: number
  account: string
  reason: string
  requested_by: string
  status: string
  decided_by: string | null
  decided_at: string | null
  created_at: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  date_today: string
  total_obligations: number
  can_cover_all: boolean
  shortfall: number
}

export interface Draft {
  id: number
  ticket_id: number
  author: string
  kind: string
  title: string
  body: string
  status: string
  created_at: string
}

export type DecisionKind = 'offer_discount' | 'decline_discount' | 'wait_for_customer'

export interface HumanDecision {
  id: number
  ticket_id: number
  decision: DecisionKind
  discount_pct: number | null
  unit_price: number | null
  qty: number | null
  note: string | null
  decided_by: string
  created_at: string
}

export interface Board {
  found: boolean
  ticket: Ticket
  drafts: Draft[]
  approvals: Approval[]
  human_decisions: HumanDecision[]
}

export interface DiscountOption {
  discount_pct: number
  unit_price: number
  unit_profit: number
  revenue: number
  discount_given: number
  total_cost: number
  profit: number
  margin_pct: number | null
  profit_given_up: number
  below_cost: boolean
}

export interface DiscountOptions {
  found: boolean
  ticket_id: number
  sku: string
  name: string | null
  size: string | null
  qty: number
  qty_on_hand: number | null
  unit_cost: number
  list_price: number
  revenue_at_list: number
  profit_at_list: number
  break_even_discount_pct: number
  options: DiscountOption[]
}

export interface AgentSummary {
  agent: string
  summaries: string[]
  tools: Record<string, number>
  delegated_to: string[]
  tasks: string[]
}

export interface TicketSummary {
  ticket_id: number
  run_id: string | null
  started_at?: string
  finished_at?: string | null
  budget?: Record<string, number>
  agents: AgentSummary[]
  decision: BossDecision | null
}

export interface Payment {
  paid: boolean
  approval_id: number
  payment_id: number
  kind: string
  payee: string
  amount: number
  approved_by: string
  paid_at: string
  tables_updated: Record<string, string>
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, `Can't reach the desk API at ${API_URL}.`)
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      const detail = body?.detail
      message = typeof detail === 'string' ? detail : detail?.error ?? JSON.stringify(detail)
    } catch {
      /* keep the status text */
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

export const api = {
  tickets: () => request<{ date_today: string; tickets: Ticket[] }>('/tickets'),
  board: (id: number) => request<Board>(`/tickets/${id}`),
  summary: (id: number) => request<TicketSummary>(`/tickets/${id}/summary`),
  runTicket: (id: number) => request<Run>(`/tickets/${id}/run`, { method: 'POST' }),
  runs: () => request<{ active_run: string | null; runs: Run[] }>('/runs'),
  run: (runId: string) => request<Run>(`/runs/${runId}`),
  events: (params: { ticket_id?: number; run_id?: string; after?: number | null; limit?: number }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) q.set(k, String(v))
    })
    return request<{ events: DeskEvent[]; next_after: number | null; total_in_trail: number }>(
      `/events?${q}`,
    )
  },
  approvals: () => request<{ approvals: Approval[] }>('/approvals?status=pending'),
  approve: (id: number, approver: string) =>
    request<{ approval: Approval; payment: Payment; cash: Cash }>(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approver }),
    }),
  reject: (id: number, approver: string) =>
    request<{ decided: boolean }>(`/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ approver }),
    }),
  discountOptions: (id: number) => request<DiscountOptions>(`/tickets/${id}/discount-options`),
  decide: (
    id: number,
    body: { decided_by: string; decision: DecisionKind; discount_pct?: number | null; note?: string },
  ) =>
    request<{ recorded: boolean; decision: HumanDecision; summary: string }>(`/tickets/${id}/decision`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  cash: () => request<Cash>('/cash'),
  reset: () => request<{ reset: boolean }>('/reset', { method: 'POST' }),
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
