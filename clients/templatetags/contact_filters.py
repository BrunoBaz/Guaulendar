import re

from django import template


register = template.Library()


@register.filter
def whatsapp_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    if digits.startswith("0034"):
        digits = digits[2:]
    elif not digits.startswith("34"):
        digits = f"34{digits}"
    return digits
