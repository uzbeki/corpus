from typing import Generic, List, TypeVar, TypedDict, Literal

T = TypeVar('T')

class Context(TypedDict):
    count: int
    context: str
    type: Literal['exact', 'partial']

# class SearchResultItem(TypedDict, Generic[T]):
class SearchResultItem(TypedDict): # python 3.10 does not support it yet
    article: T
    frequency: int
    locations: list[Context]

# class SearchResult(TypedDict, Generic[T]):
class SearchResult(TypedDict): # python 3.10 does not support it yet
    query: str
    results: List[SearchResultItem[T]]
    total_frequency: int

class FrequencyStat(TypedDict):
    word: str
    count: int
    language: str

FrequencyStats= list[FrequencyStat]