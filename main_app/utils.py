import nltk
import string
from django.db.models import Func
from regex import W

from main_app.types import Context, SearchResultItem
nltk.download('punkt')


def get_frequency_distribution(text:str, raw=False):
    """
    Get overall frequency distribution of a given text
    """
    if raw:
        fd = nltk.FreqDist(word.lower() for word in text.split() if word not in string.punctuation)
        return fd
    else:
        words = nltk.word_tokenize(text)

        # Calculate the frequency distribution with words punctuation removed
        freq_dist = nltk.FreqDist(word.lower() for word in words if word not in string.punctuation)
        # freq_dist = nltk.FreqDist(word.lower() for word in nltk.word_tokenize(sent))
        return freq_dist



def get_word_frequency(word:str, text:str):
    """
    Get word frequency of the article
    """
    freq_dist = get_frequency_distribution(text)
    return freq_dist[word]



class RegexpReplace(Func):
    """ 
    
    exaple RegexpReplace(
        'content',
        fr'((\S+\s+){{0,5}}\S*{substring}\S*(\s+\S+){{0,5}})',
        r'<mark>\1</mark>',
        'gi'  # 'gi' for case-insensitive matching
    )
    """
    function = 'REGEXP_REPLACE' # The name of the function in the database
    arity = 2 # The number of arguments the function takes



from nltk.tokenize import word_tokenize
from django.utils.html import strip_tags

def search_word(text:str, word:str, padding=5) -> SearchResultItem:
    word = word.lower()
    text = strip_tags(text) # remove HTML tags
    tokens = word_tokenize(text)
    count = 0
    results = {
        "article": None, # type: ignore
        "frequency": 0,
        "locations": []
    }
    for i, token in enumerate(tokens):
        exact_match = token.lower() == word
        partial_match = word in token.lower()
        if exact_match or partial_match:
            count += 1
            start = max(0, i - padding)
            end = min(len(tokens), i + padding + 1)
            context = ' '.join(tokens[start:end])
            # results['locations'].append((count, context, "exact" if exact_match else "partial"))
            results['locations'].append(Context(count=count, context=context, type="exact" if exact_match else "partial"))
    results['frequency'] = count

    # sort locations that exact matches come first
    results['locations'].sort(key=lambda x: x['type'], reverse=False)
    return results
