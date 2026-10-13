import type { CSSProperties } from 'react'
import type { DeskEvent } from '../api'
import { Avatar, CREW, speakerName } from '../crew'

type Activity = { state: 'idle' | 'working' | 'done'; text: string }

/** What each agent is doing right now, from the latest events of the active run. */
export function crewActivity(events: DeskEvent[], running: boolean): Record<string, Activity> {
  const out: Record<string, Activity> = {}
  for (const e of events) {
    switch (e.kind) {
      case 'agent_start':
        out[e.agent] = { state: 'working', text: 'Received orders, thinking…' }
        break
      case 'model_request':
      case 'model_response':
        if (out[e.agent]?.state !== 'done') out[e.agent] = { state: 'working', text: 'Thinking…' }
        break
      case 'tool_call':
        out[e.agent] = { state: 'working', text: `Using ${e.name}` }
        break
      case 'delegation':
        out[e.agent] = { state: 'working', text: `Briefing ${speakerName(e.name)}` }
        break
      case 'report':
      case 'agent_output':
        out[e.agent] = { state: 'done', text: 'Reported back' }
        break
      case 'status':
        out.boss = { state: 'done', text: 'Made the final call' }
        break
    }
  }
  if (!running) {
    for (const key of Object.keys(out)) {
      if (out[key].state === 'working') out[key] = { state: 'done', text: 'Finished' }
    }
  }
  return out
}

export default function CrewPanel({ events, running }: { events: DeskEvent[]; running: boolean }) {
  const activity = crewActivity(events, running)
  return (
    <section className="panel" aria-labelledby="crew-title">
      <div className="panel-head">
        <span className="eyebrow">The crew</span>
        <h2 id="crew-title">Agent team</h2>
      </div>
      <ul className="crew-list">
        {CREW.map((m) => {
          const a = activity[m.key] ?? { state: 'idle', text: 'Standing by' }
          return (
            <li key={m.key} className={`crew-row crew-${a.state}`} style={{ '--agent': m.color } as CSSProperties}>
              <Avatar agent={m.key} size={44} />
              <div className="crew-text">
                <div className="crew-name">
                  {m.character} <span className="crew-role">{m.role}</span>
                </div>
                <div className="crew-doing">
                  <span className={`light light-${a.state}`} aria-hidden="true" />
                  {a.text}
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
