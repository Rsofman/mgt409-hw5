# Campus Customs Ops Desk

A multi-agent operations desk for the Campus Customs shop. Tickets (customer orders, rent notices, discount requests) land on a board, and a team of five AI agents works them while a human watches and approves every payment.

- **MCP server** (`mcp_server/server.py`): the only way to read or change the shop database (stock, vendors, cash, invoices, leases, approvals, drafts).
- **FastAPI backend** (`backend/`): runs the five agents (Boss, Inventory, Accounting, Facilities, Customer Service) on `gpt-6-luna` through Portkey, and exposes the board, approval, and reset routes.
- **React dashboard** (`frontend/`): the board where you watch agents work and approve or reject requests.

Nothing leaves the app: no real emails, orders, or payments. Customer messages are saved as drafts.

## 1. Set up Python

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Mac/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 2. Add your Portkey key

```powershell
copy .env.example .env               # Mac/Linux: cp .env.example .env
```

Open `.env` and fill in `PORTKEY_API_KEY=`. Never commit `.env`.

## 3. Start from clean data

`data/campus_customs.db` is the original shop data. `data/campus_customs_new.db` is the working copy the agents change. Copy the original over the working copy:

```powershell
copy data\campus_customs.db data\campus_customs_new.db    # Mac/Linux: cp data/campus_customs.db data/campus_customs_new.db
```

## 4. Start the MCP server (optional)

The backend launches the MCP server for you, so you only need this to test the tools on their own:

```powershell
python mcp_server/server.py
```

`.mcp.json` registers the server for MCP clients. It uses the Windows venv path `.venv/Scripts/python.exe`; on Mac/Linux change it to `.venv/bin/python`.

## 5. Start the FastAPI backend

With the venv active:

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

## 6. Start the React board

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

This opens http://localhost:5173.

## 7. Reset before a full three-ticket run

Before running all three tickets, reset the working database to the original values in any of these ways:

- Click **Reset database** on the dashboard.
- Send `POST http://localhost:8000/reset`.
- From the project root, run `python -m backend.reset_db`.

The audit trail is kept across resets.

## Output files (`output/`)

| File | What it is |
| --- | --- |
| `desk_tickets.html` | One tab per ticket with expected vs. actual, plus the Cash and Reflection tabs |
| `resolved_tickets.json` | Each ticket's final status, outcome, agent contributions, and human approvals |
| `resolved_board.html` | Screenshots of the React board for each resolved ticket |
| `audit_trail.json` | Log of every agent run, tool call, approval, and reset |
| `harness.md` | How the system works: tables, MCP tools, the five agents, API routes, dashboard, and safety rules |
| `design.md` | Design choices for the dashboard |
| `mcp_smoke.json` | Results of testing each MCP tool through the server |

All `.html` files open with a double click.
