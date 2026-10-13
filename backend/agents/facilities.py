"""Facilities: leases and rent timing; always hands rent to accounting. Never pays."""

from .base import build_specialist

facilities_agent = build_specialist("facilities")
