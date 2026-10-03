"""Utility helpers for formatting and validations."""

import re

def format_currency(amount: float) -> str:
    return f"${amount:,.2f}"

def validate_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))

def calculate_discount(tier: str, amount: float) -> float:
    tier_rates = {
        "standard": 0.0,
        "silver": 0.05,
        "gold": 0.10,
        "platinum": 0.20,
    }
    rate = tier_rates.get(tier.lower(), 0.0)
    return amount * rate
