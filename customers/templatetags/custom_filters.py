from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """Custom template filter to lookup dictionary values with dynamic keys"""
    if dictionary is None:
        return 0
    return dictionary.get(key, 0)

@register.filter
def default_if_none(value, default):
    """Return default if value is None"""
    return default if value is None else value