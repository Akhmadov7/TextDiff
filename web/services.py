"""Сервисный слой между Django views/API и чистым вычислительным ядром."""
import csv
import io
import threading
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from core import VERSION, run
from core.schemas import TextDiffParams
from web.models import Task

INPUT_DIR = "inputs"  # подпапка MEDIA_ROOT, куда кладутся входные CSV задач (ADR-006)

# Текст по схеме — до 200 000 символов, а стандартный предел модуля csv — 131 072 символа в ячейке.
csv.field_size_limit(1_000_000)


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


def save_input_file(task_id: int, rows: list[dict]) -> str:
    """Кладёт входной CSV задачи на диск и возвращает путь относительно MEDIA_ROOT — его и хранит база."""
    relative = f"{INPUT_DIR}/task_{task_id}.csv"
    full = Path(settings.MEDIA_ROOT) / relative
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["text", "group"])
        writer.writeheader()
        writer.writerows(rows)
    return relative


def load_input_rows(relative_path: str) -> list[dict]:
    """Читает входной CSV задачи по пути из базы. Путь обязан вести внутрь MEDIA_ROOT/inputs/."""
    base = (Path(settings.MEDIA_ROOT) / INPUT_DIR).resolve()
    full = (Path(settings.MEDIA_ROOT) / relative_path).resolve()
    if base not in full.parents:
        raise ValueError(f"Входной файл должен лежать в папке {INPUT_DIR}/ внутри MEDIA_ROOT")
    if not full.is_file():
        raise ValueError(f"Входной файл задачи не найден: {relative_path}")
    with full.open("r", encoding="utf-8", newline="") as file:
        return [{"text": row["text"], "group": row["group"]} for row in csv.DictReader(file)]


def _core_params(params: dict) -> dict:
    """Собирает вход для ядра: строки берутся из файла. Старые задачи (rows прямо в params) тоже работают."""
    core_params = dict(params)
    input_file = core_params.pop("input_file", None)
    core_params.pop("n_rows", None)
    if input_file:
        core_params["rows"] = load_input_rows(input_file)
    return core_params


def create_task(name: str, params: dict, owner=None) -> Task:
    validated = TextDiffParams.model_validate(params)
    settings_only = validated.model_dump()
    rows = settings_only.pop("rows")  # CSV в базу не кладём: в params остаются настройки и путь к файлу
    task = Task.objects.create(name=name, params=settings_only, owner=owner)
    try:
        task.params["input_file"] = save_input_file(task.pk, rows)
        task.params["n_rows"] = len(rows)
        task.save(update_fields=["params"])
    except OSError as exc:
        task.delete()
        raise ValueError(f"Не удалось сохранить входной файл: {exc}") from exc
    if settings.USE_QUEUE:
        from web.jobs import enqueue_task

        enqueue_task(task.pk)
    elif settings.TASKS_SYNC:
        execute_task(task.pk)  # только для тестов: без потока тест не делит базу с фоновым потоком
    else:
        # ADR-004: расчёт в потоке — запрос отвечает сразу, статус меняется сам
        threading.Thread(target=_execute_in_thread, args=(task.pk,), daemon=True).start()
    return task


def _execute_in_thread(task_id: int) -> None:
    try:
        execute_task(task_id)
    finally:
        connection.close()  # у потока своё подключение к БД — закрываем, когда закончили


def execute_task(task_id: int) -> None:
    task = Task.objects.get(pk=task_id)
    task.status = Task.Status.RUNNING
    task.save(update_fields=["status"])
    try:
        validated = TextDiffParams.model_validate(_core_params(task.params))
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
