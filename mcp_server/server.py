"""Campus Customs MCP server.

Exposes shop-data tools to every agent on the operations team. All tools use
the working copy data/campus_customs_new.db and return only values that exist
in the database (plus simple date/arithmetic derived from them).

Write tools only touch the board (approvals, drafts, ticket status) except
pay_approved, which moves cash and only runs on a human-approved request.
"""

import calendar
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(
    os.getenv(
        "CAMPUS_DB_PATH",
        Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db",
    )
)

mcp = FastMCP("campus-customs")


TICKET_STATUSES = ("resolved", "awaiting_approval", "blocked", "needs_human")
HUMAN_DECISIONS = ("offer_discount", "decline_discount", "wait_for_customer")
PAYMENT_KINDS = ("invoice", "rent", "purchase_order")
DRAFT_KINDS = (
    "customer_message",
    "restock_recommendation",
    "purchase_order_draft",
    "payment_note",
    "rent_note",
    "note",
)

# Board tables the agents write to. They are not in the original database, so
# they are created on first use (and again after every reset).
_BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    ref_id INTEGER,
    vendor_id INTEGER,
    sku TEXT,
    size TEXT,
    qty INTEGER,
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS human_decisions (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    decision TEXT NOT NULL,
    discount_pct REAL,
    unit_price REAL,
    qty INTEGER,
    note TEXT,
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS board_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Open the working DB, commit on success, and always close the file handle."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.executescript(_BOARD_SCHEMA)
            yield conn
    finally:
        conn.close()


def _now() -> str:
    """Wall-clock timestamp for board audit rows only, never for business dates."""
    return datetime.now().isoformat(timespec="seconds")


def _add_month(d: date) -> date:
    """Same day next month, clamped to the month's last day."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _sub_month(d: date) -> date:
    """Same day last month, clamped to the month's last day."""
    year, month = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _committed(conn: sqlite3.Connection, account: str) -> float:
    """Cash already promised to approvals that are pending or approved but not yet paid."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM approvals "
        "WHERE account = ? AND status IN ('pending', 'approved')",
        (account,),
    ).fetchone()
    return round(row["total"], 2)


def _today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' always comes from desk.date_today, never the system clock."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def check_stock(sku: str, size: str, qty_needed: int = 0) -> dict:
    """Check units on hand for one SKU and size, plus its unit cost and list price.

    Use this before promising any customer order or bulk request. Pass
    qty_needed to get the shortfall (how many units are missing).
    Reads: inventory, pricing.
    """
    with _connect() as conn:
        item = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if item is None:
            sizes = [
                r["size"]
                for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku,))
            ]
            return {
                "found": False,
                "sku": sku,
                "size": size,
                "error": "No inventory row for this SKU and size.",
                "sizes_on_file_for_sku": sizes,
            }
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        # Units bought with a human-approved, paid purchase order are on their way.
        incoming = [
            {
                "approval_id": r["approval_id"],
                "qty": r["qty"],
                "vendor": r["vendor"],
                "paid_at": r["paid_at"],
                "expected_arrival": (
                    date.fromisoformat(r["paid_at"]) + timedelta(days=r["lead_days"])
                ).isoformat(),
            }
            for r in conn.execute(
                "SELECT a.id AS approval_id, a.qty, v.name AS vendor, v.lead_days, p.paid_at "
                "FROM approvals a JOIN vendors v ON v.id = a.vendor_id "
                "JOIN payments p ON p.kind = 'purchase_order' AND p.ref_id = a.id "
                "WHERE a.kind = 'purchase_order' AND a.status = 'paid' AND a.sku = ? AND a.size = ?",
                (sku, size),
            )
        ]

    on_hand = item["qty"]
    qty_incoming = sum(i["qty"] for i in incoming)
    result = {
        "found": True,
        "sku": item["sku"],
        "name": item["name"],
        "size": item["size"],
        "qty_on_hand": on_hand,
        "location": item["location"],
        "qty_needed": qty_needed,
        "shortfall": max(qty_needed - on_hand, 0),
        "in_stock_for_request": on_hand >= qty_needed if qty_needed else on_hand > 0,
        "incoming_from_paid_purchase_orders": incoming,
        "qty_incoming": qty_incoming,
        "shortfall_after_incoming": max(qty_needed - on_hand - qty_incoming, 0),
        "unit_cost": None,
        "list_price": None,
        "unit_margin": None,
    }
    if price is not None:
        result["unit_cost"] = price["unit_cost"]
        result["list_price"] = price["list_price"]
        result["unit_margin"] = round(price["list_price"] - price["unit_cost"], 2)
    return result


def check_vendor_status(vendor_id: int | None = None) -> dict:
    """Show whether each vendor can ship right now, its lead time, and any unpaid invoices.

    A vendor will not ship new product while it has an open (unpaid) invoice.
    Days overdue are measured against desk.date_today. Omit vendor_id to list
    every vendor so the right one can be matched by specialty.
    Reads: vendors, invoices, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        if vendor_id is None:
            vendors = conn.execute(
                "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"
            ).fetchall()
        else:
            vendors = conn.execute(
                "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
                (vendor_id,),
            ).fetchall()
            if not vendors:
                return {"found": False, "vendor_id": vendor_id, "error": "No vendor with this id."}

        results = []
        for v in vendors:
            open_invoices = []
            for inv in conn.execute(
                "SELECT id, amount, due_date, status, description FROM invoices "
                "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
                (v["id"],),
            ):
                days_past_due = (today - date.fromisoformat(inv["due_date"])).days
                open_invoices.append(
                    {
                        "invoice_id": inv["id"],
                        "amount": inv["amount"],
                        "due_date": inv["due_date"],
                        "status": inv["status"],
                        "description": inv["description"],
                        "overdue": days_past_due > 0,
                        "days_overdue": max(days_past_due, 0),
                    }
                )
            can_ship = not open_invoices
            results.append(
                {
                    "vendor_id": v["id"],
                    "name": v["name"],
                    "specialty": v["specialty"],
                    "lead_days": v["lead_days"],
                    "can_ship": can_ship,
                    "blocked_reason": None
                    if can_ship
                    else "Vendor has open unpaid invoice(s); will not ship until paid.",
                    "open_invoices": open_invoices,
                    "open_balance": round(sum(i["amount"] for i in open_invoices), 2),
                    "earliest_arrival_if_ordered_today": (
                        today + timedelta(days=v["lead_days"])
                    ).isoformat(),
                }
            )

    return {"date_today": today.isoformat(), "vendors": results}


def check_rent_due(lease_id: int) -> dict:
    """Show a lease's rent amount and due date, days until due, and whether cash covers it.

    Days until due are measured against desk.date_today. This tool only reads;
    paying rent requires a separate, human-approved payment.
    Reads: leases, cash_accounts, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"found": False, "lease_id": lease_id, "error": "No lease with this id."}
        accounts = [
            {"name": a["name"], "balance": a["balance"], "as_of": a["date"]}
            for a in conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name")
        ]
        paid = [
            dict(p)
            for p in conn.execute(
                "SELECT id AS payment_id, amount, paid_at, approved_by FROM payments "
                "WHERE kind = 'rent' AND ref_id = ? ORDER BY id",
                (lease_id,),
            )
        ]

    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    rent = lease["monthly_rent"]
    return {
        "found": True,
        "date_today": today.isoformat(),
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": rent,
        "next_due": lease["next_due"],
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
        "notes": lease["notes"],
        "cash_accounts": accounts,
        "accounts_that_can_cover_rent": [a["name"] for a in accounts if a["balance"] >= rent],
        "rent_payments_on_file": paid,
        # Each paid month moves next_due ahead one month, so the latest payment
        # covered the due date one month before the current next_due.
        "last_paid_due_date": (
            _sub_month(date.fromisoformat(lease["next_due"])).isoformat() if paid else None
        ),
        "requires_human_approval_to_pay": True,
    }


def get_ticket(ticket_id: int) -> dict:
    """Read one ticket from the board, plus the shop's date (desk.date_today).

    Start every ticket here. The ticket carries the IDs (sku, size, qty,
    lease_id, invoice_id) that the other tools need.
    Reads: tickets, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        decisions = [
            dict(d)
            for d in conn.execute(
                "SELECT * FROM human_decisions WHERE ticket_id = ? ORDER BY id", (ticket_id,)
            )
        ]
    if ticket is None:
        return {"found": False, "ticket_id": ticket_id, "error": "No ticket with this id."}
    return {
        "found": True,
        "date_today": today.isoformat(),
        "ticket": dict(ticket),
        # Decisions a person made on this ticket (e.g. a discount). The latest one wins.
        "human_decisions": decisions,
    }


def list_open_tickets() -> dict:
    """List every ticket that is not resolved yet, so work can be prioritized across the board.

    Reads: tickets, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        tickets = [
            dict(t)
            for t in conn.execute(
                "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status "
                "FROM tickets WHERE status != 'resolved' ORDER BY id"
            )
        ]
    return {"date_today": today.isoformat(), "tickets": tickets}


def check_cash() -> dict:
    """Show cash on hand against everything the shop owes: open invoices, rent due within
    30 days, and approvals already pending or approved.

    No revenue is modeled, so incoming money is never counted. If cash cannot
    cover every obligation, the shortfall is reported so the boss can set priorities.
    Reads: cash_accounts, invoices, vendors, leases, approvals, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        accounts = [
            {"name": a["name"], "balance": a["balance"], "as_of": a["date"]}
            for a in conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name")
        ]
        invoices = [
            {
                "invoice_id": i["id"],
                "vendor_id": i["vendor_id"],
                "vendor": i["vendor"],
                "amount": i["amount"],
                "due_date": i["due_date"],
                "days_overdue": max((today - date.fromisoformat(i["due_date"])).days, 0),
                "description": i["description"],
            }
            for i in conn.execute(
                "SELECT i.id, i.vendor_id, v.name AS vendor, i.amount, i.due_date, i.description "
                "FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                "WHERE i.status = 'open' ORDER BY i.due_date"
            )
        ]
        rent = []
        for lease in conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due FROM leases ORDER BY next_due"
        ):
            days = (date.fromisoformat(lease["next_due"]) - today).days
            if days <= 30:
                rent.append(
                    {
                        "lease_id": lease["id"],
                        "space_name": lease["space_name"],
                        "landlord": lease["landlord"],
                        "amount": lease["monthly_rent"],
                        "next_due": lease["next_due"],
                        "days_until_due": days,
                    }
                )
        approvals = [
            dict(a)
            for a in conn.execute(
                "SELECT id AS approval_id, ticket_id, kind, ref_id, payee, amount, account, status "
                "FROM approvals WHERE status IN ('pending', 'approved') ORDER BY id"
            )
        ]

    total_cash = round(sum(a["balance"] for a in accounts), 2)
    # A pending approval may be for one of the open bills above; count each bill once.
    approved_refs = {(a["kind"], a["ref_id"]) for a in approvals}
    obligations = (
        sum(i["amount"] for i in invoices if ("invoice", i["invoice_id"]) not in approved_refs)
        + sum(r["amount"] for r in rent if ("rent", r["lease_id"]) not in approved_refs)
        + sum(a["amount"] for a in approvals)
    )
    obligations = round(obligations, 2)
    return {
        "date_today": today.isoformat(),
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "open_invoices": invoices,
        "rent_due_within_30_days": rent,
        "approvals_pending_or_approved": approvals,
        "total_obligations": obligations,
        "can_cover_all": total_cash >= obligations,
        "shortfall": round(max(obligations - total_cash, 0), 2),
        "note": "No revenue is modeled; incoming money is never counted.",
    }


