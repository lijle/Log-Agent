from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.retriever import KnowledgeRetriever
from tools.base_tool import BaseTool


class RAGTool(BaseTool):
    """知识库检索工具。

    作用：
    - 基于本地 Markdown 知识库构建检索器
    - 根据日志相关查询词返回最相关的知识片段
    """

    name = "rag_tool"
    description = "Retrieve relevant troubleshooting knowledge from local markdown documents."

    def __init__(self, knowledge_base_dir: Path) -> None:
        """初始化 RAG 检索工具。

        输入：
        - knowledge_base_dir：知识库目录路径，里面存放 `.md` 排障文档

        输出：
        - None：会创建并持有 KnowledgeRetriever
        """

        self.retriever = KnowledgeRetriever(knowledge_base_dir=knowledge_base_dir)

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """执行知识检索。

        输入：
        - input：包含 `query` 和可选的 `top_k`

        输出：
        - dict[str, Any]：包含 query 和 documents 列表
        """

        query = input.get("query", "").strip()
        top_k = int(input.get("top_k", 4))
        if not query:
            return {"documents": [], "query": query}
        docs = self.retriever.retrieve(query=query, top_k=top_k)
        return {"query": query, "documents": docs}
