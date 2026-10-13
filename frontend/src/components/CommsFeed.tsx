import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'
import type { DeskEvent } from '../api'
import { Avatar, crewFor, speakerName } from '../crew'

const OUTCOME_TEXT: Record<string, string> = {
  resolved: 'Done',
  awaiting_approval: 'Awaiting your approval',
  blocked: 'Blocked',
  needs_human: 'Needs a human',
}

function compactArgs(args: unknown): string {
  if (!args || typeof args !== 'object') return ''
  return Object.entries(args as Record<string, unknown>)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
}

/** One feed line. Returns null for events too low-level to show (raw results, prompts). */
function Line({ e }: { e: DeskEvent }) {
  const member = crewFor(e.agent)
  const who = speakerName(e.agent)
  const accent = member?.color ?? '#00356b'

  switch (e.kind) {
    case 'run_start':
      return <div className="feed-divider">Run started · {new Date(e.ts).toLocaleTimeString()}</div>
    case 'run_end':
      return <div className="feed-divider">Run finished · {new Date(e.ts).toLocaleTimeString()}</div>
    case 'agent_start':
      // The task text is already in the hand-off bubble above, so just acknowledge it.
      return e.agent === 'boss' ? (
        <Bubble agent="boss" who={who} accent={accent} label="takes the ticket">
          Opened ticket #{e.ticket_id}. Assembling the team.
        </Bubble>
      ) : (
        <div className="feed-action" style={{ '--agent': accent } as CSSProperties}>
          <span className="feed-action-who">{who}</span>
          <span>copies that and gets to work</span>
        </div>
      )
    case 'model_response':
      return e.said ? (
        <Bubble agent={e.agent} who={who} accent={accent} label="says">
          {e.said}
        </Bubble>
      ) : null
    case 'tool_call':
      return (
        <div className="feed-action" style={{ '--agent': accent } as CSSProperties}>
          <span className="feed-action-who">{who}</span>
          <span className="tool-chip">{e.name}</span>
          <span className="feed-args">{compactArgs(e.args)}</span>
        </div>
      )
    case 'delegation': {
      const to = speakerName(e.name)
      return (
        <Bubble agent={e.agent} who={who} accent={accent} label={`→ ${to}`} tone="handoff">
          {e.said?.replace(/^Delegated to [a-z_]+: /, '')}
        </Bubble>
      )
    }
    case 'report':
      return (
        <Bubble agent={e.agent} who={who} accent={accent} label="reports back">
          {e.said}
        </Bubble>
      )
    case 'agent_output':
      return e.agent === 'boss' ? (
        <Bubble agent="boss" who={who} accent={accent} label="final call" tone="verdict">
          {e.said}
        </Bubble>
      ) : null
    case 'status':
      return (
        <div className="feed-status">
          Ticket #{e.ticket_id} marked <b>{OUTCOME_TEXT[e.name] ?? e.name}</b>
        </div>
      )
    case 'human_ticket_decision':
      return (
        <Bubble agent={e.agent} who={who} accent="#00356b" label="decided" tone="human">
          {(() => {
            const a = (e.args ?? {}) as { decision?: string; discount_pct?: number | null; note?: string }
            const what =
              a.decision === 'offer_discount'
                ? `Offer ${a.discount_pct}% off`
                : a.decision === 'decline_discount'
                  ? 'Decline the discount, keep list price'
                  : 'Wait for the customer to name a discount'
            return a.note ? `${what}. Note: ${a.note}` : what
          })()}
        </Bubble>
      )
    case 'human_decision':
    case 'payment':
      return (
        <Bubble agent={e.agent} who={who} accent="#00356b" label={e.kind === 'payment' ? 'paid' : 'decided'} tone="human">
          {e.kind === 'payment' ? 'Approved payment executed.' : 'Recorded an approval decision.'}
        </Bubble>
      )
    case 'limit':
    case 'error':
      return <div className="feed-warn">⚠ {who}: {e.said}</div>
    default:
      return null
  }
}

function Bubble({
  agent,
  who,
  accent,
  label,
  tone,
  children,
}: {
  agent: string
  who: string
  accent: string
  label: string
  tone?: string
  children: ReactNode
}) {
  return (
    <div className={`feed-bubble ${tone ? `tone-${tone}` : ''}`} style={{ '--agent': accent } as CSSProperties}>
      <Avatar agent={agent} size={34} />
      <div className="bubble-body">
        <div className="bubble-head">
          <b>{who}</b> <span>{label}</span>
        </div>
        <div className="bubble-text">{children}</div>
      </div>
    </div>
  )
}

export default function CommsFeed({
  events,
  running,
  ticketId,
}: {
  events: DeskEvent[]
  running: boolean
  ticketId: number | null
}) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (running) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [events.length, running])

  return (
    <section className="holonet" aria-labelledby="feed-title" aria-live="polite">
      <div className="holonet-head">
        <div>
          <span className="eyebrow eyebrow-light">Holonet comms</span>
          <h2 id="feed-title">{ticketId ? `Ticket #${ticketId}` : 'Pick a ticket'}</h2>
        </div>
        {running && (
          <span className="pill pill-live">
            <span className="pulse" /> Live
          </span>
        )}
      </div>
      <div className="feed">
        {events.length === 0 ? (
          <p className="feed-empty">
            No transmissions yet. Dispatch the team and watch each agent think, use tools, and hand off work here.
          </p>
        ) : (
          events.map((e) => <Line key={e.cursor} e={e} />)
        )}
        <div ref={end} />
      </div>
    </section>
  )
}
