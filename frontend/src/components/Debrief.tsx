import { money, type Draft, type TicketSummary } from '../api'
import { Avatar, CREW, crewFor } from '../crew'
import { OUTCOME } from './TicketBoard'

/** "Mission debrief": the boss's call and a short line on what each agent did. */
export default function Debrief({ summary, drafts }: { summary: TicketSummary | null; drafts: Draft[] }) {
  if (!summary?.run_id) return null
  const d = summary.decision
  const order = CREW.map((c) => c.key as string)
  const agents = [...summary.agents].sort((a, b) => order.indexOf(a.agent) - order.indexOf(b.agent))
  const customerDraft = drafts.filter((x) => x.kind === 'customer_message').at(-1)

  return (
    <section className="panel debrief" aria-labelledby="debrief-title">
      <div className="panel-head">
        <span className="eyebrow">Mission debrief</span>
        <h2 id="debrief-title">What the team did</h2>
        {summary.budget && (
          <p className="muted small">
            {summary.budget.tool_calls_used} of {summary.budget.tool_calls_max} tool calls ·{' '}
            {summary.budget.delegations_used} of {summary.budget.delegations_max} hand-offs
          </p>
        )}
      </div>

      {d && (
        <div className="verdict">
          <div className="verdict-head">
            <Avatar agent="boss" size={40} />
            <div>
              <b>Lord Vader's ruling</b>
              <div>
                <span className={`outcome outcome-${OUTCOME[d.status]?.tone ?? 'neutral'}`}>
                  {OUTCOME[d.status]?.label ?? d.status}
                </span>{' '}
                <span className="muted small">priority {d.priority}</span>
              </div>
            </div>
          </div>
          <p>{d.summary}</p>
          {d.payment_recommendations.length > 0 && (
            <ul className="recs">
              {d.payment_recommendations.map((p, i) => (
                <li key={i}>
                  <b>#{p.pay_order}</b> {p.kind.replace('_', ' ')} to {p.payee}: {money(p.amount)}
                  {p.approval_id && <span className="muted"> · request #{p.approval_id} (sign it on the right)</span>}
                </li>
              ))}
            </ul>
          )}
          {d.cash_priority_note && <p className="small"><b>Cash priority:</b> {d.cash_priority_note}</p>}
          {d.escalation_reason && <p className="small"><b>Why a human:</b> {d.escalation_reason}</p>}
          {d.next_steps.length > 0 && (
            <ul className="next-steps">
              {d.next_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <ul className="agent-summaries">
        {agents
          .filter((a) => a.agent !== 'boss' && crewFor(a.agent))
          .map((a) => {
            const m = crewFor(a.agent)!
            return (
              <li key={a.agent} className="agent-summary" style={{ borderColor: m.color }}>
                <div className="agent-summary-head">
                  <Avatar agent={a.agent} size={32} />
                  <b>{m.character}</b> <span className="muted small">{m.role}</span>
                </div>
                <p>{a.summaries.at(-1) ?? 'Took part without a written report.'}</p>
                <div className="chips">
                  {Object.entries(a.tools).map(([tool, n]) => (
                    <span key={tool} className="tool-chip tool-chip-light">
                      {tool}
                      {n > 1 ? ` ×${n}` : ''}
                    </span>
                  ))}
                  {a.delegated_to.map((to, i) => (
                    <span key={i} className="tool-chip tool-chip-handoff">
                      → {crewFor(to)?.character ?? to}
                    </span>
                  ))}
                </div>
              </li>
            )
          })}
      </ul>

      {customerDraft && (
        <div className="draft">
          <div className="draft-head">
            <Avatar agent="customer_service" size={26} /> <b>Customer draft</b>{' '}
            <span className="pill pill-draft">Draft · not sent</span>
          </div>
          <p className="draft-body">{customerDraft.body}</p>
        </div>
      )}
    </section>
  )
}
