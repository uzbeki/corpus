from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@stringfilter
@register.filter(name='concat')
def concat(value, arg):
    return f'{str(value)}{str(arg)}'

