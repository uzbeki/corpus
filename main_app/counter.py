KEEP_TOP_WORDS = 10

import re
from collections import Counter
from collections.abc import Iterable

_APOSTROPHE_TRANSLATION = str.maketrans({
    "’": "'",  # U+2019 right single quotation mark
    "ʼ": "'",  # U+02BC modifier letter apostrophe
    "‘": "'",  # U+2018 left single quotation mark
    "′": "'",  # U+2032 prime
    "`": "'",  # grave accent
})

def cleanse_word(word:str):
    """
    Clean word using defined rules
    :param word:
    :return:
    """
    normalized = word.translate(_APOSTROPHE_TRANSLATION).lower()
    # Keep alphanumerics and internal apostrophes; drop everything else.
    normalized = re.sub(r"[^0-9a-zA-Z']+", "", normalized)
    # Trim leading/trailing apostrophes introduced by stripping punctuation.
    normalized = normalized.strip("'")
    return normalized


class WordCounter:
    """Word counting object, counts total words and top 10 occurring words"""

    def __init__(self, list_of_contents: Iterable[str]):
        self.top_words = list()
        self.total_words = 0
        self.word_freq = dict()
        self._count_words(list_of_contents)

    def _count_words(self, list_of_contents: Iterable[str]):
        word_freq = Counter()

        for content in list_of_contents:
            for word in content.split():
                word = cleanse_word(word)
                if not word:
                    continue
                self.total_words += 1
                word_freq[word] += 1

        self.word_freq = dict(word_freq)
        self.top_words = [
            word
            for word, _count in sorted(
                word_freq.items(), key=lambda item: (-item[1], item[0])
            )[:KEEP_TOP_WORDS]
        ]

    def display_top_words(self):
        for word in self.top_words:
            print(word, self.word_freq[word])
