"""Вычислительное ядро TextDiff. Не зависит от Django, HTTP или БД."""
import itertools
import math
import random
from collections import Counter
from math import comb
from time import perf_counter

from scipy import stats

from core.schemas import WORD_RE, TextDiffParams, TextDiffResult

VERSION = "0.1.0"


def _tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def ttr(text: str) -> float:
    """Type-token ratio: число уникальных слов, делённое на число всех слов."""
    words = _tokenize(text)
    return len(set(words)) / len(words) if words else 0.0


def _mean_diff(a: list[float], b: list[float]) -> float:
    return abs(sum(a) / len(a) - sum(b) / len(b))


def permutation_test(group_a: list[float], group_b: list[float], n_permutations: int, seed: int) -> dict:
    """Перестановочный тест: [1,1] vs [3,3] -> pvalue == 2/6 (см. тесты)."""
    pooled = list(group_a) + list(group_b)
    na = len(group_a)
    observed = _mean_diff(group_a, group_b)

    total = comb(len(pooled), na)
    diffs = []
    if total <= n_permutations:
        for idx in itertools.combinations(range(len(pooled)), na):
            a = [pooled[i] for i in idx]
            b = [pooled[i] for i in range(len(pooled)) if i not in idx]
            diffs.append(_mean_diff(a, b))
        used, exact = total, True
    else:
        rng = random.Random(seed)
        for _ in range(n_permutations):
            shuffled = pooled[:]
            rng.shuffle(shuffled)
            diffs.append(_mean_diff(shuffled[:na], shuffled[na:]))
        used, exact = n_permutations, False

    at_least = sum(1 for d in diffs if d >= observed - 1e-9)
    pvalue = at_least / used if exact else (at_least + 1) / (used + 1)
    return {"statistic": observed, "pvalue": pvalue, "used": used, "exact": exact}


def _nan_to_none(value: float) -> float | None:
    return None if math.isnan(value) or math.isinf(value) else value


def run(params: dict) -> dict:
    """Единственная точка входа ядра. Валидирует вход и возвращает JSON-совместимый dict."""
    validated = TextDiffParams.model_validate(params)
    started = perf_counter()

    by_group: dict[str, dict[str, list[float]]] = {}
    words = Counter()

    for row in validated.rows:
        tokenized = _tokenize(row.text)
        count = len(tokenized)
        words.update(tokenized)
        bucket = by_group.setdefault(row.group, {"n": [], "ttr": [], "avg_len": []})
        bucket["n"].append(count)
        bucket["ttr"].append(len(set(tokenized)) / count)
        bucket["avg_len"].append(sum(map(len, tokenized)) / count)

    groups = {}
    for group, values in by_group.items():
        count = len(values["n"])
        groups[group] = {
            "n_texts": count,
            "avg_len_words": sum(values["n"]) / count,
            "avg_ttr": sum(values["ttr"]) / count,
            "avg_word_len": sum(values["avg_len"]) / count,
        }

    statistic = pvalue = None
    perm_used = perm_exact = None
    first, second = (values["ttr"] for values in by_group.values())
    if validated.test == "permutation":
        perm = permutation_test(first, second, validated.n_permutations, validated.seed)
        statistic, pvalue = perm["statistic"], perm["pvalue"]
        perm_used, perm_exact = perm["used"], perm["exact"]
    else:
        if validated.test == "ttest":
            statistic, pvalue = stats.ttest_ind(first, second, equal_var=False)
        else:
            statistic, pvalue = stats.mannwhitneyu(first, second, alternative="two-sided")
        if sorted(first) == sorted(second):
            pvalue = 1.0
        statistic, pvalue = _nan_to_none(float(statistic)), _nan_to_none(float(pvalue))

    result = TextDiffResult(
        n_texts=len(validated.rows),
        groups=groups,
        test=validated.test,
        statistic=statistic,
        pvalue=pvalue,
        top_words=words.most_common(validated.top_n),
        permutations_used=perm_used,
        permutations_exact=perm_exact,
    ).model_dump()
    result["core_version"] = VERSION
    result["elapsed_sec"] = round(perf_counter() - started, 4)
    return result
