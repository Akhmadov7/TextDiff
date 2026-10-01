import time

from django.contrib.auth.models import User

from web.models import Task


def login_new_user(client, username: str = "user", password: str = "test-pass-12345") -> User:
    """Создаёт нового пользователя и логинит его в client (ADR-005: доступ только для вошедших)."""
    user = User.objects.create_user(username=username, password=password)
    client.force_login(user)
    return user


def wait_until_finished(task_id: int, timeout: float = 10.0) -> Task:
    """Расчёт идёт в потоке (ADR-004): ждём, пока статус станет done или failed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = Task.objects.get(pk=task_id)
        if task.status in (Task.Status.DONE, Task.Status.FAILED):
            return task
        time.sleep(0.05)
    raise AssertionError(f"Задача {task_id} не завершилась за {timeout} c")
