from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class DiagnosisRequest(BaseModel):
    """创建日志诊断任务的请求参数。"""

    service_name: str = Field(
        min_length=1,
        description="需要诊断的服务名称。",
        examples=["mock-transfer-api"],
    )

    level: str = Field(
        default="ERROR",
        description="日志级别，例如 ERROR 或 WARN。",
    )

    trace_id: str = Field(
        default="",
        description="用于关联一次请求的 Trace ID。",
    )

    keyword: str = Field(
        default="",
        description="异常类型或错误关键字。",
    )

    lookback_minutes: int = Field(
        default=60,
        ge=1,
        le=10080,
        description="向前查询多少分钟，最大为 7 天。",
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="最多从 Loki 返回多少条日志。",
    )


class DiagnosisResponse(BaseModel):
    """日志诊断成功后的响应。"""

    success: bool
    error: str
    logql_query: str
    log_count: int
    report_markdown: str
    parsed_result: dict[str, Any]
    agent_trace: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """服务健康检查响应。"""

    status: str
    service: str


class TraceDiagnosisTaskRequest(BaseModel):
    """提交 Trace 异步诊断任务时使用的请求参数。"""

    trace_id: str = Field(
        min_length=1,
        description="需要诊断的 Trace ID。",
        examples=["trace-multi-002"],
    )
    lookback_minutes: int = Field(
        default=60,
        ge=1,
        le=10080,
        description="向前查询多少分钟。",
    )
    limit: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="最多从 Loki 返回多少条日志。",
    )
    project_id: str = Field(
        default="log-agent-demo",
        min_length=1,
        description="任务所属项目，用于后续记忆隔离。",
    )
    environment: str = Field(
        default="local",
        min_length=1,
        description="日志环境，例如 local、test 或 prod。",
    )


class DiagnosisTaskCreatedResponse(BaseModel):
    """任务创建成功后立即返回的取件凭证。"""

    task_id: str
    status: str
    created_at: str


class DiagnosisTaskResponse(BaseModel):
    """异步诊断任务的当前状态和结果。"""

    task_id: str
    status: str
    request_data: dict[str, Any]
    result: dict[str, Any]
    error: str
    created_at: str
    updated_at: str
