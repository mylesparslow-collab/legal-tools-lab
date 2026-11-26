"""Optional reranker interface. Off by default; nothing here ships a model.

This is where semantic ranking would plug in later. kx/search.py calls a
reranker only after permission filtering, version collapse and near-duplicate
collapse, and passes it only documents the asking user may see. A reranker
therefore cannot widen access. It can only reorder the top of a permitted
list. If the reranker is a remote service, sending it document text is a
disclosure decision for the firm; this demo makes no such call.
"""
from __future__ import annotations

from typing import Protocol, Sequence


class Reranker(Protocol):
    def rerank(self, query: str, docs: Sequence[dict]) -> Sequence[float]:
        """Return one score per document, higher is better.

        Each document is a dict with doc_id, title and body."""
        ...
