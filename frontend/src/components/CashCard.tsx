import { useEffect, useRef, useState } from 'react'
import { money, type Cash, type Payment } from '../api'

/** Animate from the previous value to the new one so a payment visibly drains the balance. */
function useCountTo(target: number | null, ms = 900): number | null {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    if (target === null) return
    const start = from.current ?? target
    if (start === target) {
      setShown(target)
      return
    }
    const t0 = performance.now()
    let raf = 0
    const step = (now: number) => {
      const p = Math.min((now - t0) / ms, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setShown(start + (target - start) * eased)
      if (p < 1) raf = requestAnimationFrame(step)
      else from.current = target
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return shown
}

export default function CashCard({ cash, payments }: { cash: Cash | null; payments: Payment[] }) {
  const shown = useCountTo(cash?.balance ?? null)
  const last = payments[0]
  const coverage = cash && cash.total_obligations > 0 ? Math.min(cash.balance / cash.total_obligations, 1) : 1

  return (
    <section className="panel cash-card" aria-labelledby="cash-title">
      <div className="panel-head">
        <span className="eyebrow">Checking · cash_accounts</span>
        <h2 id="cash-title" className="sr-only">
          Checking balance
        </h2>
      </div>
      <div className={`cash-figure ${last ? 'just-paid' : ''}`} key={last?.payment_id ?? 'none'}>
        {shown === null ? '—' : money(shown)}
      </div>
      {cash && <p className="muted small">As of shop date {cash.as_of}. No revenue is modeled, so cash only goes down.</p>}

      {cash && (
        <div className="obligations">
          <div className="bar" aria-hidden="true">
            <span style={{ width: `${coverage * 100}%` }} className={cash.can_cover_all ? '' : 'short'} />
          </div>
          <p className="small">
            Owed against it: <b>{money(cash.total_obligations)}</b>{' '}
            {cash.can_cover_all ? (
              <span className="ok">covered</span>
            ) : (
              <span className="neg">short {money(cash.shortfall)}</span>
            )}
          </p>
        </div>
      )}

      {payments.length > 0 && (
        <ul className="ledger" aria-label="Payments approved this session">
          {payments.map((p) => (
            <li key={p.payment_id}>
              <span className="neg">−{money(p.amount)}</span>
              <span>
                {p.payee} <span className="muted">({p.kind}, approved by {p.approved_by})</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
