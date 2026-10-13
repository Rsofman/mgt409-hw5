import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  API_URL,
  api,
  ApiError,
  money,
  type Approval,
  type Cash,
  type DecisionKind,
  type DeskEvent,
  type DiscountOptions,
  type HumanDecision,
  type Draft,
  type Payment,
  type Run,
  type Ticket,
  type TicketSummary,
} from './api'
import ApprovalsPanel from './components/ApprovalsPanel'
import CashCard from './components/CashCard'
import CommsFeed from './components/CommsFeed'
import CrewPanel from './components/CrewPanel'
import Debrief from './components/Debrief'
import DecisionPanel from './components/DecisionPanel'
import TicketBoard from './components/TicketBoard'
import { CREW } from './crew'

type Toast = { tone: 'good' | 'bad' | 'info'; text: string }

const POLL_EVENTS_MS = 1200
const POLL_RUN_MS = 2000
const POLL_IDLE_MS = 10000

// Optional deep link: /?ticket=102 opens that ticket.
const LINKED_TICKET = Number(new URLSearchParams(window.location.search).get('ticket')) || null

/** Events from the ticket's latest run onward (plus any approvals after it). */
function latestRun(events: DeskEvent[]): DeskEvent[] {
  let start = -1
  events.forEach((e, i) => {
    if (e.kind === 'run_start' && e.name === 'ticket') start = i
  })
  return start === -1 ? events : events.slice(start)
}

