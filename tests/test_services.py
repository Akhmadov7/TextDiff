import json
import types
from pathlib import Path

import pytest

from web import services
from web.models import Task


def make_params(n_per_group: int = 2) -> dict:
    rows = []
    for i in range(n_per_group):
        rows.append({"text": f"хороший текст номер {i}", "group": "A"})
        rows.append({"text": f"плохой пример другой {i}", "group": "B"})
    return {"rows": rows, "test": "mannwhitney", "top_n": 5}


# --- CSV в файл, а не в базу (ADR-006) -----------------------------------------------------------------------


@pytest.mark.django_db
def test_csv_is_stored_in_file_and_db_keeps_only_path(settings):
    task = services.create_task("файл", make_params(1000), owner=None)
    task.refresh_from_db()

    assert "rows" not in task.params
    assert task.params["input_file"] == f"inputs/task_{task.pk}.csv"
    assert task.params["n_rows"] == 2000
    assert len(json.dumps(task.params)) < 1000  # в базе — настройки и путь, а не сам CSV

    lines = (Path(settings.MEDIA_ROOT) / task.params["input_file"]).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "text,group"
    assert len(lines) == 2001

    assert task.status == Task.Status.DONE  # расчёт прочитал строки из файла
    assert task.result["n_texts"] == 2000


def test_csv_file_roundtrip_keeps_commas_quotes_and_newlines():
    rows = [
        {"text": 'слово, "цитата"\nвторая строка', "group": "A"},
        {"text": "ещё текст", "group": "B"},
    ]
    relative = services.save_input_file(7, rows)
    assert services.load_input_rows(relative) == rows


@pytest.mark.django_db
def test_old_task_with_rows_inside_params_still_runs():
    task = Task.objects.create(name="старая", params=make_params())
    services.execute_task(task.pk)
    task.refresh_from_db()
    assert task.status == Task.Status.DONE


@pytest.mark.django_db
def test_missing_input_file_marks_task_failed(settings):
    task = services.create_task("пропал файл", make_params(), owner=None)
    (Path(settings.MEDIA_ROOT) / task.params["input_file"]).unlink()

    services.execute_task(task.pk)
    task.refresh_from_db()
    assert task.status == Task.Status.FAILED
    assert "не найден" in task.error


@pytest.mark.django_db
def test_input_path_outside_inputs_folder_is_rejected(settings):
    secret = Path(settings.MEDIA_ROOT) / "secret.csv"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("text,group\nа б,A\nв г,B\n", encoding="utf-8")
    task = Task.objects.create(name="обход папки", params={"input_file": "inputs/../secret.csv", "test": "ttest"})

    services.execute_task(task.pk)
    task.refresh_from_db()
    assert task.status == Task.Status.FAILED
    assert "inputs" in task.error


# --- фоновый поток (ADR-004) ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_without_sync_flag_calculation_goes_to_background_thread(settings, monkeypatch):
    settings.TASKS_SYNC = False
    settings.USE_QUEUE = False
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            started.append({"target": target, "args": args, "daemon": daemon})

        def start(self):
            started.append("start")

    monkeypatch.setattr(services, "threading", types.SimpleNamespace(Thread=FakeThread))
    task = services.create_task("фон", make_params(), owner=None)
    task.refresh_from_db()

    assert task.status == Task.Status.CREATED  # запрос не ждёт расчёта
    assert started[0]["target"] is services._execute_in_thread
    assert started[0]["args"] == (task.pk,)
    assert started[0]["daemon"] is True
    assert started[1] == "start"
