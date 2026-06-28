from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.document_loader import load_markdown_documents, split_documents
from rag.vector_store import LocalEmbeddingVectorStore, LocalTfidfVectorStore
class KnowledgeRetriever:
    """知识库检索器。

    作用：
    1. 加载本地 Markdown 知识库
    2. 将文档切分成知识片段
    3. 建立 sparse + dense 双索引
    4. 先做 hybrid retrieval
    5. 再做规则型 rerank
    """

    def __init__(self, knowledge_base_dir: Path) -> None:
        """初始化检索器并立即建立索引。"""
        self.knowledge_base_dir = knowledge_base_dir
        self.sparse_store = LocalTfidfVectorStore()
        self.dense_store = LocalEmbeddingVectorStore()
        self._build_index()

    def _build_index(self) -> None:
        """构建知识库索引。"""
        documents = load_markdown_documents(self.knowledge_base_dir)
        chunks = split_documents(documents)
        self.sparse_store.build(chunks)
        self.dense_store.build(chunks)

    @staticmethod
    def _extract_query_terms(query: str) -> list[str]:
        """从 query 中提取适合 rerank 的核心词。"""
        raw_terms = [term.strip().lower() for term in query.split()]
        filtered_terms = [
            term
            for term in raw_terms
            if term
            and len(term) >= 4
            and term not in {"http", "error", "service"}
        ]

        deduplicated: list[str] = []
        for term in filtered_terms:
            if term not in deduplicated:
                deduplicated.append(term)
        return deduplicated

    @staticmethod
    def hybrid_fuse(
        sparse_docs: list[dict[str, Any]],
        dense_docs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """使用简单的 RRF 思想融合 sparse 和 dense 结果。"""
        fused: dict[tuple[str, str], dict[str, Any]] = {}

        def add_docs(docs: list[dict[str, Any]], source_name: str) -> None:
            for rank, doc in enumerate(docs, start=1):
                key = (str(doc.get("source", "")), str(doc.get("content", "")))

                # Reciprocal Rank Fusion 的简化版
                rrf_score = 1.0 / (60 + rank)

                if key not in fused:
                    fused[key] = {
                        "source": doc["source"],
                        "content": doc["content"],
                        "score": doc.get("score", 0.0),
                        "fusion_score": rrf_score,
                        "retrievers": [source_name],
                    }
                else:
                    fused[key]["fusion_score"] += rrf_score
                    if source_name not in fused[key]["retrievers"]:
                        fused[key]["retrievers"].append(source_name)

        add_docs(sparse_docs, "sparse")
        add_docs(dense_docs, "dense")

        results = list(fused.values())
        results.sort(key=lambda item: item.get("fusion_score", 0.0), reverse=True)
        return results

    def rerank_documents(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """基于规则对粗召回结果做二次重排。"""
        query_terms = self._extract_query_terms(query)
        reranked: list[dict[str, Any]] = []

        for doc in documents:
            content = str(doc.get("content", "")).lower()
            source = str(doc.get("source", "")).lower()
            base_score = float(doc.get("fusion_score", doc.get("score", 0.0)))
            rerank_score = base_score

            for term in query_terms:
                if term in content:
                    rerank_score += 0.08
                if term in source:
                    rerank_score += 0.04

            # 对日志诊断高频语义词给予额外加分。
            if "exception" in content and any("exception" in term for term in query_terms):
                rerank_score += 0.05
            if "timeout" in content and "timeout" in query_terms:
                rerank_score += 0.05
            if "connection" in content and "connection" in query_terms:
                rerank_score += 0.05

            reranked_doc = dict(doc)
            reranked_doc["base_score"] = base_score
            reranked_doc["rerank_score"] = rerank_score
            reranked.append(reranked_doc)

        reranked.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return reranked[:top_k]

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        candidate_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """检索与查询最相关的知识片段。

        输入：
        - query: 检索文本
        - top_k: 最终返回结果数
        - candidate_k: 粗召回候选数，默认取 top_k 的两倍

        输出：
        - 按 rerank 后顺序排列的知识片段
        """
        candidate_limit = candidate_k if candidate_k is not None else max(top_k * 2, top_k)

        sparse_docs = self.sparse_store.search(query=query, top_k=candidate_limit)
        dense_docs = self.dense_store.search(query=query, top_k=candidate_limit)

        fused_docs = self.hybrid_fuse(sparse_docs=sparse_docs, dense_docs=dense_docs)
        candidate_docs = fused_docs[:candidate_limit]

        return self.rerank_documents(query=query, documents=candidate_docs, top_k=top_k)
