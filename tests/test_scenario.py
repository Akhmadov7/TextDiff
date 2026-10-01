import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from tests.utils import login_new_user, wait_until_finished
from web.models import Task

CSV_DATA = "text,group\nхороший текст,A\nещё хороший,A\nплохой текст,B\nдругой плохой,B\n"


def _upload(client, name="demo", test="mannwhitney"):
    return client.post(
        "/tasks/new/",
        {
            "name": name,
            "file": SimpleUploadedFile("texts.csv", CSV_DATA.encode("utf-8"), content_type="text/csv"),
            "text_col": "text",
            "group_col": "group",
            "test": test,
            "top_n": 10,
            "n_permutations": 1000,
            "seed": 0,
        },
    )


@pytest.mark.django_db(transaction=True)  # расчёт идёт в потоке (ADR-004)
def test_user_creates_task_via_form_and_sees_result(client):
    login_new_user(client)
    response = _upload(client, name="demo")
    assert response.status_code == 302
    wait_until_finished(int(response.headers["Location"].strip("/").split("/")[-1]))
    page = client.get(response.headers["Location"])
    assert page.status_code == 200
    assert "Готово" in page.content.decode()


@pytest.mark.django_db(transaction=True)  # расчёт идёт в потоке (ADR-004)
def test_user_creates_task_with_permutation_test(client):
    login_new_user(client)
    response = _upload(client, name="demo-permutation", test="permutation")
    assert response.status_code == 302
    wait_until_finished(int(response.headers["Location"].strip("/").split("/")[-1]))
    page = client.get(response.headers["Location"])
    assert "Перестановок использовано" in page.content.decode()


@pytest.mark.django_db(transaction=True)
def test_task_reaches_done_and_has_pvalue(client):
    # пара 15: отправили CSV -> задача дошла до «готово» -> в результате есть p-value
    login_new_user(client)
    response = _upload(client, name="done-check")
    task = wait_until_finished(int(response.headers["Location"].strip("/").split("/")[-1]))
    assert task.status == Task.Status.DONE
    assert task.result["pvalue"] is not None


# --- доступ (пара 13): вход обязателен, чужая задача = 404 -----------------------------------------------------


@pytest.mark.django_db
def test_anonymous_is_redirected_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/accounts/login/")


@pytest.mark.django_db(transaction=True)
def test_user_does_not_see_others_task_via_web(client):
    login_new_user(client, username="user1")
    response = _upload(client, name="секрет A")
    task_id = int(response.headers["Location"].strip("/").split("/")[-1])
    wait_until_finished(task_id)

    other_client = Client()
    login_new_user(other_client, username="user2")
    assert other_client.get(f"/tasks/{task_id}/").status_code == 404
    list_page = other_client.get("/").content.decode()
    assert "секрет A" not in list_page
