# Ops Desk dashboard: design choices

The dashboard (`frontend/`, React + Vite + TypeScript) is where a person watches the agent team work tickets and signs off on money. It talks only to the FastAPI backend at `http://localhost:8000`. Start it with `npm run dev` from `frontend/`, which opens http://localhost:5173.

## Look: the Yale system from Homework 4

- **Same visual system as the Homework 4 store.** Warm paper background (`#F6F4EF`), white cards with warm hairline borders, **Yale Blue `#00356B`** for headings, buttons, and key numbers, and deep midnight `#071426` used sparingly. Headlines use Yale New (falls back to Georgia); body and UI use Mallory (falls back to Arial). Buttons, the "CC" brand mark, eyebrow labels, and chips are reused from Homework 4, so the desk feels like the back office of the same shop.
- **Why:** staff trust a tool that looks official and calm. Light, high-contrast pages are easier to read during a long shift than a dark "hacker console".
- **One dark panel on purpose.** The only dark surface is the agent feed, in the same way Homework 4 used navy only for the chat. It pulls the eye to where things are moving, and keeps the money panels light and sober.

## Layout

Three columns on a laptop, reading left to right in the order a person works:

| Left: **the board** | Center: **the work** | Right: **money and people** |
|---|---|---|
| The three ticket cards, with status, requester, item, and outcome | The selected ticket with a big **Dispatch the team** button, the live **Holonet comms** feed, and the **Mission debrief** after the run | **Checking balance**, **Needs your signature** (approvals), and the **Agent team** roster with live status lights |

- A three-step strip at the top (**1 Pick a ticket · 2 Dispatch the team · 3 Sign off on payments**) teaches the page in one glance.
- The side columns are sticky, so the balance and the approval queue stay in view while the feed scrolls.
- On narrower screens the right column drops below as a grid. On phones everything stacks in one column, board first.

## How the agents read

- **Cast as Star Wars characters**, each matched to the job:
  - **Darth Vader:** the boss who gives orders and makes the final call
  - **R2-D2:** inventory; the astromech scans the shelves
  - **Lando Calrissian:** accounting; the Cloud City administrator runs the books
  - **Chewbacca:** facilities; the co-pilot keeps the ship (the shop) flying
  - **C-3PO:** customer service; the protocol droid is "fluent in over six million forms of communication"
- **Original SVG avatars**, not film stills. They're simple, on-palette drawings (Vader's helmet with a thin red saber, R2's blue dome, C-3PO's gold face), so they stay crisp at any size and don't clash with the Yale palette.
- **The feed reads like a conversation, not a log:**
  - **Speech bubbles** for what an agent says, with a colored edge in that character's color.
  - **Hand-offs** read "Darth Vader → R2-D2" with the exact task, including ticket and SKU ids.
  - **Tool use** is a compact line: who, a tool chip (`check_stock`), and the arguments (`sku=CC-TEE-WHITE, size=S, qty_needed=1`). You can see what each agent is doing without opening a JSON blob.
  - **Vader's final call** is a red-edged "final call" bubble. The status change shows as a white pill: "Ticket #101 marked Awaiting your approval."
- **Live crew roster.** Each character has a status light: grey *standing by*, pulsing blue *thinking / using check_cash / briefing Lando*, green *reported back*. The agent who is working gets a glowing ring in their color, so you can tell at a glance who has the ball.
- **Noise is filtered out.** Raw prompts and raw tool results stay in `output/audit_trail.json` for auditors. The page shows only what a person needs to follow the story.

## How resolved tickets show up

- When a run finishes, the card gets a **"Resolved" rubber stamp** in Yale Blue, tilted like a registrar's seal, with a quick "thunk" animation. The pill switches from *Open* to *Resolved*.
- "Resolved" means *the team finished and Vader made the call*. The **outcome badge** under it says what the call was: *Done*, *Awaiting your approval* (amber), *Blocked*, or *Needs a human* (red). A ticket can be resolved by the team and still need you, and the page says so plainly.
- The **Mission debrief** appears on the ticket:
  - Vader's ruling: outcome, priority, plain summary, payments he recommends in pay order, cash priority note, why a human is needed, next steps
  - One card per agent: their last report in one or two sentences, the tools they used (with counts), and who they handed work to
  - C-3PO's customer message, marked **"Draft · not sent"**
  - The budget used ("18 of 30 tool calls · 4 of 8 hand-offs")

