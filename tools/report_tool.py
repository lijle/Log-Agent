from __future__ import annotations

import json
from typing import Any

from llm.base_llm import BaseLLM
from memory.sqlite_memory import SQLiteMemory
from tools.base_tool import BaseTool
from diagnosis import Evidence, RootCauseCandidate

class ReportTool(BaseTool):
    """诊断报告生成工具。

    作用：
    - 综合日志解析结果、知识检索结果、历史案例结果
    - 推断可能根因、排查步骤、推荐查询语句和置信度
    - 最终输出 Markdown 诊断报告
    """

    name = "report_tool"
    description = "生成结构化 Markdown 诊断报告。"

    def __init__(self, llm: BaseLLM, memory_store: SQLiteMemory | None = None) -> None:
        """初始化报告工具。

        输入：
        - llm：用于可选报告润色的 LLM 实例
        - memory_store：当前项目暂未直接使用，但保留给后续扩展

        输出：
        - None
        """

        self.llm = llm
        self.memory_store = memory_store

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """生成一次诊断报告结果。

        输入：
        - input：通常包含 parsed_result、rag_result、memory_result

        输出：
        - dict[str, Any]：包含 diagnosis_summary、root_causes、report_markdown 等字段
        """

        parsed_result = input.get("parsed_result", {})
        rag_result = input.get("rag_result", {})
        memory_result = input.get("memory_result", {})

        report = self._build_report(parsed_result, rag_result, memory_result)
        return report

    def _build_report(
        self,
        parsed_result: dict[str, Any],
        rag_result: dict[str, Any],
        memory_result: dict[str, Any],
    ) -> dict[str, Any]:
        """基于三类输入组装完整报告。

        作用：
        - 从日志中抽取字段和摘要
        - 结合知识库片段推断根因和排查步骤
        - 生成确定性报告，并视情况用 LLM 做增强

        输入：
        - parsed_result：日志解析结果
        - rag_result：知识库检索结果
        - memory_result：历史案例检索结果

        输出：
        - dict[str, Any]：报告结构化结果
        """

        fields = parsed_result.get("extracted_fields", {})
        summary = parsed_result.get("log_summary", "暂无日志摘要。")
        documents = rag_result.get("documents", [])
        related_cases = memory_result.get("cases", [])

        root_causes = self._infer_root_causes(fields, documents)
        troubleshooting_steps = self._infer_troubleshooting_steps(documents, fields)
        suggested_queries = self._build_queries(fields)
        confidence_score = self._estimate_confidence(fields, documents)
        root_cause_candidates = self._build_root_cause_candidates(
            fields=fields,
            documents=documents,
            evidence_lines=parsed_result.get("evidence_lines", []),
            root_causes=root_causes,
            troubleshooting_steps=troubleshooting_steps,
            confidence_score=confidence_score,
        )

        deterministic_report = self._render_markdown(
            summary=summary,
            fields=fields,
            documents=documents,
            root_causes=root_causes,
            troubleshooting_steps=troubleshooting_steps,
            suggested_queries=suggested_queries,
            confidence_score=confidence_score,
            related_cases=related_cases,
        )
        report_markdown = self._maybe_generate_llm_report(
            parsed_result=parsed_result,
            rag_result=rag_result,
            memory_result=memory_result,
            fallback_report=deterministic_report,
        )

        service_name = fields.get("service_name", "未知服务")
        exception_type = fields.get("exception_type", "未知异常")
        hint = "、".join(root_causes[:2]) if root_causes else "相关依赖或上下游链路"
        diagnosis_summary = f"{service_name} 出现 {exception_type}，建议优先排查：{hint}。"

        return {
            "diagnosis_summary": diagnosis_summary,
            "root_causes": root_causes,
            "root_cause_candidates": root_cause_candidates,
            "troubleshooting_steps": troubleshooting_steps,
            "suggested_queries": suggested_queries,
            "confidence_score": confidence_score,
            "report_markdown": report_markdown,
            "llm_mode": self.llm.__class__.__name__,
        }

    def _maybe_generate_llm_report(
        self,
        parsed_result: dict[str, Any],
        rag_result: dict[str, Any],
        memory_result: dict[str, Any],
        fallback_report: str,
    ) -> str:
        """在真实 LLM 可用时生成增强版报告，否则回退到规则报告。

        输入：
        - parsed_result：日志解析结果
        - rag_result：知识检索结果
        - memory_result：历史案例结果
        - fallback_report：确定性规则生成的报告

        输出：
        - str：最终要展示的 Markdown 报告文本
        """

        if self.llm.__class__.__name__ == "FakeLLM":
            return fallback_report

        system_prompt = (
            "你是一名资深后端稳定性与故障排查助手。"
            "请基于输入证据生成简洁、可信、可执行的中文 Markdown 诊断报告。"
        )
        user_prompt = (
            "请输出一份中文结构化诊断报告，包含以下章节：\n"
            "问题概述\n关键日志证据\n提取字段\n可能根因\n建议排查步骤\n"
            "推荐查询语句\n置信度\n相关历史案例\n\n"
            f"Parsed Result:\n{json.dumps(parsed_result, ensure_ascii=False, indent=2)}\n\n"
            f"RAG Result:\n{json.dumps(rag_result, ensure_ascii=False, indent=2)}\n\n"
            f"Memory Result:\n{json.dumps(memory_result, ensure_ascii=False, indent=2)}\n"
        )
        try:
            llm_report = self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt).strip()
            return llm_report or fallback_report
        except Exception:
            return fallback_report

    def _infer_root_causes(
        self,
        fields: dict[str, Any],
        documents: list[dict[str, Any]],
    ) -> list[str]:
        """根据异常类型、错误信息和知识库内容推断可能根因。

        输入：
        - fields：结构化日志字段
        - documents：相关知识片段

        输出：
        - list[str]：按优先级排序的根因候选列表
        """

        exception_type = str(fields.get("exception_type", "")).lower()
        message = str(fields.get("error_message", "")).lower()
        root_causes: list[str] = []

        if "timeout" in exception_type or "timeout" in message:
            root_causes.extend(
                [
                    "下游服务响应变慢或超时。",
                    "网络链路抖动导致请求耗时升高。",
                    "当前超时阈值或重试配置偏保守。",
                ]
            )
        elif "null" in exception_type or "none" in message:
            root_causes.extend(
                [
                    "代码中的空值判断不足。",
                    "上游输入字段缺失，或对象未正确初始化。",
                    "异常路径缺少防御式编程处理。",
                ]
            )
        elif "sql" in exception_type or "database" in message or "connection" in message:
            root_causes.extend(
                [
                    "数据库连接池耗尽或连接不可用。",
                    "数据库实例负载过高，或网络不可达。",
                    "应用侧数据库连接配置存在错误。",
                ]
            )
        elif "auth" in exception_type or "token" in message or fields.get("http_status_code") == 401:
            root_causes.extend(
                [
                    "认证令牌失效、缺失或格式不合法。",
                    "调用方权限不足，无法访问目标资源。",
                    "认证服务校验失败，或系统时间偏差导致签名无效。",
                ]
            )

        for doc in documents:
            content = str(doc.get("content", "")).strip()
            if "常见根因" in content or "common root causes" in content.lower():
                preview = content[:80].replace("\n", " ").strip()
                root_causes.append(f"知识库提示：{preview}...")

        if not root_causes:
            root_causes = ["当前证据不足，建议结合更多上下文继续确认根因。"]

        return root_causes[:4]

    def _infer_troubleshooting_steps(
        self,
        documents: list[dict[str, Any]],
        fields: dict[str, Any],
    ) -> list[str]:
        """生成建议排查步骤。

        作用：
        - 利用服务名、状态码、trace id 和知识库文档
        - 输出面向工程排障的可执行步骤

        输入：
        - documents：知识库片段
        - fields：结构化日志字段

        输出：
        - list[str]：建议排查步骤列表
        """

        steps: list[str] = []
        service_name = fields.get("service_name", "目标服务")

        if fields.get("http_status_code"):
            steps.append(f"确认 {service_name} 的 HTTP 状态码分布，以及失败请求的比例。")
        if fields.get("trace_id"):
            steps.append(f"基于 trace/request id `{fields['trace_id']}` 串联上下游日志。")
        steps.extend(
            [
                f"检查 {service_name} 最近的发布、配置变更和资源水位。",
                "对照知识库排查超时、连接、鉴权、空指针等高频问题。",
                "按同一时间窗口聚类错误日志，确认是孤立问题还是批量故障。",
            ]
        )
        for doc in documents[:2]:
            title = self._get_document_title(doc)
            steps.append(f"参考知识库《{title}》中的检查建议。")
        return steps[:5]

    def _build_queries(self, fields: dict[str, Any]) -> list[str]:
        """生成面向日志平台和 K8s 的通用查询语句。

        输入：
        - fields：结构化日志字段

        输出：
        - list[str]：查询语句列表
        """

        service = fields.get("service_name", "your-service")
        trace_id = fields.get("trace_id", "trace-or-request-id")
        exception_type = fields.get("exception_type", "Exception")

        return [
            f'Splunk 风格查询：service="{service}" "{exception_type}" "{trace_id}"',
            f'CloudWatch 风格查询：fields @timestamp, @message | filter @message like /{service}/ and @message like /{exception_type}/',
            f'K8s 日志查询：kubectl logs deployment/{service} --since=30m | findstr "{trace_id}"',
        ]

    def _estimate_confidence(
        self,
        fields: dict[str, Any],
        documents: list[dict[str, Any]],
    ) -> float:
        """根据字段完整度和知识召回情况估算置信度。

        输入：
        - fields：结构化日志字段
        - documents：知识片段列表

        输出：
        - float：0 到 1 之间的置信度分数
        """

        score = 0.45
        for key in ["timestamp", "log_level", "service_name", "trace_id", "exception_type", "error_message"]:
            if fields.get(key):
                score += 0.05
        if fields.get("http_status_code"):
            score += 0.05
        if documents:
            score += min(0.15, len(documents) * 0.03)
        return round(min(score, 0.95), 2)

    def _build_root_cause_candidates(
        self,
        fields: dict[str, Any],
        documents: list[dict[str, Any]],
        evidence_lines: list[str],
        root_causes: list[str],
        troubleshooting_steps: list[str],
        confidence_score: float,
    ) -> list[dict[str, Any]]:
        """生成带证据的根因候选，供评估和后续可解释展示使用。"""

        evidence_list: list[Evidence] = []

        # 1. 把结构化字段转成 Evidence 对象
        for key in ["service_name", "exception_type", "error_message", "http_status_code"]:
            value = fields.get(key)
            if value:
                evidence_item = Evidence(
                    evidence_type="log_field",
                    content=f"{key}={value}",
                    source="parsed_log",
                    score=None,
                    metadata={"field": key},
                )
                evidence_list.append(evidence_item)

        # 2. 把关键原始日志行转成 Evidence 对象
        for line in evidence_lines[:3]:
            evidence_item = Evidence(
                evidence_type="log_line",
                content=line,
                source="raw_log",
                score=None,
                metadata={},
            )
            evidence_list.append(evidence_item)

        # 3. 把知识库片段转成 Evidence 对象
        for doc in documents[:3]:
            evidence_item = Evidence(
                evidence_type="rag_chunk",
                content=str(doc.get("content", ""))[:240],
                source=str(doc.get("source", "knowledge_base")),
                score=doc.get("rerank_score", doc.get("score")),
                metadata={
                    "retrievers": doc.get("retrievers", []),
                    "base_score": doc.get("base_score"),
                    "fusion_score": doc.get("fusion_score"),
                },
            )
            evidence_list.append(evidence_item)

        # 4. 先整理缺失证据
        missing_evidence: list[str] = []
        if not fields.get("service_name"):
            missing_evidence.append("service_name")
        if not fields.get("exception_type"):
            missing_evidence.append("exception_type")
        if not fields.get("error_message"):
            missing_evidence.append("error_message")
        if not documents:
            missing_evidence.append("rag_chunk")

        # 5. 为每个 root cause 生成一个 RootCauseCandidate 对象
        candidates: list[RootCauseCandidate] = []
        for index, cause in enumerate(root_causes):
            candidate = RootCauseCandidate(
                hypothesis=cause,
                evidence=evidence_list,
                confidence=round(max(0.1, confidence_score - index * 0.08), 2),
                missing_evidence=missing_evidence,
                next_actions=troubleshooting_steps[:3],
            )
            candidates.append(candidate)

        # 6. 最后统一转成 dict，方便 JSON / Streamlit / eval 使用
        return [candidate.to_dict() for candidate in candidates]

    def _render_markdown(
        self,
        summary: str,
        fields: dict[str, Any],
        documents: list[dict[str, Any]],
        root_causes: list[str],
        troubleshooting_steps: list[str],
        suggested_queries: list[str],
        confidence_score: float,
        related_cases: list[dict[str, Any]],
    ) -> str:
        """把报告结果渲染成 Markdown。

        输入：
        - summary：日志摘要
        - fields：结构化字段
        - documents：知识片段
        - root_causes：根因列表
        - troubleshooting_steps：排查步骤
        - suggested_queries：建议查询语句
        - confidence_score：置信度
        - related_cases：相似历史案例

        输出：
        - str：最终展示给用户的 Markdown 文本
        """

        knowledge_lines = [
            f"- 《{self._get_document_title(doc)}》：{doc.get('content', '')[:180].replace(chr(10), ' ').strip()}..."
            for doc in documents
        ] or ["- 暂无相关知识片段。"]

        case_lines = [
            f"- `{case.get('case_id')}` | {case.get('diagnosis_summary', '')}"
            for case in related_cases
        ] or ["- 暂无相似历史案例。"]

        return f"""
## 问题概述
{summary}

## 关键日志证据
- 异常类型：`{fields.get("exception_type", "N/A")}`
- 错误信息：`{fields.get("error_message", "N/A")}`
- 服务名称：`{fields.get("service_name", "N/A")}`
- Trace ID：`{fields.get("trace_id", "N/A")}`
- HTTP 状态码：`{fields.get("http_status_code", "N/A")}`

## 提取字段
```json
{json.dumps(fields, ensure_ascii=False, indent=2)}
```

## 可能根因
{chr(10).join(f"- {item}" for item in root_causes)}

## 建议排查步骤
{chr(10).join(f"- {item}" for item in troubleshooting_steps)}

## 推荐查询语句
{chr(10).join(f"- {item}" for item in suggested_queries)}

## 检索到的知识
{chr(10).join(knowledge_lines)}

## 相关历史案例
{chr(10).join(case_lines)}

## 置信度
`{confidence_score}`
""".strip()

    @staticmethod
    def _get_document_title(doc: dict[str, Any]) -> str:
        """从知识文档内容中提取标题。

        输入：
        - doc：知识片段字典

        输出：
        - str：优先返回 Markdown 标题，否则回退到文件名
        """

        content = str(doc.get("content", "")).strip()
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip()
        return str(doc.get("source", "未命名知识文档"))
