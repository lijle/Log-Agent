from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.retriever import KnowledgeRetriever
from tools.base_tool import BaseTool


class RAGTool(BaseTool):
    """知识库检索工具。"""

    name = "rag_tool"
    description = "Retrieve relevant troubleshooting knowledge from local markdown documents."

    def __init__(
        self,
        knowledge_base_dir: Path,
        default_top_k: int = 4,
        default_candidate_k: int | None = None,
    ) -> None:
        """初始化 RAG 检索工具。"""
        self.retriever = KnowledgeRetriever(knowledge_base_dir=knowledge_base_dir)
        self.default_top_k = default_top_k
        self.default_candidate_k = default_candidate_k

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """执行知识检索。

        输入：
        - input["query"]: 检索词
        - input["top_k"]: 最终返回条数
        - input["candidate_k"]: 粗召回候选条数
        """
        query = input.get("query", "").strip()
        top_k = int(input.get("top_k", self.default_top_k))
        candidate_k = input.get("candidate_k", self.default_candidate_k)
        candidate_k = int(candidate_k) if candidate_k is not None else None

        if not query:
            return {"documents": [], "query": query, "top_k": top_k, "candidate_k": candidate_k}

        docs = self.retriever.retrieve(query=query, top_k=top_k, candidate_k=candidate_k)
        return {
            "query": query,
            "top_k": top_k,
            "candidate_k": candidate_k,
            "retrieval_mode": "hybrid",
            "documents": docs,
        }
