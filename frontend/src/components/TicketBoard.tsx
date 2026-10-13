import type { BoardStatus, Ticket } from '../api'

export const OUTCOME: Record<BoardStatus, { label: string; tone: string }> = {
  open: { label: 'New', tone: 'neutral' },
  resolved: { label: 'Done', tone: 'good' },
  awaiting_approval: { label: 'Awaiting your approval', tone: 'warn' },
  blocked: { label: 'Blocked', tone: 'bad' },
  needs_human: { label: 'Needs a human', tone: 'bad' },
}

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
  vendor_invoice: 'Vendor invoice',
}

function detail(t: Ticket): string {
  if (t.sku) return `${t.qty ?? ''} × ${t.sku} · size ${t.size}`
  if (t.lease_id) return `Lease ${t.lease_id}`
  if (t.invoice_id) return `Invoice ${t.invoice_id}`
  return t.notes ?? ''
}

export default function TicketBoard({
  tickets,
  selected,
  onSelect,
}: {
  tickets: Ticket[]
  selected: number | null
  onSelect: (id: number) => void
}) {
  return (
    <section className="panel" aria-labelledby="board-title">
      <div className="panel-head">
        <span className="eyebrow">The board</span>
        <h2 id="board-title">Tickets</h2>
      </div>
      <ul className="ticket-list">
        {tickets.map((t) => {
          const outcome = OUTCOME[t.status] ?? OUTCOME.open
          return (
            <li key={t.id}>
              <button
                className={`ticket-card ${selected === t.id ? 'is-selected' : ''} ${
                  t.state === 'resolved' ? 'is-resolved' : ''
                }`}
                onClick={() => onSelect(t.id)}
                aria-pressed={selected === t.id}
              >
                <div className="ticket-top">
                  <span className="ticket-id">#{t.id}</span>
                  <span className="ticket-type">{TYPE_LABEL[t.type] ?? t.type}</span>
                  {t.running ? (
                    <span className="pill pill-live">
                      <span className="pulse" /> Team working
                    </span>
                  ) : (
                    <span className={`pill pill-${t.state}`}>{t.state === 'resolved' ? 'Resolved' : 'Open'}</span>
                  )}
                </div>
                <h3 className="ticket-subject">{t.subject}</h3>
                <p className="ticket-meta">
                  {t.requester} · {detail(t)}
                </p>
                {t.state === 'resolved' && (
                  <div className="ticket-foot">
                    <span className={`outcome outcome-${outcome.tone}`}>{outcome.label}</span>
                  </div>
                )}
                {t.state === 'resolved' && <span className="stamp" aria-hidden="true">Resolved</span>}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
