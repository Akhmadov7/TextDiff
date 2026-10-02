"""REST API на Django Ninja. Swagger UI: /api/docs.

Доступ (ADR-005): весь API — только для вошедших пользователей (django_auth,
сессионная аутентификация). Анонимный запрос -> 401. Каждый пользователь видит
и может получить только свои задачи (owner=request.user) -> чужая задача = 404.
"""
from typing import Any

from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema
from ninja.responses import Status
from ninja.security import django_auth

from core.schemas import TextDiffParams
from web import services
from web.models import Task

api = NinjaAPI(
    title="TextDiff API",
    version="1.0",
    description=(
        "TextDiff: сравнение двух групп текстов по лексике. Загрузите тексты с меткой группы, "
        "получите метрики (длина, TTR, длина слова, частые слова) и p-value теста о различии групп. "
        "Подробное описание: docs/api.md."
    ),
    auth=django_auth,  # весь API только после входа; аноним получает 401
)


class TaskIn(Schema):
    name: str
    params: dict[str, Any]


class TaskOut(Schema):
    id: int
    name: str
    status: str
    core_version: str
    error: str


class ResultOut(Schema):
    id: int
    status: str
    result: dict[str, Any] | None


class ErrorOut(Schema):
    detail: str


@api.post("/tasks", response={202: TaskOut, 422: ErrorOut}, summary="Создать задачу")
def create_task(request, payload: TaskIn):
    try:
        validated = TextDiffParams.model_validate(payload.params)
    except Exception as exc:  # noqa: BLE001
        return Status(422, {"detail": str(exc)})
    owner = request.user  # django_auth гарантирует, что сюда анонимный пользователь не попадёт
    task = services.create_task(payload.name, validated.model_dump(), owner=owner)
    return Status(202, task)


@api.get("/tasks", response=list[TaskOut], summary="Список своих задач")
def list_tasks(request, status: str | None = None):
    qs = Task.objects.filter(owner=request.user)
    if status:
        qs = qs.filter(status=status)
    return qs[:100]


@api.get("/tasks/{task_id}", response=TaskOut, summary="Статус своей задачи")
def get_task(request, task_id: int):
    return get_object_or_404(Task, pk=task_id, owner=request.user)


@api.get("/tasks/{task_id}/result", response={200: ResultOut, 409: ErrorOut}, summary="Результат своей задачи")
def get_result(request, task_id: int):
    task = get_object_or_404(Task, pk=task_id, owner=request.user)
    if task.status != Task.Status.DONE:
        return Status(409, {"detail": f"Задача ещё не завершена: статус {task.status}"})
    return Status(200, task)
