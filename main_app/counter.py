KEEP_TOP_WORDS = 10

import re

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

    def __init__(self, list_of_contents: list[str]):
        self.top_words = list()
        self.total_words = 0
        self.list_of_contents = list_of_contents
        self.word_freq = dict()
        self._count_words()

    def _count_words(self):
        for content in self.list_of_contents:
            for word in content.split():
                word = cleanse_word(word)
                if not word:
                    continue
                self.word_freq.setdefault(word, 0)
                self.word_freq[word] += 1
                self.total_words += 1
                self._insert_to_top(word)

    def _insert_to_top(self, word):
        if self.top_words:
            for index, item in enumerate(self.top_words):
                if self.word_freq[item] <= self.word_freq[word]:
                    if word in self.top_words:
                        del self.top_words[self.top_words.index(word)]
                    self.top_words.insert(index, word)
                    del self.top_words[KEEP_TOP_WORDS:]
                    break
                elif len(self.top_words) < KEEP_TOP_WORDS and word not in self.top_words:
                    # Case where top 10 not full and word not in top 10 already
                    self.top_words.append(word)
        else:
            self.top_words.append(word)

    def display_top_words(self):
        for word in self.top_words:
            print(word, self.word_freq[word])