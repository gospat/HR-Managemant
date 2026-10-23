from django import template
from django.template.defaultfilters import floatformat
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def export_currency(context, amount):
    """Use the exported employee's explicit currency; never global/session settings."""
    currency = context.get("currency")
    if not currency:
        return ""
    value = floatformat(amount, 2)
    if not value:
        return ""
    if context.get("currency_position") == "postfix":
        return format_html("{} {}", value, currency)
    return format_html("{} {}", currency, value)
