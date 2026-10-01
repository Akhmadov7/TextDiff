import pytest
from django.test import Client

from tests.utils import login_new_user, wait_until_finished
from web.models import Task


def params():
    return {
        "rows": [
            {"text": "хороший текст хороший", "group": "A"},
            {"text": "хороший пример", "group": "A"},
            {"text": "плохой текст другой", "group": "B"},
            {"text": "другой плохой", "group": "B"},
        ],
        "test": "mannwhitney",
        "top_n": 10,
    }


@pytest.mark.django_db(transaction=True)  # расчёт идёт в потоке (ADR-004)
def test_create_task_returns_202_and_computes(client):
    login_new_user(client)
    response = client.post("/api/tasks", {"name": "t", "params": params()}, content_type="application/json")
    assert response.status_code == 202
    task_id = response.json()["id"]
    wait_until_finished(task_id)
    result_response = client.get(f"/api/tasks/{task_id}/result")
    assert result_response.status_code == 200
    assert result_response.json()["result"]["n_texts"] == 4


@pytest.mark.django_db
def test_bad_params_are_rejected_with_422(client):
    login_new_user(client)
    bad = params()
    bad["test"] = "eval"
    response = client.post("/api/tasks", {"name": "bad", "params": bad}, content_type="application/json")
    assert response.status_code == 422
    assert Task.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_list_and_status(client):
    login_new_user(client)
    response = client.post("/api/tasks", {"name": "x", "params": params()}, content_type="application/json")
    wait_until_finished(response.json()["id"])
    assert len(client.get("/api/tasks").json()) == 1
    assert client.get("/api/tasks?status=done").json()[0]["status"] == "done"
    assert client.get("/api/tasks/999").status_code == 404


# --- плохой вход (пара 12): 422 и ни одной созданной задачи ---------------------------------------------------


@pytest.mark.django_db
def test_three_groups_are_rejected_with_422(client):
    login_new_user(client)
    bad = params()
    bad["rows"].append({"text": "третья группа текст", "group": "C"})
    response = client.post("/api/tasks", {"name": "bad", "params": bad}, content_type="application/json")
    assert response.status_code == 422
    assert "rows" in response.json()["detail"]
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_text_without_words_is_rejected_with_row_number(client):
    login_new_user(client)
    bad = params()
    bad["rows"][2]["text"] = "123 456 !!!"  # третья строка данных = строка 4 в CSV (первая — заголовок)
    response = client.post("/api/tasks", {"name": "bad", "params": bad}, content_type="application/json")
    assert response.status_code == 422
    assert "Строка 4" in response.json()["detail"]
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_too_big_input_is_rejected_with_422(client):
    login_new_user(client)
    big = params()
    big["test"] = "permutation"
    big["n_permutations"] = 200_000
    big["rows"] = [{"text": "a", "group": "A" if i % 2 else "B"} for i in range(50_000)]
    response = client.post("/api/tasks", {"name": "big", "params": big}, content_type="application/json")
    assert response.status_code == 422
    assert Task.objects.count() == 0


# --- доступ (пара 13): весь API только для вошедших, чужая задача = 404 ----------------------------------------


@pytest.mark.django_db
def test_anonymous_post_is_rejected_with_401(client):
    response = client.post("/api/tasks", {"name": "t", "params": params()}, content_type="application/json")
    assert response.status_code == 401
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_list_is_rejected_with_401(client):
    assert client.get("/api/tasks").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_user_does_not_see_others_task_via_api(client):
    login_new_user(client, username="user1")
    response = client.post("/api/tasks", {"name": "секрет A", "params": params()}, content_type="application/json")
    task_id = response.json()["id"]
    wait_until_finished(task_id)

    other_client = Client()
    login_new_user(other_client, username="user2")
    assert other_client.get(f"/api/tasks/{task_id}").status_code == 404
    assert other_client.get(f"/api/tasks/{task_id}/result").status_code == 404
    assert other_client.get("/api/tasks").json() == []
