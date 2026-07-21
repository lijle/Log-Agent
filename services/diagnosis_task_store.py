from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any


class DiagnosisTaskStatus(str, Enum):
    """诊断任务可能处于的状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class DiagnosisTask:
    """保存一次异步诊断任务的输入、状态和结果。"""

    task_id: str
    status: DiagnosisTaskStatus
    request_data: dict[str, Any]
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """将任务对象转换成可以返回给 API 的字典。"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "request_data": self.request_data,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DiagnosisTaskStore:
    """使用线程锁保护的内存任务仓库。"""

    def __init__(self) -> None:
        """初始化空任务字典和线程锁。"""
        self._tasks: dict[str, DiagnosisTask] = {}
        self._lock = Lock()

    def create_task(
        self,
        request_data: dict[str, Any],
    ) -> dict[str, Any]:
        """创建 PENDING 任务并返回任务快照。"""
        task_id = str(uuid.uuid4())
        current_time = self._current_time()

        task = DiagnosisTask(
            task_id=task_id,
            status=DiagnosisTaskStatus.PENDING,
            request_data=request_data,
            created_at=current_time,
            updated_at=current_time,
        )

        with self._lock:
            self._tasks[task_id] = task

        return copy.deepcopy(task.to_dict())

    def get_task(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        """根据 task_id 返回任务快照，找不到时返回 None。"""
        with self._lock:
            task = self._tasks.get(task_id)

            if task is None:
                return None

            return copy.deepcopy(task.to_dict())

    def mark_running(
        self,
        task_id: str,
    ) -> bool:
        """将非终态任务修改为 RUNNING。"""
        with self._lock:
            task = self._tasks.get(task_id)

            if task is None or self._is_terminal(task.status):
                return False

            task.updated_at = self._current_time()
            task.status = DiagnosisTaskStatus.RUNNING
            return True

    def mark_succeeded(
        self,
        task_id: str,
        result: dict[str, Any],
    ) -> bool:
        """保存完整诊断结果，并将任务修改为 SUCCEEDED。"""
        with self._lock:
            task = self._tasks.get(task_id)

            if task is None or self._is_terminal(task.status):
                return False

            task.result = result
            task.error = ""
            task.updated_at = self._current_time()
            # 状态最后更新，相当于确认前面的结果已经全部写入。
            task.status = DiagnosisTaskStatus.SUCCEEDED
            return True

    def mark_failed(
        self,
        task_id: str,
        error: str,
    ) -> bool:
        """保存失败原因，并将任务修改为 FAILED。"""
        with self._lock:
            task = self._tasks.get(task_id)

            if task is None or self._is_terminal(task.status):
                return False

            task.result = {}
            task.error = error
            task.updated_at = self._current_time()
            task.status = DiagnosisTaskStatus.FAILED
            return True

    def _is_terminal(
        self,
        status: DiagnosisTaskStatus,
    ) -> bool:
        """判断任务是否已经进入不可再次覆盖的最终状态。"""
        return status in {
            DiagnosisTaskStatus.SUCCEEDED,
            DiagnosisTaskStatus.FAILED,
        }

    def _current_time(self) -> str:
        """生成 UTC ISO 格式时间。"""
        return datetime.now(timezone.utc).isoformat()
