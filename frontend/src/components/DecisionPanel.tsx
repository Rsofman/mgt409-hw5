import { useMemo, useState } from 'react'
import { money, type DecisionKind, type DiscountOption, type DiscountOptions, type HumanDecision } from '../api'
import { Avatar } from '../crew'

/** Same math as the MCP discount_options tool, for a custom % or a different quantity. */
function price(opts: DiscountOptions, pct: number, qty: number): DiscountOption {
  const unit = Math.round(opts.list_price * (1 - pct / 100) * 100) / 100
  const revenue = Math.round(unit * qty * 100) / 100
  const profit = Math.round((unit - opts.unit_cost) * qty * 100) / 100
  const listProfit = (opts.list_price - opts.unit_cost) * qty
  return {
    discount_pct: pct,
    unit_price: unit,
    unit_profit: Math.round((unit - opts.unit_cost) * 100) / 100,
    revenue,
    discount_given: Math.round((opts.list_price * qty - revenue) * 100) / 100,
    total_cost: opts.unit_cost * qty,
    profit,
    margin_pct: revenue ? Math.round((profit / revenue) * 10000) / 100 : null,
    profit_given_up: Math.round((listProfit - profit) * 100) / 100,
    below_cost: unit < opts.unit_cost,
  }
}

const LABEL: Record<DecisionKind, string> = {
  offer_discount: 'Offer discount',
  decline_discount: 'Declined, list price',
  wait_for_customer: 'Wait for customer',
}

