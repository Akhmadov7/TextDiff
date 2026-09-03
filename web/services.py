"""Сервисный слой между Django views/API и чистым вычислительным ядром."""
import csv
import io

from django.conf import settings
from django.utils import timezone

from core import VERSION, run
from core.schemas import TextDiffParams
from web.models import Task


def parse_csv_file(uploaded_file, text_col: str, group_col: str) -> list[dict]:
    raw = uploaded_file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV должен быть сохранён в UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV-файл пустой или не содержит заголовков")
    if text_col not in reader.fieldnames or group_col not in reader.fieldnames:
        raise ValueError(
            f"В CSV не найдены колонки '{text_col}' и/или '{group_col}'. "
            f"Найдены: {', '.join(reader.fieldnames)}"
        )

    rows = []
    for row_number, row in enumerate(reader, start=2):
        text_value = (row.get(text_col) or "").strip()
        group_value = (row.get(group_col) or "").strip()
        if not text_value or not group_value:
            raise ValueError(f"Строка {row_number}: текст и группа не должны быть пустыми")
        rows.append({"text": text_value, "group": group_value})

    if len(rows) < 2:
        raise ValueError("Нужно минимум 2 строки данных")
    return rows


def create_task(name: str, params: dict, owner=None) -> Task:
    validated = TextDiffParams.model_validate(params)
    task = Task.objects.create(name=name, params=validated.model_dump(), owner=owner)
    if settings.USE_QUEUE:
        from web.jobs import enqueue_task

        enqueue_task(task.pk)
    else:
        execute_task(task.pk)
        task.refresh_from_db()
    return task


def execute_task(task_id: int) -> None:
    task = Task.objects.get(pk=task_id)
    task.status = Task.Status.RUNNING
    task.save(update_fields=["status"])
    try:
        validated = TextDiffParams.model_validate(task.params)
        result = run(validated.model_dump())
        task.result = result
        task.core_version = result.get("core_version", VERSION)
        task.error = ""
        task.status = Task.Status.DONE
    except Exception as exc:  # noqa: BLE001
        task.error = str(exc)
        task.status = Task.Status.FAILED
    task.finished_at = timezone.now()
    task.save()
