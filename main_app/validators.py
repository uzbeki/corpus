from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def max_word_count(value, max_words):
    num_words = len(value.split())
    if num_words > max_words:
        raise ValidationError(
            _(f"The maximum number of words allowed is {max_words}. You have {num_words} words."),
            params={'max_words': max_words},
        )

def min_word_count(value, min_words):
    num_words = len(value.split())
    if num_words < min_words:
        raise ValidationError(
            _(f"The minimum number of words allowed is {min_words}. You have {num_words} words."),
            params={'min_words': min_words},
        )
