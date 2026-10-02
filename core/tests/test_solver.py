import pytest
from pydantic import ValidationError

from core.solver import permutation_test, run, ttr


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


def test_ttr_by_definition():
    assert ttr("а а а а") == 0.25
    assert ttr("а б в г") == 1.0


def test_permutation_test_matches_known_example():
    # [1,1] и [3,3]: из 6 разбиений по 2+2 у двух разность средних >= 2 -> p=2/6
    result = permutation_test([1, 1], [3, 3], n_permutations=1000, seed=0)
    assert result["statistic"] == pytest.approx(2.0)
    assert result["pvalue"] == pytest.approx(2 / 6)
    assert result["exact"] is True


def test_sampled_pvalue_never_zero():
    # эталон: Phipson, Smyth (2010) — p >= 1 / (n + 1)
    result = permutation_test([1] * 10, [10] * 10, n_permutations=1000, seed=1)
    assert result["exact"] is False
    assert result["pvalue"] == 1 / 1001


def test_permutation_test_same_seed_is_reproducible():
    a, b = list(range(20)), list(range(20, 45))
    first = permutation_test(a, b, n_permutations=500, seed=42)
    second = permutation_test(a, b, n_permutations=500, seed=42)
    assert first["exact"] is False
    assert first == second


def test_permutation_test_wired_into_run():
    rows = [
        {"text": "кот кот кот кот", "group": "A"},
        {"text": "кот кот", "group": "A"},
        {"text": "дом окно улица небо", "group": "B"},
        {"text": "дом окно улица", "group": "B"},
    ]
    result = run({"rows": rows, "test": "permutation", "n_permutations": 1000, "seed": 0})
    assert result["test"] == "permutation"
    assert result["pvalue"] is not None
    assert result["permutations_used"] is not None


def test_identical_groups_show_no_difference():
    rows = [
        {"text": "кот сидел на окне", "group": "A"},
        {"text": "кот сидел на окне", "group": "B"},
        {"text": "шёл дождь весь день", "group": "A"},
        {"text": "шёл дождь весь день", "group": "B"},
    ]
    result = run({"rows": rows, "test": "mannwhitney"})
    assert result["pvalue"] >= 0.9


# --- ограничение метрики TTR (docs/architecture.md, разделы 7 и 12) -------------------------------------------

VOCABULARY = ["кот", "пёс", "дом", "лес", "река", "поле", "луг", "мост", "сад", "холм"]


def test_ttr_drops_when_text_gets_longer():
    short_text = " ".join(VOCABULARY)  # 10 слов, все разные
    long_text = " ".join(VOCABULARY * 5)  # тот же словарь, но 50 слов
    assert ttr(short_text) == 1.0
    assert ttr(long_text) == pytest.approx(10 / 50)


def test_groups_with_different_text_length_differ_in_ttr_even_with_same_vocabulary():
    rows = [
        {"text": " ".join(VOCABULARY), "group": "A"},
        {"text": " ".join(VOCABULARY), "group": "A"},
        {"text": " ".join(VOCABULARY * 5), "group": "B"},
        {"text": " ".join(VOCABULARY * 5), "group": "B"},
    ]
    result = run({"rows": rows, "test": "mannwhitney"})
    short_group, long_group = result["groups"]["A"], result["groups"]["B"]
    assert long_group["avg_len_words"] > short_group["avg_len_words"]
    assert long_group["avg_ttr"] < short_group["avg_ttr"]  # словарь один, а различие «есть»: виновата длина
