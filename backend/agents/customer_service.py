"""Customer service: customer message drafts from confirmed facts only. Never sends."""

from .base import build_specialist

customer_service_agent = build_specialist("customer_service")