def check_invoice(invoice_id: int) -> dict:
    """Verify one vendor bill before paying it: amount, vendor, due date, status, days overdue,
    and any payments or approvals already on file for it.

    Reads: invoices, vendors, payments, approvals, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        inv = conn.execute(
            "SELECT i.*, v.name AS vendor, v.specialty FROM invoices i "
            "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (invoice_id,),
        ).fetchone()
        if inv is None:
            return {"found": False, "invoice_id": invoice_id, "error": "No invoice with this id."}
        payments = [
            dict(p)
            for p in conn.execute(
                "SELECT * FROM payments WHERE kind = 'invoice' AND ref_id = ?", (invoice_id,)
            )
        ]
        approvals = [
            dict(a)
            for a in conn.execute(
                "SELECT id AS approval_id, status, amount, requested_by, decided_by FROM approvals "
                "WHERE kind = 'invoice' AND ref_id = ?",
                (invoice_id,),
            )
        ]
    days_past_due = (today - date.fromisoformat(inv["due_date"])).days
    return {
        "found": True,
        "date_today": today.isoformat(),
        "invoice_id": inv["id"],
        "vendor_id": inv["vendor_id"],
        "vendor": inv["vendor"],
        "vendor_specialty": inv["specialty"],
        "amount": inv["amount"],
        "due_date": inv["due_date"],
        "status": inv["status"],
        "description": inv["description"],
        "overdue": inv["status"] == "open" and days_past_due > 0,
        "days_overdue": max(days_past_due, 0) if inv["status"] == "open" else 0,
        "payments_on_file": payments,
        "approvals_on_file": approvals,
    }


def check_discount(
    sku: str,
    qty: int,
    discount_pct: float | None = None,
    offered_unit_price: float | None = None,
) -> dict:
    """Show the margin impact of a discount or offered price on qty units of a SKU, and flag
    any price below unit cost.

    Give either discount_pct (e.g. 15 for 15% off list) or offered_unit_price.
    This only calculates; it never grants a discount.
    Reads: pricing.
    """
    with _connect() as conn:
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
    if price is None:
        return {"found": False, "sku": sku, "error": "No pricing row for this SKU."}
    if qty <= 0:
        return {"found": True, "sku": sku, "error": "qty must be greater than 0."}

    cost, list_price = price["unit_cost"], price["list_price"]
    if offered_unit_price is not None:
        unit_price = offered_unit_price
    elif discount_pct is not None:
        unit_price = list_price * (1 - discount_pct / 100)
    else:
        unit_price = list_price
    unit_price = round(unit_price, 2)

    list_margin = round((list_price - cost) * qty, 2)
    new_margin = round((unit_price - cost) * qty, 2)
    return {
        "found": True,
        "sku": sku,
        "qty": qty,
        "unit_cost": cost,
        "list_price": list_price,
        "discount_pct": round((1 - unit_price / list_price) * 100, 2),
        "unit_price": unit_price,
        "unit_margin": round(unit_price - cost, 2),
        "margin_pct": round((unit_price - cost) / unit_price * 100, 2) if unit_price else None,
        "total_revenue": round(unit_price * qty, 2),
        "total_margin_at_list": list_margin,
        "total_margin_at_offer": new_margin,
        "margin_given_up": round(list_margin - new_margin, 2),
        "below_cost": unit_price < cost,
        "break_even_discount_pct": round((1 - cost / list_price) * 100, 2),
    }


def request_payment_approval(
    ticket_id: int,
    kind: str,
    amount: float,
    reason: str,
    requested_by: str,
    ref_id: int | None = None,
    account: str = "checking",
    vendor_id: int | None = None,
    sku: str | None = None,
    size: str | None = None,
    qty: int | None = None,
) -> dict:
    """Ask a human to approve a payment. This never moves money.

    kind is 'invoice' (ref_id = invoice id), 'rent' (ref_id = lease id), or
    'purchase_order' (vendor_id, sku, size, qty; amount = unit_cost x qty).
    The bill is verified first and the amount must match it in full, so
    partial payments are refused. The request is refused if the account cannot
    cover it after other pending or approved payments.
    Reads: invoices, leases, vendors, inventory, pricing, cash_accounts, approvals.
    Writes: approvals (status 'pending').
    """
    if kind not in PAYMENT_KINDS:
        return {"created": False, "error": f"kind must be one of {PAYMENT_KINDS}."}

    with _connect() as conn:
        today = _today(conn)

        if kind == "invoice":
            inv = conn.execute(
                "SELECT i.*, v.name AS vendor FROM invoices i "
                "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ref_id,),
            ).fetchone()
            if inv is None:
                return {"created": False, "error": f"No invoice with id {ref_id}."}
            if inv["status"] != "open":
                return {"created": False, "error": f"Invoice {ref_id} is '{inv['status']}', not open."}
            bill_amount, payee, vendor_id = inv["amount"], inv["vendor"], inv["vendor_id"]
        elif kind == "rent":
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return {"created": False, "error": f"No lease with id {ref_id}."}
            bill_amount, payee = lease["monthly_rent"], lease["landlord"]
        else:
            vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
            if vendor is None:
                return {"created": False, "error": f"No vendor with id {vendor_id}."}
            item = conn.execute(
                "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)
            ).fetchone()
            price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
            if item is None or price is None:
                return {"created": False, "error": f"No inventory/pricing for {sku} size {size}."}
            if not qty or qty <= 0:
                return {"created": False, "error": "Purchase orders need qty greater than 0."}
            blocking = conn.execute(
                "SELECT id, amount FROM invoices WHERE vendor_id = ? AND status = 'open'",
                (vendor_id,),
            ).fetchall()
            if blocking:
                return {
                    "created": False,
                    "error": f"{vendor['name']} has open invoice(s) "
                    f"{[b['id'] for b in blocking]} and will not ship. Pay those first.",
                }
            bill_amount, payee, ref_id = round(price["unit_cost"] * qty, 2), vendor["name"], None

        if round(amount, 2) != round(bill_amount, 2):
            return {
                "created": False,
                "error": f"Amount {amount} does not match the bill ({bill_amount}). "
                "Only full payments are allowed.",
                "bill_amount": bill_amount,
            }

        duplicate = conn.execute(
            "SELECT id, status FROM approvals WHERE kind = ? AND ref_id IS ? "
            "AND COALESCE(sku, '') = COALESCE(?, '') AND status IN ('pending', 'approved')",
            (kind, ref_id, sku if kind == "purchase_order" else None),
        ).fetchone()
        if duplicate is not None:
            return {
                "created": False,
                "error": f"Approval {duplicate['id']} for this bill is already {duplicate['status']}.",
                "approval_id": duplicate["id"],
            }

        acct = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        if acct is None:
            return {"created": False, "error": f"No cash account named '{account}'."}
        committed = _committed(conn, account)
        available = round(acct["balance"] - committed, 2)
        if bill_amount > available:
            return {
                "created": False,
                "refused": True,
                "error": "Not enough cash. Request refused; no partial payments.",
                "amount": bill_amount,
                "balance": acct["balance"],
                "already_committed_to_other_approvals": committed,
                "available": available,
            }

        cur = conn.execute(
            "INSERT INTO approvals (ticket_id, kind, ref_id, vendor_id, sku, size, qty, payee, "
            "amount, account, reason, requested_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (
                ticket_id, kind, ref_id, vendor_id, sku, size, qty, payee,
                bill_amount, account, reason, requested_by, _now(),
            ),
        )

    return {
        "created": True,
        "approval_id": cur.lastrowid,
        "status": "pending",
        "kind": kind,
        "ref_id": ref_id,
        "payee": payee,
        "amount": bill_amount,
        "account": account,
        "balance": acct["balance"],
        "available_after_this_request": round(available - bill_amount, 2),
        "date_today": today.isoformat(),
        "message": "Waiting for human approval. Do not pay until a human approves it.",
    }


def pay_approved(approval_id: int, paid_by: str) -> dict:
    """Pay a request ONLY after a human has approved it, then update the books.

    Refuses if the request is not approved, the bill is no longer open, or cash
    is short (no negative balances, no partial payments). On success it writes a
    payments row, marks the invoice paid or moves the lease's next_due ahead one
    month, and lowers the cash balance.
    Reads/writes: approvals, payments, invoices, leases, cash_accounts.
    """
    with _connect() as conn:
        today = _today(conn)
        appr = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if appr is None:
            return {"paid": False, "error": f"No approval with id {approval_id}."}
        if appr["status"] != "approved" or not appr["decided_by"]:
            return {
                "paid": False,
                "error": f"Approval {approval_id} is '{appr['status']}'. "
                "Only human-approved requests can be paid.",
            }

        if appr["kind"] == "invoice":
            inv = conn.execute(
                "SELECT status, amount FROM invoices WHERE id = ?", (appr["ref_id"],)
            ).fetchone()
            if inv is None or inv["status"] != "open":
                return {"paid": False, "error": f"Invoice {appr['ref_id']} is not open."}

        acct = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (appr["account"],)
        ).fetchone()
        if acct is None or acct["balance"] < appr["amount"]:
            conn.execute("UPDATE approvals SET status = 'refused' WHERE id = ?", (approval_id,))
            return {
                "paid": False,
                "refused": True,
                "error": "Not enough cash. Payment refused; balances never go negative.",
                "amount": appr["amount"],
                "balance": None if acct is None else acct["balance"],
            }

        new_balance = round(acct["balance"] - appr["amount"], 2)
        ref_id = appr["ref_id"] if appr["kind"] != "purchase_order" else approval_id
        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (appr["kind"], ref_id, appr["amount"], appr["account"], today.isoformat(), appr["decided_by"]),
        )
        updates = {"payments": f"row {pay.lastrowid} added"}
        if appr["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (appr["ref_id"],))
            updates["invoices"] = f"invoice {appr['ref_id']} status -> paid"
        elif appr["kind"] == "rent":
            lease = conn.execute(
                "SELECT next_due FROM leases WHERE id = ?", (appr["ref_id"],)
            ).fetchone()
            next_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, appr["ref_id"]))
            updates["leases"] = f"lease {appr['ref_id']} next_due {lease['next_due']} -> {next_due}"
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today.isoformat(), appr["account"]),
        )
        updates["cash_accounts"] = f"{appr['account']} {acct['balance']} -> {new_balance}"
        conn.execute("UPDATE approvals SET status = 'paid' WHERE id = ?", (approval_id,))
        updates["approvals"] = f"approval {approval_id} status -> paid"
        # Post the payment to the ticket's board so later runs see it was settled.
        conn.execute(
            "INSERT INTO board_drafts (ticket_id, author, kind, title, body, status, created_at) "
            "VALUES (?, 'system', 'payment_note', ?, ?, 'draft', ?)",
            (
                appr["ticket_id"],
                f"Paid: approval {approval_id}",
                f"{appr['kind']} payment of ${appr['amount']:.2f} to {appr['payee']} executed on "
                f"{today.isoformat()} after human approval by {appr['decided_by']}. "
                + "; ".join(f"{k}: {v}" for k, v in updates.items()),
                _now(),
            ),
        )

    return {
        "paid": True,
        "approval_id": approval_id,
        "payment_id": pay.lastrowid,
        "kind": appr["kind"],
        "payee": appr["payee"],
        "amount": appr["amount"],
        "approved_by": appr["decided_by"],
        "paid_by": paid_by,
        "paid_at": today.isoformat(),
        "tables_updated": updates,
    }


def save_draft(ticket_id: int, author: str, kind: str, title: str, body: str) -> dict:
    """Save a draft to the ticket's board. Drafts are never sent to customers, vendors, or landlords.

    kind is one of: customer_message, restock_recommendation, purchase_order_draft,
    payment_note, rent_note, note.
    Writes: board_drafts (status 'draft').
    """
    if kind not in DRAFT_KINDS:
        return {"saved": False, "error": f"kind must be one of {DRAFT_KINDS}."}
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"saved": False, "error": f"No ticket with id {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO board_drafts (ticket_id, author, kind, title, body, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'draft', ?)",
            (ticket_id, author, kind, title, body, _now()),
        )
    return {
        "saved": True,
        "draft_id": cur.lastrowid,
        "ticket_id": ticket_id,
        "kind": kind,
        "status": "draft",
        "sent": False,
    }


def list_board(ticket_id: int) -> dict:
    """Show everything on a ticket's board: the ticket, saved drafts, and payment approvals.

    Reads: tickets, board_drafts, approvals.
    """
    with _connect() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"found": False, "ticket_id": ticket_id, "error": "No ticket with this id."}
        drafts = [
            dict(d)
            for d in conn.execute(
                "SELECT * FROM board_drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,)
            )
        ]
        approvals = [
            dict(a)
            for a in conn.execute(
                "SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,)
            )
        ]
        decisions = [
            dict(d)
            for d in conn.execute(
                "SELECT * FROM human_decisions WHERE ticket_id = ? ORDER BY id", (ticket_id,)
            )
        ]
    return {
        "found": True,
        "ticket": dict(ticket),
        "drafts": drafts,
        "approvals": approvals,
        "human_decisions": decisions,
    }


def set_ticket_status(ticket_id: int, status: str, summary: str, set_by: str) -> dict:
    """Set a ticket's final status and post the decision summary to its board.

    status is one of: resolved, awaiting_approval, blocked, needs_human.
    Writes: tickets.status, board_drafts (kind 'note').
    """
    if status not in TICKET_STATUSES:
        return {"updated": False, "error": f"status must be one of {TICKET_STATUSES}."}
    with _connect() as conn:
        row = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"updated": False, "error": f"No ticket with id {ticket_id}."}
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO board_drafts (ticket_id, author, kind, title, body, status, created_at) "
            "VALUES (?, ?, 'note', ?, ?, 'draft', ?)",
            (ticket_id, set_by, f"Status: {status}", summary, _now()),
        )
    return {"updated": True, "ticket_id": ticket_id, "old_status": row["status"], "status": status}


def list_tickets() -> dict:
    """List every ticket on the board, resolved or not, with its current status.

    Reads: tickets, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        tickets = [dict(t) for t in conn.execute("SELECT * FROM tickets ORDER BY id")]
    return {"date_today": today.isoformat(), "tickets": tickets}