## How cash shows up

- **Checking is the biggest number on the page**, in Yale New, top right, and repeated as a chip in the header.
- **Payments visibly drain it.** After you approve, the number counts down to the new balance and flashes red, then settles back to blue. A ledger line appears under it: "−$840.00 Bulldog Print Co (invoice, approved by Roman Sofman)."
- **An obligations bar** shows how much of what's owed (open invoices, rent due, pending approvals) the balance covers. It turns amber with "short $X" when cash can't cover everything. That's the cue for Vader's pay order.
- A one-line reminder under the number: *No revenue is modeled, so cash only goes down.*

## Human approval is built into the layout

- **Needs your signature** has a Yale Blue top rule and its own "Signing as" field in italic serif, so approving feels like signing a check.
- Each request shows the amount, payee, what it pays (invoice, lease, or PO line), the agent's reason, and who prepared it ("Prepared by Lando Calrissian").
- **Approval takes two steps:** *Approve…* opens a confirm box ("Pay $840.00 to Bulldog Print Co from checking? Balance after: $2,560.00") before *Approve & pay as Roman Sofman*.
- **The buttons stay locked** until a name is entered, while a run is in progress, and when checking can't cover the amount. The backend enforces the same rules, so the page can't be talked around.
- Agents never see this panel's actions. The only route that moves cash runs when a person clicks.

## Deciding a discount (added after Problem 9)

When Vader sends a price-override ticket to a human, the ticket shows a **Decide the discount** panel under the ticket header. It uses the same Yale Blue top rule as the signature panel, so judgment calls and money approvals look alike.

- **A plain sentence first:** who asked, how many, revenue and profit at list price, unit cost, and how many are in stock now.
- **A profitability table** with one row per discount (list price, 5%–30%, plus any custom %). Each row shows the price per unit, **revenue after the discount**, the discount given in dollars, profit (with a small green bar so you can compare rows at a glance), margin %, and the profit given up compared with list price.
- **"Full order / In stock now" toggle:** the same table for the full order (20) or only what can ship today (8), because the shop can't promise the other 12.
- **Below-cost rows are disabled.** The break-even discount is spelled out, and the MCP tool refuses below-cost offers too.
- **Three clear choices:** *Offer X% off ($Y/unit)*, *Decline, keep list price*, or *Wait for customer*. Each comes with an optional note to the team, a signature, and a confirm step.
- **The team acts on it right away.** Saving the decision re-runs the ticket: Lando confirms the numbers, and C-3PO drafts the offer at exactly that price (never sent). The latest decision shows on the panel and in the comms feed.

## Small things that make it feel special

- The **Dispatch** button has a faint red lightsaber edge, the only place Vader's red appears outside his own bubbles.
- The comms panel has a few faint stars behind the text, a quiet nod to the theme that doesn't hurt readability.
- Live run timer on the button ("Team working · 0:46") and a red **Live** pill on the feed and the ticket card.
- Toasts in plain language: "Lord Vader has opened ticket #101. The team is on it." / "Paid $840.00 to Bulldog Print Co. Checking is now $2,560.00."
- The character quotes ("I find your lack of approval disturbing.") live in the code for flavor but are kept out of the working feed, which stays factual.
- A "Mock shop · nothing leaves this desk" line at the top, so nobody worries the agents are emailing real people.

## What a human would want from it

- **See everything at once:** which tickets need you, how much cash there is, and what's waiting for a signature, without clicking around.
- **Trust but verify:** every claim in the debrief comes from a named tool the agents actually called, and the full trail is in the audit file.
- **Stay in control of money:** nothing is paid without a typed name and a confirm, and the balance change is impossible to miss.
- **Know what to do next:** the outcome badge and Vader's next steps say exactly what the human owes the ticket (approve request #1, decide on the discount, re-run after paying).
- **Recover safely:** *Reset database* (with a confirm) gives a fresh run. The audit trail is never wiped.
- **Clear failure messages:** if the backend isn't running, a banner gives the exact command to start it, instead of an empty page.
- **Accessible:** keyboard-focus outlines, `aria-live` on the feed, real buttons for tickets, and a reduced-motion mode that turns off all animation.
