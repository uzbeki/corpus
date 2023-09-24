from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@stringfilter
@register.filter(name='concat')
def concat(value, arg):
    return f'{str(value)}{str(arg)}'

@stringfilter
@register.filter(name='random_img')
def random_img(value):
    import random
    return f'{str(value)}{random.randint(1, 4)}.png'