def list_inventory(sku: str | None = None) -> dict:
    """List every SKU and size on file with units on hand, or every size of one SKU.

    Use it to find sizes that are in stock when the requested one is short or missing.
    Reads: inventory.
    """
    with _connect() as conn:
        if sku is None:
            rows = conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory ORDER BY sku, size"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
                (sku,),
            ).fetchall()
    if sku is not None and not rows:
        return {"found": False, "sku": sku, "error": "No inventory rows for this SKU."}
    return {"found": True, "items": [dict(r) for r in rows]}


def list_approvals(status: str | None = None, ticket_id: int | None = None) -> dict:
    """List payment approval requests, optionally filtered by status
    (pending, approved, rejected, paid, refused) and/or ticket.

    Reads: approvals.
    """
    sql, params = "SELECT * FROM approvals WHERE 1 = 1", []
    if status is not None:
        sql, params = sql + " AND status = ?", params + [status]
    if ticket_id is not None:
        sql, params = sql + " AND ticket_id = ?", params + [ticket_id]
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY id", params)]
    return {"approvals": rows}


def get_approval(approval_id: int) -> dict:
    """Read one payment approval request: what it pays, how much, its status, and who decided.

    Reads: approvals.
    """
    with _connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if row is None:
        return {"found": False, "approval_id": approval_id, "error": "No approval with this id."}
    return {"found": True, "approval": dict(row)}


