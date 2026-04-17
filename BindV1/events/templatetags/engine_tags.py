from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Permite acceder a diccionarios por clave en los templates Django."""
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
