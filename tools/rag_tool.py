from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.retriever import KnowledgeRetriever
from tools.base_tool import BaseTool


class RAGTool(BaseTool):
    name = "rag_tool"
    description = "Retrieve relevant troubleshooting knowledge from local markdown documents."

    def __init__(self, knowledge_base_dir: Path) -> None:
        self.retriever = KnowledgeRetriever(knowledge_base_dir=knowledge_base_dir)

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        query = input.get("query", "").strip()
        top_k = int(input.get("top_k", 4))
        if not query:
            return {"documents": [], "query": query}
        docs = self.retriever.retrieve(query=query, top_k=top_k)
        return {"query": query, "documents": docs}
