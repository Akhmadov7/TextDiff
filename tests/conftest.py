import pytest


@pytest.fixture(autouse=True)
def _tasks_without_thread_and_tmp_media(settings, tmp_path):
    """Тесты считают задачи сразу, без фонового потока, и пишут входные CSV во временную папку.

    С потоком тест и поток одновременно работали с базой, и сценарные тесты изредка падали (ADR-004).
    Что `create_task` действительно запускает поток, проверяет отдельный тест в tests/test_services.py.
    """
    settings.TASKS_SYNC = True
    settings.MEDIA_ROOT = tmp_path / "media"
