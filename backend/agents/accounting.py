"""Accounting: cash, invoices, margins; requests approvals and pays only human-approved ones."""

from .base import build_specialist

accounting_agent = build_specialist("accounting")
