import pytest
from pydantic import ValidationError

from core.solver import run


def sample_params():
    return {
        "rows": [
            {"text": "хороший текст хороший пример", "group": "A"},
            {"text": "ещё хороший пример", "group": "A"},
            {"text": "плохой текст другой пример", "group": "B"},
            {"text": "другой плохой текст", "group": "B"},
        ],
        "test": "mannwhitney",
        "top_n": 5,
    }


def test_run_returns_groups_and_statistics():
    result = run(sample_params())
    assert result["n_texts"] == 4
    assert set(result["groups"]) == {"A", "B"}
    assert result["pvalue"] is not None
    assert result["core_version"] == "0.1.0"


def test_run_ttest():
    params = sample_params()
    params["test"] = "ttest"
    result = run(params)
    assert result["test"] == "ttest"
    assert result["statistic"] is not None


def test_validation_rejects_single_group():
    params = sample_params()
    params["rows"] = [{"text": "один текст", "group": "A"}, {"text": "второй текст", "group": "A"}]
    with pytest.raises(ValidationError):
        run(params)