function elapsed(since: string): string {
  const s = Math.max(0, Math.floor((Date.now() - new Date(since).getTime()) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [dateToday, setDateToday] = useState<string>('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [eventsByTicket, setEventsByTicket] = useState<Record<number, DeskEvent[]>>({})
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [decisions, setDecisions] = useState<HumanDecision[]>([])
  const [discount, setDiscount] = useState<DiscountOptions | null>(null)
  const [activeRun, setActiveRun] = useState<Run | null>(null)
  const [offline, setOffline] = useState(false)
  const [toast, setToast] = useState<Toast | null>(null)
  const [signer, setSigner] = useState(() => localStorage.getItem('desk-signer') ?? '')
  const [, tick] = useState(0)
  const cursor = useRef<number | null>(null)

  const notify = useCallback((t: Toast) => {
    setToast(t)
    window.setTimeout(() => setToast((cur) => (cur === t ? null : cur)), 6000)
  }, [])

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 0) setOffline(true)
      else notify({ tone: 'bad', text: err instanceof Error ? err.message : String(err) })
    },
    [notify],
  )

  // ---------------------------------------------------------------- loading

  const refreshBoard = useCallback(async () => {
    try {
      const [t, c, a, r] = await Promise.all([api.tickets(), api.cash(), api.approvals(), api.runs()])
      setTickets(t.tickets)
      setDateToday(t.date_today)
      setCash(c)
      setApprovals(a.approvals)
      setOffline(false)
      setSelected((cur) => cur ?? LINKED_TICKET ?? t.tickets[0]?.id ?? null)
      const live = r.active_run ? r.runs.find((x) => x.run_id === r.active_run) ?? null : null
      setActiveRun((cur) => (live ? cur ?? live : cur && cur.status === 'running' ? cur : null))
    } catch (err) {
      handleError(err)
    }
  }, [handleError])

  const loadTicket = useCallback(
    async (id: number) => {
      try {
        const [ev, s, b] = await Promise.all([
          api.events({ ticket_id: id, limit: 500 }),
          api.summary(id),
          api.board(id),
        ])
        setEventsByTicket((m) => ({ ...m, [id]: ev.events }))
        setSummary(s)
        setDrafts(b.drafts)
        setDecisions(b.human_decisions ?? [])
        setDiscount(b.ticket.type === 'price_override' ? await api.discountOptions(id) : null)
      } catch (err) {
        handleError(err)
      }
    },
    [handleError],
  )

  useEffect(() => {
    refreshBoard()
    api
      .events({ limit: 1 })
      .then((ev) => (cursor.current = ev.next_after))
      .catch(() => undefined)
  }, [refreshBoard])

  useEffect(() => {
    if (selected !== null) loadTicket(selected)
  }, [selected, loadTicket])

  // Quiet refresh while idle, so CLI changes and other tabs show up.
  useEffect(() => {
    if (activeRun) return
    const id = window.setInterval(refreshBoard, POLL_IDLE_MS)
    return () => window.clearInterval(id)
  }, [activeRun, refreshBoard])

  // ---------------------------------------------------------------- live run

  useEffect(() => {
    if (!activeRun) return
    const evTimer = window.setInterval(async () => {
      try {
        const ev = await api.events({ after: cursor.current, limit: 500 })
        if (ev.events.length === 0) return
        cursor.current = ev.next_after
        setEventsByTicket((m) => {
          const next = { ...m }
          for (const e of ev.events) {
            if (e.ticket_id === null) continue
            const list = next[e.ticket_id] ?? []
            if (!list.some((x) => x.cursor === e.cursor)) next[e.ticket_id] = [...list, e]
          }
          return next
        })
      } catch {
        /* next tick retries */
      }
    }, POLL_EVENTS_MS)

    const runTimer = window.setInterval(async () => {
      try {
        const run = await api.run(activeRun.run_id)
        if (run.status === 'running') return
        setActiveRun(null)
        await refreshBoard()
        await loadTicket(run.ticket_id)
        if (run.status === 'finished') {
          notify({ tone: 'good', text: `Ticket #${run.ticket_id} resolved by the team. See the debrief.` })
        } else {
          notify({ tone: 'bad', text: `Run on #${run.ticket_id} failed: ${run.error}` })
        }
      } catch (err) {
        handleError(err)
      }
    }, POLL_RUN_MS)

    const clock = window.setInterval(() => tick((n) => n + 1), 1000)
    return () => {
      window.clearInterval(evTimer)
      window.clearInterval(runTimer)
      window.clearInterval(clock)
    }
  }, [activeRun, refreshBoard, loadTicket, notify, handleError])

  // ---------------------------------------------------------------- actions

  async function dispatch(id: number) {
    try {
      const run = await api.runTicket(id)
      setActiveRun(run)
      setTickets((ts) => ts.map((t) => (t.id === id ? { ...t, running: true } : t)))
      notify({ tone: 'info', text: `Lord Vader has opened ticket #${id}. The team is on it.` })
    } catch (err) {
      handleError(err)
    }
  }

  async function decide(d: { decision: DecisionKind; discount_pct?: number; note: string }) {
    if (selected === null) return
    try {
      const res = await api.decide(selected, { decided_by: signer.trim(), ...d })
      notify({ tone: 'good', text: `Decision recorded: ${res.summary}. The team is re-running #${selected}.` })
      await loadTicket(selected)
      await dispatch(selected)
    } catch (err) {
      handleError(err)
    }
  }

  async function approve(a: Approval) {
    try {
      const res = await api.approve(a.id, signer.trim())
      setPayments((p) => [res.payment, ...p])
      setCash(res.cash)
      notify({
        tone: 'good',
        text: `Paid ${money(res.payment.amount)} to ${res.payment.payee}. Checking is now ${money(res.cash.balance)}.`,
      })
      await refreshBoard()
      if (selected !== null) await loadTicket(selected)
    } catch (err) {
      handleError(err)
      await refreshBoard()
    }
  }

  async function reject(a: Approval) {
    try {
      await api.reject(a.id, signer.trim())
      notify({ tone: 'info', text: `Request #${a.id} rejected. No money moved.` })
      await refreshBoard()
    } catch (err) {
      handleError(err)
    }
  }

  async function reset() {
    if (!window.confirm('Reset the shop database to its original values? The audit trail is kept.')) return
    try {
      await api.reset()
      setPayments([])
      setEventsByTicket({})
      await refreshBoard()
      if (selected !== null) await loadTicket(selected)
      notify({ tone: 'info', text: 'Database reset to the original values. Fresh run ready.' })
    } catch (err) {
      handleError(err)
    }
  }

  function changeSigner(name: string) {
    setSigner(name)
    localStorage.setItem('desk-signer', name)
  }

  // ---------------------------------------------------------------- derived

  const ticket = tickets.find((t) => t.id === selected) ?? null
  const feed = useMemo(() => latestRun(selected !== null ? eventsByTicket[selected] ?? [] : []), [eventsByTicket, selected])
  const runningHere = !!activeRun && activeRun.ticket_id === selected
  const busyElsewhere = !!activeRun && !runningHere

  return (
    <div className="app">
      <header className="nav">
        <div className="nav-inner">
          <div className="brand">
            <span className="brand-mark">CC</span>
            <span className="brand-text">
              Campus Customs
              <small>Operations Desk</small>
            </span>
          </div>
          <div className="nav-right">
            {dateToday && (
              <span className="chip">
                Shop date <b>{dateToday}</b>
              </span>
            )}
            {cash && (
              <span className="chip chip-cash" title="Checking balance">
                Checking <b>{money(cash.balance)}</b>
              </span>
            )}
            <button className="button button-ghost button-sm" onClick={reset} disabled={!!activeRun}>
              Reset database
            </button>
          </div>
        </div>
      </header>

      {offline && (
        <div className="banner" role="alert">
          Can't reach the desk API at <code>{API_URL}</code>. Start it from <code>backend/</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.{' '}
          <button className="link-button" onClick={refreshBoard}>
            Try again
          </button>
        </div>
      )}

      <main className="main">
        <section className="intro">
          <div>
            <span className="eyebrow">Mock shop · nothing leaves this desk</span>
            <h1>The Ops Desk</h1>
            <p className="lead">
              Pick a ticket, dispatch the team, and watch them work. Money only moves when you sign for it.
            </p>
          </div>
          <ol className="steps" aria-label="How to use the desk">
            <li>
              <b>1</b> Pick a ticket
            </li>
            <li>
              <b>2</b> Dispatch the team
            </li>
            <li>
              <b>3</b> Sign off on payments
            </li>
          </ol>
        </section>

        <div className="layout">
          <aside className="col col-left">
            <TicketBoard tickets={tickets} selected={selected} onSelect={setSelected} />
          </aside>

          <div className="col col-center">
            {ticket && (
              <section className="panel ticket-focus">
                <div className="focus-head">
                  <div>
                    <span className="eyebrow">
                      Ticket #{ticket.id} · {ticket.requester}
                    </span>
                    <h2>{ticket.subject}</h2>
                    <p className="muted">{ticket.notes}</p>
                  </div>
                  <div className="dispatch">
                    <button
                      className="button button-lg button-dispatch"
                      onClick={() => dispatch(ticket.id)}
                      disabled={!!activeRun || offline}
                    >
                      {runningHere
                        ? `Team working · ${elapsed(activeRun!.started_at)}`
                        : ticket.state === 'resolved'
                          ? 'Run the team again'
                          : 'Dispatch the team'}
                    </button>
                    {busyElsewhere && (
                      <p className="small muted">The team is busy on #{activeRun!.ticket_id}. One ticket at a time.</p>
                    )}
                    {!activeRun && ticket.state === 'resolved' && (
                      <p className="small muted">Resolved. Re-run after a payment to let Vader close it out.</p>
                    )}
                  </div>
                </div>
              </section>
            )}

            {ticket && discount && !runningHere && ticket.state === 'resolved' && (
              <DecisionPanel
                key={ticket.id}
                options={discount}
                decisions={decisions}
                requester={ticket.requester}
                signer={signer}
                onSignerChange={changeSigner}
                onDecide={decide}
                disabledReason={activeRun ? 'Decisions unlock when the current run finishes.' : null}
              />
            )}
            <CommsFeed events={feed} running={runningHere} ticketId={selected} />
            {!runningHere && <Debrief summary={summary} drafts={drafts} />}
          </div>

          <aside className="col col-right">
            <CashCard cash={cash} payments={payments} />
            <ApprovalsPanel
              approvals={approvals}
              balance={cash?.balance ?? null}
              signer={signer}
              onSignerChange={changeSigner}
              onApprove={approve}
              onReject={reject}
              disabledReason={activeRun ? 'Approvals unlock when the current run finishes.' : null}
            />
            <CrewPanel events={feed} running={runningHere} />
          </aside>
        </div>
      </main>

      <footer className="footer">
        <span>
          Campus Customs Ops Desk · all agents run gpt-6-luna · shop data via the campus-customs MCP server
        </span>
        <span className="footer-cast">{CREW.map((c) => c.character).join(' · ')}</span>
      </footer>

      {toast && (
        <div className={`toast toast-${toast.tone}`} role="status">
          {toast.text}
        </div>
      )}
    </div>
  )
}
