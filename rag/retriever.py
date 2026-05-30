from __future__ import annotations

from pathlib import Path

from rag.document_loader import load_markdown_documents, split_documents
from rag.vector_store import LocalTfidfVectorStore


class KnowledgeRetriever:
    def __init__(self, knowledge_base_dir: Path) -> None:
        self.knowledge_base_dir = knowledge_base_dir
        self.vector_store = LocalTfidfVectorStore()
        self._build_index()

    def _build_index(self) -> None:
        documents = load_markdown_documents(self.knowledge_base_dir)
        chunks = split_documents(documents)
        self.vector_store.build(chunks)

    def retrieve(self, query: str, top_k: int = 4) -> list[dict[str, str]]:
        return self.vector_store.search(query=query, top_k=top_k)
