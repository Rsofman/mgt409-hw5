// The agent team, cast as Star Wars characters. Avatars are simple original SVG
// drawings (no film images), so they stay crisp and on-palette.

import type { ReactNode } from 'react'

export type AgentKey = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface CrewMember {
  key: AgentKey
  character: string
  role: string
  job: string
  quote: string
  color: string
  avatar: ReactNode
}

const Vader = (
  <svg viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="32" r="32" fill="#14161b" />
    <path d="M14 46c0-17 7-30 18-30s18 13 18 30l-6 6H20z" fill="#2a2d34" />
    <path d="M18 30h28l-2 6H20z" fill="#0b0c0f" />
    <path d="M22 31l5 3h10l5-3" stroke="#5b6170" strokeWidth="1.5" fill="none" />
    <path d="M32 36l-6 14h12z" fill="#0b0c0f" />
    <path d="M29 40h6M28.5 43h7M28 46h8" stroke="#5b6170" strokeWidth="1" />
    <rect x="5" y="56" width="22" height="3" rx="1.5" fill="#e0242f" />
  </svg>
)

const R2 = (
  <svg viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="32" r="32" fill="#e8eef5" />
    <path d="M14 34a18 18 0 0 1 36 0z" fill="#f4f6f9" stroke="#b9c3d0" />
    <rect x="14" y="34" width="36" height="22" fill="#f4f6f9" stroke="#b9c3d0" />
    <rect x="22" y="21" width="9" height="7" rx="1" fill="#2b5fa8" />
    <circle cx="37" cy="25" r="3.5" fill="#1b1f27" />
    <circle cx="37" cy="25" r="1.4" fill="#d62f2f" />
    <rect x="19" y="39" width="26" height="4" fill="#2b5fa8" />
    <rect x="22" y="46" width="6" height="7" fill="#2b5fa8" />
    <rect x="36" y="46" width="6" height="7" fill="#2b5fa8" />
  </svg>
)

const Lando = (
  <svg viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="32" r="32" fill="#e3ecf4" />
    <path d="M10 64c2-12 10-17 22-17s20 5 22 17z" fill="#00356b" />
    <path d="M24 49l8 8 8-8" fill="#f2d48f" />
    <ellipse cx="32" cy="31" rx="11" ry="13" fill="#8a5a3c" />
    <path d="M21 26c1-8 6-11 11-11s10 3 11 11c-3-4-7-5-11-5s-8 1-11 5z" fill="#1d1712" />
    <path d="M25 37c4 3 10 3 14 0-2 1-5 2-7 2s-5-1-7-2z" fill="#1d1712" />
    <circle cx="28" cy="30" r="1.3" fill="#1d1712" />
    <circle cx="36" cy="30" r="1.3" fill="#1d1712" />
  </svg>
)

const Chewie = (
  <svg viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="32" r="32" fill="#f1e7da" />
    <path d="M12 60c-2-24 6-44 20-44s22 20 20 44z" fill="#7a5233" />
    <path d="M18 34c4-6 9-8 14-8s10 2 14 8c-4-2-9-3-14-3s-10 1-14 3z" fill="#5c3c24" />
    <circle cx="26" cy="33" r="1.8" fill="#1d1712" />
    <circle cx="38" cy="33" r="1.8" fill="#1d1712" />
    <ellipse cx="32" cy="41" rx="5" ry="3" fill="#3b2617" />
    <path d="M14 46l40 14" stroke="#8b8f97" strokeWidth="5" />
    <path d="M20 48l3 1M28 51l3 1M36 54l3 1" stroke="#c8ccd2" strokeWidth="3" />
  </svg>
)

const Threepio = (
  <svg viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="32" r="32" fill="#f6f0dd" />
    <ellipse cx="32" cy="33" rx="14" ry="17" fill="#d9a92b" />
    <path d="M18 30c2-10 8-14 14-14s12 4 14 14" fill="#e8bd45" />
    <circle cx="26" cy="31" r="3.4" fill="#fff6c9" stroke="#8a6412" />
    <circle cx="38" cy="31" r="3.4" fill="#fff6c9" stroke="#8a6412" />
    <rect x="27" y="40" width="10" height="3" rx="1.5" fill="#8a6412" />
    <path d="M30 46h4" stroke="#8a6412" strokeWidth="1.5" />
  </svg>
)

export const CREW: CrewMember[] = [
  {
    key: 'boss',
    character: 'Darth Vader',
    role: 'Boss',
    job: 'Reads every ticket, gives the orders, checks the evidence, makes the final call.',
    quote: 'I find your lack of approval disturbing.',
    color: '#c8102e',
    avatar: Vader,
  },
  {
    key: 'inventory',
    character: 'R2-D2',
    role: 'Inventory',
    job: 'Scans the shelves, finds shortfalls, and tracks which vendor can restock.',
    quote: 'Beep-boop. Shelves scanned.',
    color: '#2b5fa8',
    avatar: R2,
  },
  {
    key: 'accounting',
    character: 'Lando Calrissian',
    role: 'Accounting',
    job: 'Runs cash, invoices, and margins. Prepares payments for your signature.',
    quote: 'This deal is getting worse all the time.',
    color: '#00356b',
    avatar: Lando,
  },
  {
    key: 'facilities',
    character: 'Chewbacca',
    role: 'Facilities',
    job: 'Keeps the shop flying: leases, rent, due dates. Hands rent to Lando.',
    quote: 'Rrrraaaarrgh.',
    color: '#7a5233',
    avatar: Chewie,
  },
  {
    key: 'customer_service',
    character: 'C-3PO',
    role: 'Customer Service',
    job: 'Drafts polite customer replies from confirmed facts. Never sends them.',
    quote: 'Fluent in over six million forms of communication.',
    color: '#b8861b',
    avatar: Threepio,
  },
]

export const crewByKey = Object.fromEntries(CREW.map((c) => [c.key, c])) as Record<
  AgentKey,
  CrewMember
>

export function crewFor(agent: string): CrewMember | undefined {
  return crewByKey[agent as AgentKey]
}

/** Display name for any event author: crew, the system, or a human approver. */
export function speakerName(agent: string): string {
  const member = crewFor(agent)
  if (member) return member.character
  if (agent.startsWith('human:')) return agent.slice(6)
  if (agent === 'system') return 'Desk'
  return agent
}

export function Avatar({ agent, size = 40 }: { agent: string; size?: number }) {
  const member = crewFor(agent)
  const style = { width: size, height: size }
  if (member) {
    return (
      <span className="avatar" style={style} title={`${member.character} · ${member.role}`}>
        {member.avatar}
      </span>
    )
  }
  const label = agent.startsWith('human:') ? agent.slice(6, 7).toUpperCase() : 'CC'
  return (
    <span className={`avatar avatar-text ${agent.startsWith('human:') ? 'avatar-human' : ''}`} style={style}>
      {label}
    </span>
  )
}