def discount_options(ticket_id: int, discount_pcts: list[float] | None = None) -> dict:
    """Profitability of several discount levels for a ticket's SKU and quantity.

    For each discount: unit price, revenue, discount given, cost, profit, margin,
    profit given up versus list, and a below-cost flag. Also reports the stock on
    hand so a person can see how much of the order can ship now.
    Reads: tickets, inventory, pricing.
    """
    with _connect() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"found": False, "error": f"No ticket with id {ticket_id}."}
        if not ticket["sku"] or not ticket["qty"]:
            return {"found": False, "error": f"Ticket {ticket_id} has no SKU and quantity to price."}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)
        ).fetchone()
        item = conn.execute(
            "SELECT name, qty FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        ).fetchone()
    if price is None:
        return {"found": False, "error": f"No pricing row for {ticket['sku']}."}

    cost, list_price, qty = price["unit_cost"], price["list_price"], ticket["qty"]
    list_profit = round((list_price - cost) * qty, 2)
    options = []
    for pct in sorted(set(discount_pcts or [0, 5, 10, 15, 20, 25, 30])):
        unit = round(list_price * (1 - pct / 100), 2)
        revenue = round(unit * qty, 2)
        profit = round((unit - cost) * qty, 2)
        options.append(
            {
                "discount_pct": pct,
                "unit_price": unit,
                "unit_profit": round(unit - cost, 2),
                "revenue": revenue,
                "discount_given": round(list_price * qty - revenue, 2),
                "total_cost": round(cost * qty, 2),
                "profit": profit,
                "margin_pct": round(profit / revenue * 100, 2) if revenue else None,
                "profit_given_up": round(list_profit - profit, 2),
                "below_cost": unit < cost,
            }
        )
    return {
        "found": True,
        "ticket_id": ticket_id,
        "sku": ticket["sku"],
        "name": item["name"] if item else None,
        "size": ticket["size"],
        "qty": qty,
        "qty_on_hand": item["qty"] if item else None,
        "unit_cost": cost,
        "list_price": list_price,
        "revenue_at_list": round(list_price * qty, 2),
        "profit_at_list": list_profit,
        "break_even_discount_pct": round((1 - cost / list_price) * 100, 2),
        "options": options,
    }


_AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "system"}


