from __future__ import annotations

import json
from typing import Any

from llm.base_llm import BaseLLM
from memory.sqlite_memory import SQLiteMemory
from tools.base_tool import BaseTool


class ReportTool(BaseTool):
    name = "report_tool"
    description = "Generate a structured diagnosis report in markdown."

    def __init__(self, llm: BaseLLM, memory_store: SQLiteMemory | None = None) -> None:
        self.llm = llm
        self.memory_store = memory_store

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
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
        fields = parsed_result.get("extracted_fields", {})
        summary = parsed_result.get("log_summary", "No summary available.")
        documents = rag_result.get("documents", [])
        related_cases = memory_result.get("cases", [])

        root_causes = self._infer_root_causes(fields, documents)
        troubleshooting_steps = self._infer_troubleshooting_steps(documents, fields)
        suggested_queries = self._build_queries(fields)
        confidence_score = self._estimate_confidence(fields, documents)

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

        diagnosis_summary = f"{fields.get('service_name', 'unknown-service')} 出现 {fields.get('exception_type', '异常')}，需要重点检查 {', '.join(root_causes[:2]) or '相关依赖'}。"

        return {
            "diagnosis_summary": diagnosis_summary,
            "root_causes": root_causes,
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
        if self.llm.__class__.__name__ == "FakeLLM":
            return fallback_report

        system_prompt = (
            "You are a senior SRE assistant. "
            "Generate a concise markdown diagnosis report with factual grounding only."
        )
        user_prompt = (
            "Please generate a structured markdown diagnosis report with these sections:\n"
            "Problem Summary\nKey Log Evidence\nExtracted Fields\nPossible Root Causes\n"
            "Recommended Troubleshooting Steps\nSuggested Splunk-like / CloudWatch-like / K8s-like Generic Queries\n"
            "Confidence Score\nRelated Historical Cases\n\n"
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
        exception_type = str(fields.get("exception_type", "")).lower()
        message = str(fields.get("error_message", "")).lower()
        root_causes: list[str] = []

        if "timeout" in exception_type or "timeout" in message:
            root_causes.extend(
                [
                    "下游服务响应变慢或超时",
                    "网络链路抖动导致请求耗时上升",
                    "当前超时阈值或重试配置偏保守",
                ]
            )
        elif "null" in exception_type or "none" in message:
            root_causes.extend(
                [
                    "代码空值判断不足",
                    "上游输入字段缺失或对象未初始化",
                    "异常路径缺少防御式编程处理",
                ]
            )
        elif "sql" in exception_type or "database" in message or "connection" in message:
            root_causes.extend(
                [
                    "数据库连接池耗尽或连接不可用",
                    "数据库实例负载过高或网络不可达",
                    "应用侧连接配置错误",
                ]
            )
        elif "auth" in exception_type or "token" in message or fields.get("http_status_code") == 401:
            root_causes.extend(
                [
                    "认证令牌失效或缺失",
                    "调用方权限不足",
                    "认证服务校验失败或时间偏差导致签名无效",
                ]
            )

        for doc in documents:
            content = doc.get("content", "")
            if "root cause" in content.lower() or "常见原因" in content:
                root_causes.append(f"知识库提示：{content[:80].strip()}...")

        if not root_causes:
            root_causes = ["需要结合更多上下文进一步确认根因"]

        return root_causes[:4]

    def _infer_troubleshooting_steps(
        self,
        documents: list[dict[str, Any]],
        fields: dict[str, Any],
    ) -> list[str]:
        steps: list[str] = []
        service_name = fields.get("service_name", "目标服务")

        if fields.get("http_status_code"):
            steps.append(f"确认 {service_name} 对应请求的 HTTP 状态码分布和失败比例。")
        if fields.get("trace_id"):
            steps.append(f"基于 trace/request id `{fields['trace_id']}` 串联上下游日志。")
        steps.extend(
            [
                f"检查 {service_name} 的最近发布、配置变更和资源水位。",
                "对照知识库检查超时、连接、鉴权或空指针等高频问题项。",
                "对同一时间窗口的错误日志进行聚类，确认是否为批量故障。",
            ]
        )
        for doc in documents[:2]:
            steps.append(f"参考知识库 `{doc.get('source', 'unknown')}` 中的处理建议。")
        return steps[:5]

    def _build_queries(self, fields: dict[str, Any]) -> list[str]:
        service = fields.get("service_name", "your-service")
        trace_id = fields.get("trace_id", "trace-or-request-id")
        exception_type = fields.get("exception_type", "Exception")

        return [
            f'Splunk-like: service="{service}" "{exception_type}" "{trace_id}"',
            f'CloudWatch-like: fields @timestamp, @message | filter @message like /{service}/ and @message like /{exception_type}/',
            f'K8s-like: kubectl logs deployment/{service} --since=30m | findstr "{trace_id}"',
        ]

    def _estimate_confidence(
        self,
        fields: dict[str, Any],
        documents: list[dict[str, Any]],
    ) -> float:
        score = 0.45
        for key in ["timestamp", "log_level", "service_name", "trace_id", "exception_type", "error_message"]:
            if fields.get(key):
                score += 0.05
        if fields.get("http_status_code"):
            score += 0.05
        if documents:
            score += min(0.15, len(documents) * 0.03)
        return round(min(score, 0.95), 2)

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
        knowledge_lines = [
            f"- `{doc.get('source', 'unknown')}`: {doc.get('content', '')[:180].strip()}..."
            for doc in documents
        ] or ["- 暂无相关知识片段"]

        case_lines = [
            f"- `{case.get('case_id')}` | {case.get('diagnosis_summary', '')}"
            for case in related_cases
        ] or ["- 暂无相似历史案例"]

        return f"""
## Problem Summary
{summary}

## Key Log Evidence
- Exception Type: `{fields.get("exception_type", "N/A")}`
- Error Message: `{fields.get("error_message", "N/A")}`
- Service Name: `{fields.get("service_name", "N/A")}`
- Trace ID: `{fields.get("trace_id", "N/A")}`
- HTTP Status Code: `{fields.get("http_status_code", "N/A")}`

## Extracted Fields
```json
{json.dumps(fields, ensure_ascii=False, indent=2)}
```

## Possible Root Causes
{chr(10).join(f"- {item}" for item in root_causes)}

## Recommended Troubleshooting Steps
{chr(10).join(f"- {item}" for item in troubleshooting_steps)}

## Suggested Splunk-like / CloudWatch-like / K8s-like Generic Queries
{chr(10).join(f"- {item}" for item in suggested_queries)}

## Retrieved Knowledge
{chr(10).join(knowledge_lines)}

## Related Historical Cases
{chr(10).join(case_lines)}

## Confidence Score
`{confidence_score}`
""".strip()