export default function DecisionPanel({
  options,
  decisions,
  requester,
  signer,
  onSignerChange,
  onDecide,
  disabledReason,
}: {
  options: DiscountOptions
  decisions: HumanDecision[]
  requester: string
  signer: string
  onSignerChange: (name: string) => void
  onDecide: (d: { decision: DecisionKind; discount_pct?: number; note: string }) => Promise<void>
  disabledReason: string | null
}) {
  const [basis, setBasis] = useState<'order' | 'stock'>('order')
  const [selected, setSelected] = useState<number>(10)
  const [custom, setCustom] = useState('')
  const [note, setNote] = useState('')
  const [confirming, setConfirming] = useState<DecisionKind | null>(null)
  const [busy, setBusy] = useState(false)

  const qty = basis === 'order' ? options.qty : Math.min(options.qty_on_hand ?? 0, options.qty)
  const rows = useMemo(() => {
    const pcts = options.options.map((o) => o.discount_pct)
    const customPct = Number(custom)
    if (custom !== '' && customPct > 0 && customPct < 100 && !pcts.includes(customPct)) pcts.push(customPct)
    return pcts.sort((a, b) => a - b).map((p) => price(options, p, qty))
  }, [options, custom, qty])

  const chosen = rows.find((r) => r.discount_pct === selected) ?? null
  const maxProfit = Math.max(...rows.map((r) => r.profit), 1)
  const latest = decisions.at(-1)
  const signed = signer.trim().length > 0
  const canOffer = signed && !!chosen && chosen.discount_pct > 0 && !chosen.below_cost && !disabledReason

  async function submit(kind: DecisionKind) {
    setBusy(true)
    try {
      await onDecide({
        decision: kind,
        discount_pct: kind === 'offer_discount' ? selected : undefined,
        note: note.trim(),
      })
      setConfirming(null)
      setNote('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel decision" aria-labelledby="decision-title">
      <div className="panel-head">
        <span className="eyebrow">Your call · Vader sent this to a human</span>
        <h2 id="decision-title">Decide the discount</h2>
        <p className="muted small">
          {requester} asked for a bulk discount on {options.qty} × {options.name ?? options.sku} (size {options.size}). At
          list price that's <b>{money(options.revenue_at_list)}</b> revenue and <b>{money(options.profit_at_list)}</b>{' '}
          profit. Unit cost is {money(options.unit_cost)} (total cost {money(options.unit_cost * options.qty)}), list price{' '}
          {money(options.list_price)}.{' '}
          <b>{options.qty_on_hand ?? 0}</b> are in stock now.
        </p>
      </div>

      {latest && (
        <div className="decision-latest">
          <Avatar agent={`human:${latest.decided_by}`} size={26} />
          <span>
            Latest decision: <b>{LABEL[latest.decision]}</b>
            {latest.discount_pct !== null && ` ${latest.discount_pct}% (${money(latest.unit_price ?? 0)}/unit)`} by{' '}
            {latest.decided_by}
            {latest.note && <span className="muted"> · "{latest.note}"</span>}
          </span>
        </div>
      )}

      <div className="decision-controls">
        <div className="segmented" role="group" aria-label="Show numbers for">
          <button className={basis === 'order' ? 'on' : ''} onClick={() => setBasis('order')}>
            Full order ({options.qty})
          </button>
          <button className={basis === 'stock' ? 'on' : ''} onClick={() => setBasis('stock')}>
            In stock now ({Math.min(options.qty_on_hand ?? 0, options.qty)})
          </button>
        </div>
        <label className="custom-pct">
          Custom %
          <input
            type="number"
            min={1}
            max={99}
            step={1}
            value={custom}
            onChange={(e) => {
              setCustom(e.target.value)
              if (Number(e.target.value) > 0) setSelected(Number(e.target.value))
            }}
            placeholder="e.g. 12"
          />
        </label>
      </div>

      <div className="table-wrap">
        <table className="options-table">
          <thead>
            <tr>
              <th />
              <th>Discount</th>
              <th>Price / unit</th>
              <th>Revenue</th>
              <th>Discount given</th>
              <th>Profit</th>
              <th>Margin</th>
              <th>vs list</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.discount_pct}
                className={`${selected === r.discount_pct ? 'is-chosen' : ''} ${r.below_cost ? 'is-below' : ''}`}
                onClick={() => !r.below_cost && setSelected(r.discount_pct)}
              >
                <td>
                  <input
                    type="radio"
                    name="discount"
                    aria-label={`${r.discount_pct}% off`}
                    checked={selected === r.discount_pct}
                    disabled={r.below_cost}
                    onChange={() => setSelected(r.discount_pct)}
                  />
                </td>
                <td>
                  <b>{r.discount_pct === 0 ? 'List price' : `${r.discount_pct}% off`}</b>
                </td>
                <td>{money(r.unit_price)}</td>
                <td>{money(r.revenue)}</td>
                <td className="neg-soft">{r.discount_given ? `−${money(r.discount_given)}` : '—'}</td>
                <td>
                  <div className="profit-cell">
                    <span className="profit-bar" style={{ width: `${Math.max(0, (r.profit / maxProfit) * 100)}%` }} />
                    <b>{money(r.profit)}</b>
                  </div>
                </td>
                <td>{r.margin_pct === null ? '—' : `${r.margin_pct}%`}</td>
                <td className={r.profit_given_up ? 'neg-soft' : 'muted'}>
                  {r.below_cost ? 'Below cost' : r.profit_given_up ? `−${money(r.profit_given_up)}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted">
        Revenue = price per unit × quantity. Profit = revenue − cost. Selling below cost starts past{' '}
        <b>{options.break_even_discount_pct}% off</b>, and those discounts are blocked. No cash moves when you decide; the
        team re-runs the ticket and C-3PO drafts the reply (never sent).
      </p>

      <label className="decision-note">
        <span>Note for the team (optional)</span>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="e.g. Repeat customer; offer applies to the 8 in stock now" />
      </label>

      <label className="signer">
        <span>Signing as</span>
        <input value={signer} onChange={(e) => onSignerChange(e.target.value)} placeholder="Your name" />
      </label>

      {confirming ? (
        <div className="confirm">
          <p>
            {confirming === 'offer_discount' && chosen && (
              <>
                Offer <b>{chosen.discount_pct}% off</b>: {money(chosen.unit_price)}/unit, {money(price(options, chosen.discount_pct, options.qty).revenue)} revenue
                and {money(price(options, chosen.discount_pct, options.qty).profit)} profit on {options.qty}?
              </>
            )}
            {confirming === 'decline_discount' && <>Decline the discount and keep list price ({money(options.list_price)}/unit)?</>}
            {confirming === 'wait_for_customer' && <>Wait for {requester} to name the discount they want?</>} The team will re-run
            the ticket.
          </p>
          <div className="row">
            <button className="button" disabled={busy} onClick={() => submit(confirming)}>
              {busy ? 'Saving…' : `Confirm as ${signer.trim()}`}
            </button>
            <button className="button button-ghost" onClick={() => setConfirming(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="row">
          <button className="button" disabled={!canOffer} onClick={() => setConfirming('offer_discount')} title={!signed ? 'Enter your name to sign' : disabledReason ?? ''}>
            {chosen && chosen.discount_pct > 0 ? `Offer ${chosen.discount_pct}% off (${money(chosen.unit_price)}/unit)` : 'Pick a discount'}
          </button>
          <button className="button button-ghost" disabled={!signed || !!disabledReason} onClick={() => setConfirming('decline_discount')}>
            Decline, keep list price
          </button>
          <button className="button button-ghost" disabled={!signed || !!disabledReason} onClick={() => setConfirming('wait_for_customer')}>
            Wait for customer
          </button>
        </div>
      )}
      {disabledReason && <p className="small muted">{disabledReason}</p>}
    </section>
  )
}
