from typing import Generic, List, TypeVar, TypedDict, Literal

T = TypeVar('T')

class Context(TypedDict):
    count: int
    context: str
    type: Literal['exact', 'partial']

class SearchResultItem(TypedDict, Generic[T]):
    article: T
    frequency: int
    locations: list[Context]

class SearchResult(TypedDict, Generic[T]):
    query: str
    results: List[SearchResultItem[T]]
    total_frequency: int