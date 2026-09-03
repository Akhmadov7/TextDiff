import pytest

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


@pytest.mark.django_db
def test_create_task_returns_202_and_computes(client):
    response = client.post("/api/tasks", {"name": "t", "params": params()}, content_type="application/json")
    assert response.status_code == 202
    task_id = response.json()["id"]
    result_response = client.get(f"/api/tasks/{task_id}/result")
    assert result_response.status_code == 200
    assert result_response.json()["result"]["n_texts"] == 4


@pytest.mark.django_db
def test_bad_params_are_rejected_with_422(client):
    bad = params()
    bad["test"] = "eval"
    response = client.post("/api/tasks", {"name": "bad", "params": bad}, content_type="application/json")
    assert response.status_code == 422
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_list_and_status(client):
    client.post("/api/tasks", {"name": "x", "params": params()}, content_type="application/json")
    assert len(client.get("/api/tasks").json()) == 1
    assert client.get("/api/tasks?status=done").json()[0]["status"] == "done"
    assert client.get("/api/tasks/999").status_code == 404
