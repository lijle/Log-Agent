from __future__ import annotations

from pathlib import Path

from rag.document_loader import load_markdown_documents, split_documents
from rag.vector_store import LocalTfidfVectorStore


class KnowledgeRetriever:
    """知识库检索器。

    作用：
    - 负责加载 Markdown 文档
    - 将文档切片
    - 把切片交给本地向量检索实现
    """

    def __init__(self, knowledge_base_dir: Path) -> None:
        """初始化检索器并立即建立索引。

        输入：
        - knowledge_base_dir：知识库目录

        输出：
        - None
        """

        self.knowledge_base_dir = knowledge_base_dir
        self.vector_store = LocalTfidfVectorStore()
        self._build_index()

    def _build_index(self) -> None:
        """构建知识库索引。

        作用：
        - 读取原始 Markdown
        - 切分成 chunks
        - 建立 TF-IDF 索引

        输出：
        - None
        """

        documents = load_markdown_documents(self.knowledge_base_dir)
        chunks = split_documents(documents)
        self.vector_store.build(chunks)

    def retrieve(self, query: str, top_k: int = 4) -> list[dict[str, str]]:
        """检索与查询最相关的知识片段。

        输入：
        - query：检索文本
        - top_k：返回的最大结果数

        输出：
        - list[dict[str, str]]：按相关性排序的知识片段
        """

        return self.vector_store.search(query=query, top_k=top_k)
