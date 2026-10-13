# Campus Customs Operations Harness

Reference for the multi-agent operations team (Boss, Inventory, Accounting, Facilities, Customer Service).

- **Original data (read-only):** `data/campus_customs.db`
- **Working copy (agents update this):** `data/campus_customs_new.db`
- **Shop "today":** `desk.date_today` = **2026-08-31**
- **Model:** `gpt-6-luna` for every agent, through Portkey (`PORTKEY_API_KEY` in `.env`)
- **Mock project:** nothing leaves this machine. There are no real emails, calls, orders, or payments.

**Contents:** [Database tables](#database-tables) · [MCP tools](#all-mcp-tools) · [Agent team](#agent-team-backend) · [Backend routes](#backend-routes-backendmainpy) · [Dashboard](#dashboard-frontend) · [Audit trail](#audit-trail-outputaudit_trailjson) · [Problem 9 full run](#problem-9-full-run) · [Safety](#safety)

### How to run it

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt
cd backend; uvicorn main:app --reload --port 8000      # API at http://localhost:8000
cd frontend; npm install; npm run dev                  # dashboard at http://localhost:5173
```

The CLI alternatives: `python -m backend.reset_db`, `python -m backend.team run 101`, `python -m backend.approvals list`, and `python -m backend.approvals approve <id> --by "<name>"`.

---

## Database tables

### `desk`
| Field | Type | Notes |
|---|---|---|
| `date_today` | TEXT | The shop's current date (2026-08-31) |
| `notes` | TEXT | Free-form desk notes (currently empty) |

**Why it matters:** This is the shop's clock. Every agent uses `date_today` to decide whether something is overdue or coming due.

### `inventory`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT | Product code (primary key with `size`) |
| `name` | TEXT | Product name |
| `size` | TEXT | S / M / L / XL, or OS (one size) |
| `qty` | INTEGER | Units on hand |
| `location` | TEXT | Aisle in the shop |

**Why it matters:** Inventory checks stock by SKU and size here to spot shortfalls before an order is promised.

### `pricing`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT | Product code (primary key) |
| `unit_cost` | REAL | What the shop pays per unit |
| `list_price` | REAL | What the shop charges per unit |

**Why it matters:** Accounting uses cost and price to work out margins, so it can judge discount requests and value purchase orders.

### `vendors`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Vendor ID (primary key) |
| `name` | TEXT | Vendor name |
| `specialty` | TEXT | What the vendor supplies |
| `lead_days` | INTEGER | Days from order to delivery |

**Why it matters:** Inventory picks the right restock vendor by specialty. `lead_days` is the only source for delivery estimates.

### `leases`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Lease ID (primary key) |
| `space_name` | TEXT | Rented space |
| `landlord` | TEXT | Who is paid |
| `monthly_rent` | REAL | Rent amount |
| `next_due` | TEXT | Next rent due date |
| `notes` | TEXT | Lease notes |

**Why it matters:** Facilities tracks rent amounts and due dates here. After an approved rent payment, `next_due` must move forward.

### `cash_accounts`
| Field | Type | Notes |
|---|---|---|
| `name` | TEXT | Account name (primary key) |
| `balance` | REAL | Current cash balance |
| `date` | TEXT | Date of the balance |

**Why it matters:** This is the only money the shop has. The pay tool must refuse any payment that would push the balance below $0. Cash only goes out; no revenue is modeled.

### `payments`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Payment ID (primary key) |
| `kind` | TEXT | Payment type, e.g. invoice or rent |
| `ref_id` | INTEGER | ID of the invoice or lease being paid |
| `amount` | REAL | Amount paid |
| `account` | TEXT | Cash account debited |
| `paid_at` | TEXT | When it was paid |
| `approved_by` | TEXT | The human who approved it (required) |

**Why it matters:** This is the audit trail. Every payment needs a row here with a named human approver. It starts empty.

### `invoices`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Invoice ID (primary key) |
| `vendor_id` | INTEGER | Links to `vendors.id` |
| `amount` | REAL | Amount owed |
| `due_date` | TEXT | When payment is due |
| `status` | TEXT | e.g. `open` / `paid` |
| `description` | TEXT | What the invoice was for |

**Why it matters:** Accounting watches unpaid bills here. A vendor with an `open` invoice will not ship new product, so this table can block a restock.

### `tickets`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Ticket ID (primary key) |
| `type` | TEXT | e.g. `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT | Who raised the ticket |
| `subject` | TEXT | Short title |
| `sku`, `size`, `qty` | TEXT / TEXT / INTEGER | Product details, if any |
| `lease_id` | INTEGER | Links to `leases.id`, if any |
| `invoice_id` | INTEGER | Links to `invoices.id`, if any |
| `status` | TEXT | e.g. `open` |
| `notes` | TEXT | Request details |
| `created_at` | TEXT | Timestamp |

**Why it matters:** This is the work board. Boss reads every ticket and routes it. The link fields point agents to the inventory, lease, or invoice they need. After a run, `status` holds the boss's final call: `resolved`, `awaiting_approval`, `blocked`, or `needs_human`.

### `approvals` (board table, created by the MCP server)
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Approval request ID |
| `ticket_id` | INTEGER | Ticket the request belongs to |
| `kind` | TEXT | `invoice`, `rent`, or `purchase_order` |
| `ref_id` | INTEGER | Invoice id or lease id (null for POs) |
| `vendor_id`, `sku`, `size`, `qty` | | Purchase-order details |
| `payee`, `amount`, `account` | | Who gets paid, the full bill amount, and the cash account |
| `reason`, `requested_by` | TEXT | Why, and which agent prepared it (stamped by code) |
| `status` | TEXT | `pending` → `approved` / `rejected` → `paid` / `refused` |
| `decided_by`, `decided_at` | TEXT | The human who decided, and when |

**Why it matters:** This is the human-approval gate. Agents can only create `pending` rows. Only `decide_approval` (humans) can approve, and only approved rows can be paid.

### `board_drafts` (board table, created by the MCP server)
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Draft ID |
| `ticket_id` | INTEGER | Ticket it is posted on |
| `author` | TEXT | Agent, `system`, or `boss` (stamped by code) |
| `kind` | TEXT | `customer_message`, `restock_recommendation`, `purchase_order_draft`, `payment_note`, `rent_note`, `note` |
| `title`, `body` | TEXT | The draft |
| `status` | TEXT | Always `draft`. Nothing is ever sent |

**Why it matters:** Customer replies, notes, the boss's status summaries, and payment confirmations live here and stay on the board.

---

### `human_decisions` (board table, created by the MCP server)
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | Decision ID |
| `ticket_id` | INTEGER | Ticket the decision is for |
| `decision` | TEXT | `offer_discount`, `decline_discount`, or `wait_for_customer` |
| `discount_pct`, `unit_price`, `qty` | | The approved discount, the resulting price per unit, and the quantity |
| `note` | TEXT | The person's note to the team |
| `decided_by`, `created_at` | TEXT | Who decided, and when |

**Why it matters:** This is where a person answers a ticket the boss sent to a human (for example, which discount to give). Agents read it through `get_ticket` and `list_board` and must follow the latest decision. Only `record_human_decision` can write it.

---

## Starting data snapshot (after reset, as of 2026-08-31)

- **Cash:** checking = **$3,400.00**
- **Open invoice:** #501, Bulldog Print Co (vendor 1), **$840.00**, due 2026-08-28. **OVERDUE by 3 days.** For: "Rush reprint CC-TEE-WHITE S"
- **Lease:** #1 Chapel Street shop, Elm City Properties, **$2,400.00/mo**, next due **2026-09-02** (in 2 days)
- **Vendors:** 1 Bulldog Print Co (apparel reprint, 5 days) · 2 Elm City Gifts (mugs and small goods, 3 days) · 3 QuickShip CT (local courier, 1 day)
- **Zero-stock items:** CC-TEE-WHITE size S, CC-MUG-CREST size OS
- **Payments:** none yet

---

## Open tickets and how they link

### Ticket 101: `customer_order` from Tauhid Zaman ("Bulldog tee")
- **Wants:** 1 × CC-TEE-WHITE, size S
- **Links:** `inventory` (CC-TEE-WHITE / S), `pricing` (cost $8, price $28), `invoice_id` → #501, then `vendor_id` 1 → Bulldog Print Co
- **What the data shows:** Stock for size S is **0**, so it's a shortfall. The restock vendor for apparel is Bulldog Print Co (5-day lead time), but they have overdue open invoice #501 ($840). **They won't ship until #501 is paid**, and paying it needs human approval.
- **Agents involved:** Inventory (shortfall, vendor), Accounting (pay #501 with approval), Customer Service (draft an update to the customer)

### Ticket 102: `rent_notice` from Elm City Properties ("Rent due")
- **Wants:** rent payment
- **Links:** `lease_id` → lease #1 ($2,400, due 2026-09-02), then `cash_accounts`, then `payments`
- **What the data shows:** Rent is due in 2 days, not yet overdue. Paying it needs human approval. Afterward, add a `payments` row, lower the cash balance, and move `leases.next_due` forward one month.
- **Agents involved:** Facilities (lease), Accounting (cash check, prep payment), human (approve)

### Ticket 103: `price_override` from Yale AI Club ("Bulk hoodie discount")
- **Wants:** 20 × CC-HOOD-NAVY, size M, at a bulk discount
- **Links:** `inventory` (CC-HOOD-NAVY / M), `pricing` (cost $22, list $58), then `vendors` (Bulldog Print Co, which is blocked by #501)
- **What the data shows:** Only **8** size M on hand, so the order is **12 short**. List price gives $36 margin per unit (62%). Any discount must stay above the $22 cost. Restocking also depends on Bulldog Print Co, which is blocked by unpaid invoice #501.
- **Agents involved:** Inventory (shortfall, restock), Accounting (margin and discount floor), Boss (approve or decline the discount), Customer Service (draft a reply)

### Cross-ticket constraint: cash
Invoice #501 ($840) plus rent ($2,400) = **$3,240**, against $3,400 in cash. **Both can be paid, leaving $160.** Any restock purchase order on top of that would overdraw the account and must be refused or deferred.

---

## First three MCP tools (Problem 3)

These three tools read the working copy `data/campus_customs_new.db`. They return only values stored in the database, plus simple math on them. Every date comparison uses `desk.date_today` (2026-08-31). The full list of tools, including the ones added for the agent team, is in [All MCP tools](#all-mcp-tools) below.

### 1. `check_stock(sku, size, qty_needed=0)`
- **Tables read:** `inventory` (qty, location for the SKU and size), `pricing` (unit_cost, list_price)
- **Unlocks:** **Ticket 101** and **Ticket 103**
- **Why it's the right tool:**
  - **101:** Called as `check_stock("CC-TEE-WHITE", "S", 1)`, it shows Tauhid Zaman's size S Bulldog tee has 0 on hand and a shortfall of 1. That tells the team the order can't be filled from the shelf and has to wait for a restock, rather than being promised by mistake.
  - **103:** Called as `check_stock("CC-HOOD-NAVY", "M", 20)`, it shows only 8 size M hoodies on hand (a 12-unit shortfall for the Yale AI Club). In the same call it returns the $22 unit cost and $58 list price, so Accounting gets the $36 per-unit margin and the $22 price floor for the bulk discount without another lookup.

### 2. `check_vendor_status(vendor_id=None)`
- **Tables read:** `vendors` (name, specialty, lead_days), `invoices` (open invoices for that vendor), `desk` (date_today, to measure days overdue)
- **Unlocks:** **Ticket 101** (and the restock half of **Ticket 103**)
- **Why it's the right tool:**
  - **101:** Ticket 101 links to invoice #501, and `check_vendor_status(1)` reports that Bulldog Print Co, the apparel-reprint vendor for the tee, has `can_ship = false` because #501 ($840, due 2026-08-28) is still open and 3 days overdue. That shows the size S tee can't be reordered until Accounting gets #501 paid with human approval, and that the restock arrives about 5 days after it ships (`lead_days` = 5).
  - **103:** The same block stops the 12 missing size M hoodies from being reprinted, so the discount reply can't promise 20 units until #501 is cleared.

### 3. `check_rent_due(lease_id)`
- **Tables read:** `leases` (landlord, monthly_rent, next_due), `cash_accounts` (balance), `desk` (date_today)
- **Unlocks:** **Ticket 102**
- **Why it's the right tool:** Ticket 102 links to `lease_id = 1`, and `check_rent_due(1)` confirms the Chapel Street shop rent owed to Elm City Properties is $2,400, due 2026-09-02 (2 days from `desk.date_today`, not yet overdue), and that the $3,400 checking balance can cover it. That gives Facilities and Accounting exactly what they need to prepare a rent payment for human approval, without guessing the amount or date from the landlord's email.

---

## Shop rules (enforced by the harness)

1. `desk.date_today` is "today" for all overdue checks.
2. Vendor lead times come only from `vendors.lead_days`.
3. A vendor will not ship while it has an open unpaid invoice.
4. **Every payment requires human approval.** On payment, write a `payments` row (with `approved_by`), lower `cash_accounts.balance`, and update the source record (`invoices.status` → paid, or `leases.next_due` → next month).
5. The pay tool refuses any payment the cash can't cover. No negative balances.
6. Cash only goes out. No revenue is modeled.
7. Reset the working DB to the original values before a full ticket run.
8. Never email customers or contact real vendors. All drafts stay on the board.

---

## Agent team (`backend/`)

The team is five pydantic-ai agents, all running **gpt-6-luna** through Portkey. Prompts are in `backend/prompts/`: one file per agent, plus `team_rules.md` with the rules every agent shares. Any agent can hand a task to any other with the `delegate` tool. Each agent can only see the MCP tools for its role (`backend/mcp_tools.py`).

| Agent | Role | MCP tools it can call |
|---|---|---|
| **Boss** (`agents/boss.py`) | Reads and classifies each ticket and routes specific tasks with IDs. Checks that every finding traces to a tool call. Sets the final status (resolved / awaiting_approval / blocked / needs_human). Recommends payments, and their order when cash is short. Never approves or pays | `get_ticket`, `list_open_tickets`, `check_cash`, `list_board`, `list_approvals` |
| **Inventory** (`agents/inventory.py`) | Checks stock by SKU + size + qty and reports shortfalls and missing SKUs or sizes. Finds which vendor can restock and the arrival date (date_today + lead_days). Hands blocked vendors to accounting. Recommends, never orders | `get_ticket`, `check_stock`, `list_inventory`, `check_vendor_status`, `save_draft` |
| **Accounting** (`agents/accounting.py`) | Watches cash, invoices, and margins. Payment flow: verify the bill → check cash → request human approval → pay only after approval → books updated. Refuses when cash is short. Shows the margin impact of discounts and flags selling below cost | `get_ticket`, `check_cash`, `check_invoice`, `check_rent_due`, `check_discount`, `check_stock`, `check_vendor_status`, `request_payment_approval`, `list_approvals`, `get_approval`, `pay_approved`, `list_board`, `save_draft` |
| **Facilities** (`agents/facilities.py`) | Reports the lease amount, payee, and due date, labeled upcoming / due today / overdue against date_today. Always hands rent to accounting. Never pays, renegotiates, or contacts the landlord | `get_ticket`, `check_rent_due`, `save_draft` |
| **Customer Service** (`agents/customer_service.py`) | Drafts customer messages (thank → answer → honest about delays → next step) using only facts confirmed by inventory or the boss. Never shares internal information or promises unconfirmed dates, discounts, or stock. Drafts are never sent | `get_ticket`, `save_draft` (customer_message only) |

The orchestrator (`backend/team.py`) starts each ticket with the boss. It writes the boss's validated status to the board through `set_ticket_status`. Humans approve payments in the dashboard (`POST /approvals/{id}/approve`) or with `python -m backend.approvals`. Both call `decide_approval` over MCP, and approving through the API then runs `pay_approved`.

**All shop data goes through the MCP server. No part of the backend reads or writes `data/campus_customs_new.db` directly.** The only exception is `backend/reset_db.py`, which copies the original file over the working copy before a full run.

---

## All MCP tools

All 20 tools use `data/campus_customs_new.db`. `approvals`, `board_drafts`, and `human_decisions` are board tables that the server creates on first use.

| # | Tool | Tables | Reads / writes | Used by |
|---|---|---|---|---|
| 1 | `check_stock(sku, size, qty_needed)` | `inventory`, `pricing`, plus `approvals`, `payments`, `vendors` for incoming stock from paid POs | read | inventory, accounting |
| 2 | `check_vendor_status(vendor_id)` | `vendors`, `invoices`, `desk` | read | inventory, accounting |
| 3 | `check_rent_due(lease_id)` | `leases`, `cash_accounts`, `payments`, `desk` (includes rent payments on file and the due date they covered) | read | facilities, accounting |
| 4 | `get_ticket(ticket_id)` | `tickets`, `desk` | read | all agents, orchestrator |
| 5 | `list_open_tickets()` | `tickets`, `desk` | read | boss, orchestrator |
| 6 | `list_inventory(sku)` | `inventory` | read | inventory |
| 7 | `check_cash()` | `cash_accounts`, `invoices`, `vendors`, `leases`, `approvals`, `desk` | read | boss, accounting |
| 8 | `check_invoice(invoice_id)` | `invoices`, `vendors`, `payments`, `approvals`, `desk` | read | accounting |
| 9 | `check_discount(sku, qty, discount_pct or offered_unit_price)` | `pricing` | read | accounting |
| 10 | `request_payment_approval(...)` | reads `invoices`, `leases`, `vendors`, `inventory`, `pricing`, `cash_accounts`; writes `approvals` | write (pending request only) | accounting |
| 11 | `list_approvals(status, ticket_id)` | `approvals` | read | boss, accounting, human CLI |
| 12 | `get_approval(approval_id)` | `approvals` | read | accounting, orchestrator |
| 13 | `decide_approval(approval_id, approver, approve)` | `approvals` | write | **humans only** (no agent has it) |
| 14 | `pay_approved(approval_id)` | `approvals`, `payments`, `invoices` or `leases`, `cash_accounts`, `board_drafts` (payment note) | write | accounting or the approve route, only after human approval |
| 15 | `save_draft(...)` | reads `tickets`; writes `board_drafts` | write | inventory, accounting, facilities, customer service |
| 16 | `list_board(ticket_id)` | `tickets`, `board_drafts`, `approvals` | read | boss, accounting |
| 17 | `set_ticket_status(...)` | `tickets`, `board_drafts` | write | orchestrator only (from the boss's decision) |
| 18 | `list_tickets()` | `tickets`, `desk` | read | backend API (`GET /tickets`) |
| 19 | `discount_options(ticket_id, discount_pcts)` | `tickets`, `inventory`, `pricing` | read | boss, accounting, dashboard |
| 20 | `record_human_decision(ticket_id, decided_by, decision, discount_pct, note)` | reads `tickets`, `pricing`; writes `human_decisions`, `board_drafts` | write | **humans only** (dashboard); refuses agent names and below-cost discounts |

---

## Backend routes (`backend/main.py`)

Start from the `backend/` folder with `uvicorn main:app --reload --port 8000`. The API runs at http://localhost:8000 (interactive docs at http://localhost:8000/docs). Every route reaches shop data through the MCP server.

- `GET /`: health check, the model in use, and the list of routes.
- `GET /tickets`: all three tickets with their board status, plus `state` (open, or resolved once the team has finished a run and the boss has made the call) and whether the team is working on each right now.
- `GET /tickets/{ticket_id}`: one ticket with everything on its board (drafts and payment approvals).
- `GET /tickets/{ticket_id}/summary`: what each agent did on the ticket's latest run (their report, tools used, hand-offs) and the boss's decision, for the dashboard's debrief.
- `POST /tickets/{ticket_id}/run`: starts the agent team on that ticket in the background and returns a `run_id`. Add `?wait=true` to wait for the result. Only one run at a time.
- `GET /runs` and `GET /runs/{run_id}`: whether a run is running, finished, or failed, and the boss's final decision.
- `GET /events`: recent agent events from the audit trail, showing what each agent said and which tools it used. Filter with `?ticket_id=`, `?run_id=`, or `?limit=`, and poll with `?after=<next_after>` to get only new events for the board.
- `GET /approvals`: payment and purchase-order requests the agents prepared (pending by default; `?status=` to change).
- `POST /approvals/{approval_id}/approve` with body `{"approver": "<name>"}`: a human approves the request, then it is paid and the `payments`, `invoices`/`leases`, and `cash_accounts` tables are updated. This is the only route that can change cash, and it refuses agent names and short cash.
- `POST /approvals/{approval_id}/reject` with body `{"approver": "<name>"}`: a human rejects the request. No money moves.
- `GET /tickets/{ticket_id}/discount-options`: discount levels for the ticket's SKU and quantity, with price per unit, revenue, discount given, cost, profit, margin, and profit given up compared with list price. Add `?pcts=12&pcts=18` for custom levels.
- `POST /tickets/{ticket_id}/decision` with body `{"decided_by", "decision", "discount_pct", "note"}`: a human records a decision on the ticket (offer a discount, decline, or wait for the customer). Below-cost discounts and agent names are refused. No money moves, and the dashboard then re-runs the ticket.
- `GET /cash`: the current checking balance from `cash_accounts`, plus what is owed against it.
- `POST /reset`: resets `data/campus_customs_new.db` to the original values for a fresh run. Refused while a run is in progress. The audit trail is kept and the reset is added to it.

---

## Dashboard (`frontend/`)

React + Vite + TypeScript, in the Yale style from Homework 4. Start it with `npm run dev`, which opens http://localhost:5173. It calls only the backend at http://localhost:8000, which allows the 5173 origin through CORS. `?ticket=102` opens a specific ticket. Design reasons are in `output/design.md`.

| Area | What it shows | Routes it uses |
|---|---|---|
| Ticket board (left) | All three tickets, Open or Resolved, a "Resolved" stamp, and the boss's outcome badge | `GET /tickets` |
| Ticket focus + **Dispatch the team** | The selected ticket and a run button with a live timer (one run at a time) | `POST /tickets/{id}/run`, `GET /runs/{id}` |
| Holonet comms (dark panel) | Live feed: hand-offs between agents, tool calls with arguments, reports, and the boss's final call | `GET /events?after=` (polled every 1.2 s during a run) |
| Mission debrief | The boss's ruling, one card per agent (summary, tools, hand-offs), and the customer draft marked "not sent" | `GET /tickets/{id}/summary`, `GET /tickets/{id}` |
| Checking balance | The `cash_accounts` balance. It counts down after an approved payment, with a ledger line | `GET /cash` |
| Needs your signature | Pending payment and PO requests. Approving needs a typed name and a confirm step, and is locked during runs and when cash is short | `GET /approvals`, `POST /approvals/{id}/approve`, `/reject` |
| Decide the discount (price-override tickets) | A profitability table for each discount (price per unit, revenue, discount given, profit with bars, margin, profit given up), shown for the full order or the units in stock now, plus a custom % row. Offer, decline, or wait, with a note and signature; below-cost rows are disabled | `GET /tickets/{id}/discount-options`, `POST /tickets/{id}/decision`, then `POST /tickets/{id}/run` |
| Agent team | Darth Vader (boss), R2-D2 (inventory), Lando Calrissian (accounting), Chewbacca (facilities), C-3PO (customer service), each with a live status light | (from events) |
| Reset database | Fresh run (asks to confirm; the audit trail is kept) | `POST /reset` |

---

## Problem 9 full run

Run on 2026-10-12 against the working database, after `POST /reset`. Full detail is in `output/resolved_tickets.json`, the Actual and Cash tabs of `output/desk_tickets.html`, screenshots in `output/resolved_board.html`, and every step in `output/audit_trail.json`.

| Ticket | Final status | Human approvals | Cash change |
|---|---|---|---|
| 101 Bulldog tee | `resolved`: 1 tee incoming on a paid PO, expected 2026-09-05; customer draft saved | #1 invoice 501 $840 (Store manager); #3 PO 1 × CC-TEE-WHITE S $8 (Store Manager, in the dashboard) | −$848.00 |
| 102 Rent due | `resolved`: September 2 rent paid; next due 2026-10-02 | #2 rent lease 1 $2,400 (Store manager) | −$2,400.00 |
| 103 Bulk hoodies | `needs_human`: the club named no discount, which is a human decision; clarification draft saved | none | $0.00 |

**Checking:** $3,400.00 → $1,000.00 (rent) → $160.00 (invoice 501) → **$152.00** (PO). That matches `cash_accounts` in the working database.

**Two tool blind spots found and fixed during the run:**
- `check_rent_due` didn't show that rent had been paid, so ticket 102 was escalated by mistake. It now returns `rent_payments_on_file` and `last_paid_due_date`.
- `check_stock` didn't show units bought on a paid PO, so ticket 101 was escalated by mistake. It now returns `incoming_from_paid_purchase_orders`, `qty_incoming`, and `shortfall_after_incoming`.

`pay_approved` also posts a `payment_note` to the ticket's board.

---

## Audit trail (`output/audit_trail.json`)

Every agent loop step is appended as it happens. The file is one JSON array. New entries go in before the closing bracket, so earlier entries are never rewritten or wiped.

Each entry has these fields:
- `run_id`, `seq`, and a UTC timestamp `ts`
- `shop_date`, `ticket_id`, `agent`, and delegation `depth`
- `model`, `kind`, `name`, and `data`
- `budget`: the ticket's tool calls and delegations used so far

| `kind` | What is recorded |
|---|---|
| `run_start` / `run_end` | The ticket or payment being worked; the final status and budget used |
| `agent_start` | The task given to the agent, the model, its prompt files, and its allowed tools |
| `model_request` | What the model was sent that step: the task, tool results, validation retries |
| `model_response` | What the model decided: tool calls with arguments, text, finish reason, tokens |
| `tool_call` / `tool_result` | The exact MCP arguments sent (after the identity stamp) and the full result |
| `delegation` / `report` | Who handed what task to whom, and the report that came back |
| `agent_output` | The agent's validated final output and token use so far on the ticket |
| `limit` / `error` | A budget hit, a blocked tool, or a crash |
| `status` | The status written to the board |
| `human_decision` | Who approved or rejected which payment request, and when |

---

## Safety

This is a mock assignment. Everything runs locally against the SQLite file. No tool can email, call, or message anyone, and no tool places a real order. A purchase order is only an approval request and a board draft.

### Guardrails for agents that touch customers and real money
- **Humans approve every payment.** No agent has `decide_approval`, and it rejects agent names. `pay_approved` refuses anything a named human hasn't approved, and the approver's name is written to `payments.approved_by`.
- **The checks are in the tools, not just the prompts.** The tools refuse partial payments, negative balances, duplicate requests, and POs to vendors with unpaid invoices. Cash already promised to other pending approvals counts against what's available.
- **People make the judgment calls.** Discounts are decided by a named person on the dashboard (`record_human_decision`), never by an agent. Below-cost offers are refused by the tool, and agents must follow the latest decision exactly.
- **Least privilege.** Each agent sees only its role's tools. The guard blocks any other call even if an agent ignores its prompt.
- **No spoofing.** The code stamps who requested, wrote, or paid something and which ticket it belongs to. The model doesn't get to choose.
- **Evidence or nothing.** The boss's and specialists' answers are sent back if a finding cites a tool nobody called on the ticket, or an approval or draft id that wasn't created.
- **Customer messages are drafts.** Only customer service writes them, using confirmed facts only, and they are never sent. A real business would add a human review before anything goes out, and keep internal data (cash, invoices, margins, vendor problems) out of customer text.
- **Full audit trail.** Every step is kept append-only, so any payment or message can be traced back to the tool results behind it.
- **Reset before a full run** (`python -m backend.reset_db`), so every run starts from known data.
- **Secrets** come from `.env` (`PORTKEY_API_KEY`), which is git-ignored and never in source.

### Limits that keep token use in check
These are per ticket and shared by all agents.

| Limit | Value | When hit |
|---|---|---|
| MCP tool calls | 30 | Tools return "budget used up, escalate" |
| Delegations | 8 | `delegate` refuses and tells the agent to finish and escalate |
| Delegation depth | 3 | Same as delegations |
| Model requests | 60 | The run stops and the ticket is set to `needs_human` |
| Total tokens | 300,000 | The run stops and the ticket is set to `needs_human` |
| Output tokens per response | 6,000 | The response is capped |
| Validation retries per agent | 2 | The agent run fails and is escalated |

Other ways it saves tokens:
- Only one model (gpt-6-luna) is used.
- Tickets run one at a time.
- The shop date and remaining budget are put in each agent's context, so agents don't need to look them up.
- Agents are told not to repeat a tool call they already have the answer to.
