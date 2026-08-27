from typing import Protocol


class Reranker(Protocol):
    async def rank(self, query: str, candidates: list) -> list: ...
