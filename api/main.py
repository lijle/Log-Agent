from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from api.report_view import (
    build_error_html,
    build_pending_html,
    build_report_html,
)
from api.schemas import (
    DiagnosisRequest,
    DiagnosisResponse,
    DiagnosisTaskCreatedResponse,
    DiagnosisTaskResponse,
    HealthResponse,
    TraceDiagnosisTaskRequest,
)
from services.diagnosis_task_service import DiagnosisTaskService
from services.diagnosis_task_store import DiagnosisTaskStore
from services.loki_diagnosis_service import LokiDiagnosisService


app = FastAPI(
    title="Log Diagnosis Agent API",
    description=(
        "从 Loki 查询业务日志，并通过 LangGraph Agent "
        "生成结构化故障诊断报告。"
    ),
    version="1.1.0",
)

# API 进程复用同一套服务。任务执行由线程池负责，HTTP 请求无需等待 Agent 完成。
diagnosis_service = LokiDiagnosisService()
diagnosis_task_store = DiagnosisTaskStore()
diagnosis_task_service = DiagnosisTaskService(
    task_store=diagnosis_task_store,
    diagnosis_service=diagnosis_service,
    max_workers=2,
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["系统"],
)
def health_check() -> HealthResponse:
    """检查 Log Agent API 是否正常运行。"""
    return HealthResponse(
        status="UP",
        service="log-diagnosis-agent",
    )


@app.post(
    "/api/v1/diagnoses",
    response_model=DiagnosisResponse,
    tags=["同步日志诊断"],
)
def create_diagnosis(
    request: DiagnosisRequest,
) -> DiagnosisResponse:
    """同步查询 Loki 并生成报告，保留用于调试和兼容旧调用。"""
    service_result = diagnosis_service.diagnose(
        service_name=request.service_name,
        level=request.level,
        trace_id=request.trace_id,
        keyword=request.keyword,
        lookback_minutes=request.lookback_minutes,
        limit=request.limit,
    )

    if not service_result.get("success"):
        error_message = str(
            service_result.get("error", "日志诊断失败。")
        )
        raise HTTPException(
            status_code=502,
            detail=error_message,
        )

    loki_result = service_result.get("loki_result", {})
    diagnosis_result = service_result.get("diagnosis_result", {})

    return DiagnosisResponse(
        success=True,
        error="",
        logql_query=service_result.get("logql_query", ""),
        log_count=loki_result.get("total", 0),
        report_markdown=diagnosis_result.get("report_markdown", ""),
        parsed_result=diagnosis_result.get("parsed_result", {}),
        agent_trace=diagnosis_result.get("trace", []),
    )


@app.post(
    "/api/v1/diagnosis-tasks",
    response_model=DiagnosisTaskCreatedResponse,
    status_code=202,
    tags=["异步日志诊断"],
)
def create_trace_diagnosis_task(
    request: TraceDiagnosisTaskRequest,
) -> DiagnosisTaskCreatedResponse:
    """提交跨服务 Trace 诊断，并立即返回 task_id。"""
    task = diagnosis_task_service.submit_trace_diagnosis(
        trace_id=request.trace_id,
        lookback_minutes=request.lookback_minutes,
        limit=request.limit,
        project_id=request.project_id,
        environment=request.environment,
    )

    return DiagnosisTaskCreatedResponse(
        task_id=task["task_id"],
        status=task["status"],
        created_at=task["created_at"],
    )


@app.get(
    "/api/v1/diagnosis-tasks/{task_id}",
    response_model=DiagnosisTaskResponse,
    tags=["异步日志诊断"],
)
def get_diagnosis_task(
    task_id: str,
) -> DiagnosisTaskResponse:
    """根据 task_id 查询任务进度、结果或错误原因。"""
    task = diagnosis_task_service.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="诊断任务不存在。",
        )

    return DiagnosisTaskResponse(**task)


@app.get(
    "/diagnoses/view",
    response_class=HTMLResponse,
    tags=["日志诊断页面"],
)
def start_diagnosis_report(
    trace_id: str = Query(
        min_length=1,
        description="Trace ID。",
    ),
    lookback_minutes: int = Query(
        default=60,
        ge=1,
        le=10080,
        description="向前查询多少分钟。",
    ),
) -> RedirectResponse:
    """创建异步诊断任务，并跳转到该任务的报告页面。"""
    task = diagnosis_task_service.submit_trace_diagnosis(
        trace_id=trace_id,
        lookback_minutes=lookback_minutes,
        limit=200,
    )
    task_id = task["task_id"]

    return RedirectResponse(
        url=f"/diagnoses/tasks/{task_id}/view",
        status_code=303,
    )


@app.get(
    "/diagnoses/tasks/{task_id}/view",
    response_class=HTMLResponse,
    tags=["日志诊断页面"],
)
def view_diagnosis_task_report(
    task_id: str,
) -> HTMLResponse:
    """显示任务进度；任务成功后显示最终诊断报告。"""
    task = diagnosis_task_service.get_task(task_id)

    if task is None:
        return HTMLResponse(
            content=build_error_html("诊断任务不存在。"),
            status_code=404,
        )

    status = task["status"]

    if status in {"PENDING", "RUNNING"}:
        return HTMLResponse(
            content=build_pending_html(
                task_id=task_id,
                status=status,
            ),
            status_code=200,
        )

    if status == "FAILED":
        return HTMLResponse(
            content=build_error_html(task["error"]),
            status_code=502,
        )

    service_result = task["result"]
    diagnosis_result = service_result.get("diagnosis_result", {})
    service_names = service_result.get("service_names", [])

    if service_names:
        service_name_text = ", ".join(service_names)
    else:
        service_name_text = "未识别服务"

    page_html = build_report_html(
        service_name=service_name_text,
        trace_id=task["request_data"].get("trace_id", ""),
        logql_query=service_result.get("logql_query", ""),
        report_markdown=diagnosis_result.get("report_markdown", ""),
    )

    return HTMLResponse(
        content=page_html,
        status_code=200,
    )
