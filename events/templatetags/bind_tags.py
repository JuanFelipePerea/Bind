from django import template

register = template.Library()


@register.filter
def currency_format(value, currency=''):
    """
    Formatea un número con separadores de miles (estilo es-CO: puntos).
    {{ 5000000|currency_format }}          → "5.000.000"
    {{ 5000000|currency_format:budget.currency }} → "5.000.000 COP"
    """
    try:
        val = int(round(float(value)))
        formatted = f"{val:,}".replace(",", ".")
        return f"{formatted} {currency}".strip() if currency else formatted
    except (ValueError, TypeError):
        return value
