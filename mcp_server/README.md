# Campus Customs MCP Server

This MCP server is the shared toolbox for the Campus Customs operations team. Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) gets shop facts by calling these tools instead of guessing. The server is built with [FastMCP](https://gofastmcp.com).

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy that agents update.
- **Never touches:** `data/campus_customs.db`, the original, which is used to reset the working copy.
- **Override:** set `CAMPUS_DB_PATH` to point at a different file.
- **Today's date:** every date comparison uses `desk.date_today`, never the computer's clock.
- **No invented data:** tools return only values stored in the database, plus simple math on them (shortfall, margin, days overdue, arrival date).

## Tools

All 20 tools are listed below, in the order they are registered in `server.py`. `approvals`, `board_drafts`, and `human_decisions` are board tables the server creates automatically in the working database.

| # | Tool | Tables (reads / writes) | What it does |
|---|---|---|---|
| 1 | `check_stock(sku, size, qty_needed=0)` | reads `inventory`, `pricing`, `approvals`, `payments`, `vendors` | Units on hand for a SKU and size, the shortfall for a requested quantity, units incoming from paid purchase orders (with expected arrival), and the unit cost, list price, and margin |
| 2 | `check_vendor_status(vendor_id=None)` | reads `vendors`, `invoices`, `desk` | Whether a vendor can ship (blocked if it has an open invoice), its lead time and earliest arrival date, and how overdue each unpaid invoice is |
| 3 | `check_rent_due(lease_id)` | reads `leases`, `cash_accounts`, `payments`, `desk` | A lease's rent, payee, and next due date, days until due or overdue, rent payments on file and the due date they covered, and which cash accounts can cover it |
| 4 | `get_ticket(ticket_id)` | reads `tickets`, `desk` | One ticket and its IDs, plus the shop date |
| 5 | `list_open_tickets()` | reads `tickets`, `desk` | Every unresolved ticket, for setting priorities |
| 6 | `check_cash()` | reads `cash_accounts`, `invoices`, `vendors`, `leases`, `approvals`, `desk` | Cash against open invoices, rent due within 30 days, and pending approvals; flags a shortfall. Never counts revenue |
| 7 | `check_invoice(invoice_id)` | reads `invoices`, `vendors`, `payments`, `approvals`, `desk` | Verifies a bill before payment |
| 8 | `check_discount(sku, qty, discount_pct or offered_unit_price)` | reads `pricing` | Margin impact of a discount; flags selling below cost |
| 9 | `request_payment_approval(...)` | reads `invoices`, `leases`, `vendors`, `inventory`, `pricing`, `cash_accounts`; writes `approvals` | Creates a **pending** request for a human. Refuses partial amounts, blocked vendors, duplicates, and anything cash can't cover |
| 10 | `pay_approved(approval_id)` | writes `payments`, `invoices` or `leases`, `cash_accounts`, `approvals`, `board_drafts` | Pays **only** a human-approved request; refuses if cash is short (no negative balances) |
| 11 | `save_draft(...)` | reads `tickets`; writes `board_drafts` | Saves customer messages and notes to the board as drafts. Nothing is ever sent |
| 12 | `list_board(ticket_id)` | reads `tickets`, `board_drafts`, `approvals` | Everything on one ticket's board |
| 13 | `set_ticket_status(...)` | writes `tickets`, `board_drafts` | Final status: resolved, awaiting_approval, blocked, needs_human. Only the orchestrator calls it |
| 14 | `list_inventory(sku=None)` | reads `inventory` | Every size of a SKU (or every item) with units on hand, for in-stock alternatives |
| 15 | `list_approvals(status=None, ticket_id=None)` | reads `approvals` | Payment requests, filtered by status or ticket |
| 16 | `get_approval(approval_id)` | reads `approvals` | One payment request and who decided it |
| 17 | `decide_approval(approval_id, approver, approve)` | writes `approvals` | **Humans only.** Records an approve/reject decision. Rejects agent names, and no agent is given this tool |
| 18 | `list_tickets()` | reads `tickets`, `desk` | Every ticket on the board, resolved or not, for the dashboard |
| 19 | `discount_options(ticket_id, discount_pcts=None)` | reads `tickets`, `inventory`, `pricing` | For each discount level: price per unit, revenue, discount given, cost, profit, margin, profit given up, and a below-cost flag, plus stock on hand |
| 20 | `record_human_decision(ticket_id, decided_by, decision, discount_pct=None, note="")` | reads `tickets`, `pricing`; writes `human_decisions`, `board_drafts` | **Humans only.** Records offer_discount / decline_discount / wait_for_customer. Refuses agent names and below-cost discounts. No agent is given this tool |

Agents only see the tools for their role (`backend/mcp_tools.py`). Humans approve payments with `python -m backend.approvals`, which calls `decide_approval` over MCP. Nothing in this mock contacts anyone or places a real order.

## Run

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python mcp_server/server.py
```

## Connect to a coding assistant

`.mcp.json` in the project folder registers the server under the name `campus-customs`, using stdio. Claude Code reads this file when it is opened in the project folder and lists the server under `/mcp`.

## Testing

All three tools were called through the `campus-customs` MCP server from Claude Code, using the prompts below. Each output was checked against `data/campus_customs_new.db` (shop date `desk.date_today` = 2026-08-31). All 6 tests passed. The full JSON outputs are in `output/mcp_smoke.json`.

| # | Prompt | Tool | Result | Matches DB |
|---|---|---|---|---|
| 1 | Through the campus-customs MCP server, call check_stock for CC-TEE-WHITE size S, quantity 1 | `check_stock` | Classic Bulldog Tee S: 0 on hand (Aisle B), shortfall 1, not in stock; cost $8, price $28, margin $20 | Yes (`inventory`, `pricing`) |
| 2 | Through the campus-customs MCP server, call check_stock for CC-HOOD-NAVY size M, quantity 20 | `check_stock` | Basic Hoodie Big Yale M: 8 on hand (Aisle A), shortfall 12, not in stock; cost $22, price $58, margin $36 | Yes (`inventory`, `pricing`) |
| 3 | Through the campus-customs MCP server, call check_vendor_status for vendor 1 | `check_vendor_status` | Bulldog Print Co (apparel reprint, 5-day lead): cannot ship; invoice #501 $840 due 2026-08-28, 3 days overdue; earliest arrival 2026-09-05 | Yes (`vendors`, `invoices`, `desk`) |
| 4 | Through the campus-customs MCP server, call check_vendor_status with no vendor ID | `check_vendor_status` | Lists all 3 vendors: Bulldog Print Co blocked ($840 open); Elm City Gifts can ship, arrival 2026-09-03; QuickShip CT can ship, arrival 2026-09-01 | Yes (`vendors`, `invoices`, `desk`) |
| 5 | Through the campus-customs MCP server, call check_rent_due for lease 1 | `check_rent_due` | Chapel Street shop (Elm City Properties): $2,400 due 2026-09-02, 2 days away, not overdue; checking $3,400 covers it; payment needs human approval | Yes (`leases`, `cash_accounts`, `desk`) |
| 6 | Through the campus-customs MCP server, call check_stock for CC-HOOD-NAVY size XXL | `check_stock` | Not found: no inventory row for that size; sizes on file are S, M, L, XL (no quantity invented) | Yes (no XXL row in `inventory`) |
