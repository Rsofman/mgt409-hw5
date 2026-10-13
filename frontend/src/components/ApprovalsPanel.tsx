import { useState } from 'react'
import { money, type Approval } from '../api'
import { Avatar, speakerName } from '../crew'

const KIND: Record<Approval['kind'], string> = {
  invoice: 'Vendor invoice',
  rent: 'Rent',
  purchase_order: 'Purchase order',
}

function what(a: Approval): string {
  if (a.kind === 'invoice') return `Invoice ${a.ref_id}`
  if (a.kind === 'rent') return `Lease ${a.ref_id}`
  return `${a.qty} × ${a.sku} size ${a.size}`
}

export default function ApprovalsPanel({
  approvals,
  balance,
  signer,
  onSignerChange,
  onApprove,
  onReject,
  disabledReason,
}: {
  approvals: Approval[]
  balance: number | null
  signer: string
  onSignerChange: (name: string) => void
  onApprove: (a: Approval) => Promise<void>
  onReject: (a: Approval) => Promise<void>
  disabledReason: string | null
}) {
  const [confirming, setConfirming] = useState<number | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const signed = signer.trim().length > 0

  async function act(a: Approval, fn: (a: Approval) => Promise<void>) {
    setBusy(a.id)
    try {
      await fn(a)
    } finally {
      setBusy(null)
      setConfirming(null)
    }
  }

  return (
    <section className="panel panel-approvals" aria-labelledby="approvals-title">
      <div className="panel-head">
        <span className="eyebrow">Human approval required</span>
        <h2 id="approvals-title">Needs your signature</h2>
        <p className="muted small">
          Agents only prepare payments. Nothing is paid and no cash moves until a person approves it here.
        </p>
      </div>

      <label className="signer">
        <span>Signing as</span>
        <input
          value={signer}
          onChange={(e) => onSignerChange(e.target.value)}
          placeholder="Your name"
          autoComplete="name"
        />
      </label>

      {approvals.length === 0 ? (
        <p className="empty-note">No payments waiting. When Lando prepares one, it lands here for you.</p>
      ) : (
        <ul className="approval-list">
          {approvals.map((a) => {
            const after = balance === null ? null : balance - a.amount
            const short = after !== null && after < 0
            return (
              <li key={a.id} className="approval-card">
                <div className="approval-top">
                  <span className="approval-kind">{KIND[a.kind]}</span>
                  <span className="approval-ticket">Ticket #{a.ticket_id} · request #{a.id}</span>
                </div>
                <div className="approval-amount">{money(a.amount)}</div>
                <div className="approval-payee">
                  to <b>{a.payee}</b> · {what(a)}
                </div>
                <p className="approval-reason">{a.reason}</p>
                <div className="approval-by">
                  <Avatar agent={a.requested_by} size={22} /> Prepared by {speakerName(a.requested_by)}
                </div>

                {confirming === a.id ? (
                  <div className="confirm">
                    <p>
                      Pay <b>{money(a.amount)}</b> to {a.payee} from checking?
                      {after !== null && (
                        <>
                          {' '}
                          Balance after: <b className={short ? 'neg' : ''}>{money(after)}</b>
                        </>
                      )}
                    </p>
                    <div className="row">
                      <button className="button" disabled={busy === a.id} onClick={() => act(a, onApprove)}>
                        {busy === a.id ? 'Paying…' : `Approve & pay as ${signer.trim()}`}
                      </button>
                      <button className="button button-ghost" onClick={() => setConfirming(null)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="row">
                    <button
                      className="button"
                      disabled={!signed || !!disabledReason || short}
                      title={
                        !signed ? 'Enter your name to sign' : disabledReason ?? (short ? 'Not enough cash' : '')
                      }
                      onClick={() => setConfirming(a.id)}
                    >
                      Approve…
                    </button>
                    <button
                      className="button button-ghost"
                      disabled={!signed || busy === a.id}
                      onClick={() => act(a, onReject)}
                    >
                      Reject
                    </button>
                  </div>
                )}
                {short && <p className="warn-note">Checking can't cover this. It will be refused.</p>}
              </li>
            )
          })}
        </ul>
      )}
      {disabledReason && approvals.length > 0 && <p className="muted small">{disabledReason}</p>}
    </section>
  )
}