def decide_approval(approval_id: int, approver: str, approve: bool) -> dict:
    """HUMAN ONLY: record a person's approve/reject decision on a pending payment request.

    No agent is given this tool. It refuses agent names as the approver.
    Approving does not move money; accounting pays afterwards with pay_approved.
    Reads/writes: approvals.
    """
    approver = approver.strip()
    if not approver or approver.lower() in _AGENT_NAMES:
        return {"decided": False, "error": "Approvals must be made by a named human, not an agent."}
    with _connect() as conn:
        row = conn.execute("SELECT status FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            return {"decided": False, "error": f"No approval with id {approval_id}."}
        if row["status"] != "pending":
            return {"decided": False, "error": f"Approval {approval_id} is already '{row['status']}'."}
        status = "approved" if approve else "rejected"
        conn.execute(
            "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
            (status, approver, _now(), approval_id),
        )
        appr = dict(conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone())
    return {"decided": True, "approval": appr}


def record_human_decision(
    ticket_id: int,
    decided_by: str,
    decision: str,
    discount_pct: float | None = None,
    note: str = "",
) -> dict:
    """HUMAN ONLY: record a person's decision on a ticket the boss sent to a human.

    decision is offer_discount (with discount_pct), decline_discount, or
    wait_for_customer. A discount that would sell below unit cost is refused.
    No agent is given this tool; it rejects agent names. It moves no money.
    Reads: tickets, pricing. Writes: human_decisions, board_drafts (note).
    """
    decided_by = decided_by.strip()
    if not decided_by or decided_by.lower() in _AGENT_NAMES:
        return {"recorded": False, "error": "Decisions must be made by a named human, not an agent."}
    if decision not in HUMAN_DECISIONS:
        return {"recorded": False, "error": f"decision must be one of {HUMAN_DECISIONS}."}
    with _connect() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"recorded": False, "error": f"No ticket with id {ticket_id}."}
        unit_price = None
        if decision == "offer_discount":
            if discount_pct is None or not 0 < discount_pct < 100:
                return {"recorded": False, "error": "offer_discount needs a discount_pct between 0 and 100."}
            price = conn.execute(
                "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)
            ).fetchone()
            if price is None:
                return {"recorded": False, "error": f"No pricing for the SKU on ticket {ticket_id}."}
            unit_price = round(price["list_price"] * (1 - discount_pct / 100), 2)
            if unit_price < price["unit_cost"]:
                return {
                    "recorded": False,
                    "error": f"{discount_pct}% off gives ${unit_price:.2f}, below the "
                    f"${price['unit_cost']:.2f} unit cost. Refused: no selling below cost.",
                }
        else:
            discount_pct = None
        cur = conn.execute(
            "INSERT INTO human_decisions (ticket_id, decision, discount_pct, unit_price, qty, note, "
            "decided_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, decision, discount_pct, unit_price, ticket["qty"], note, decided_by, _now()),
        )
        if decision == "offer_discount":
            label = f"Offer {discount_pct:g}% off (${unit_price:.2f} per unit)"
        elif decision == "decline_discount":
            label = "Decline the discount; keep list price"
        else:
            label = "Wait for the customer to name a discount"
        conn.execute(
            "INSERT INTO board_drafts (ticket_id, author, kind, title, body, status, created_at) "
            "VALUES (?, ?, 'note', ?, ?, 'draft', ?)",
            (ticket_id, f"human:{decided_by}", f"Human decision: {label}",
             f"{label}. Decided by {decided_by}." + (f" Note: {note}" if note else ""), _now()),
        )
        row = dict(conn.execute(
            "SELECT * FROM human_decisions WHERE id = ?", (cur.lastrowid,)
        ).fetchone())
    return {"recorded": True, "decision": row, "summary": label}


for _tool in (
    check_stock,
    check_vendor_status,
    check_rent_due,
    get_ticket,
    list_open_tickets,
    check_cash,
    check_invoice,
    check_discount,
    request_payment_approval,
    pay_approved,
    save_draft,
    list_board,
    set_ticket_status,
    list_tickets,
    list_inventory,
    list_approvals,
    get_approval,
    decide_approval,
    discount_options,
    record_human_decision,
):
    mcp.tool(_tool)


if __name__ == "__main__":
    mcp.run()
