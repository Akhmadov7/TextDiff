import pytest
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.mark.django_db
def test_user_creates_task_via_form_and_sees_result(client):
    csv_data = "text,group\nхороший текст,A\nещё хороший,A\nплохой текст,B\nдругой плохой,B\n"
    response = client.post(
        "/tasks/new/",
        {
            "name": "demo",
            "file": SimpleUploadedFile("texts.csv", csv_data.encode("utf-8"), content_type="text/csv"),
            "text_col": "text",
            "group_col": "group",
            "test": "mannwhitney",
            "top_n": 10,
            "n_permutations": 1000,
            "seed": 0,
        },
    )
    assert response.status_code == 302
    page = client.get(response.headers["Location"])
    assert page.status_code == 200
    assert "Готово" in page.content.decode()


@pytest.mark.django_db
def test_user_creates_task_with_permutation_test(client):
    csv_data = "text,group\nхороший текст,A\nещё хороший,A\nплохой текст,B\nдругой плохой,B\n"
    response = client.post(
        "/tasks/new/",
        {
            "name": "demo-permutation",
            "file": SimpleUploadedFile("texts.csv", csv_data.encode("utf-8"), content_type="text/csv"),
            "text_col": "text",
            "group_col": "group",
            "test": "permutation",
            "top_n": 10,
            "n_permutations": 1000,
            "seed": 0,
        },
    )
    assert response.status_code == 302
    page = client.get(response.headers["Location"])
    assert "Перестановок использовано" in page.content.decode()
