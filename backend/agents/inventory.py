"""Inventory: stock by SKU + size + qty, shortfalls, and which vendor can restock. Never orders."""

from .base import build_specialist

inventory_agent = build_specialist("inventory")
