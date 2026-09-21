"""Вычислительное ядро TextDiff. Не зависит от Django, HTTP или БД."""
import itertools
import math
import random
import re
from collections import Counter
from math import comb
from time import perf_counter

from scipy import stats

from core.schemas import TextDiffParams, TextDiffResult

VERSION = "0.1.0"
WORD_RE = re.compile(r"[а-яa-zё]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def ttr(text: str) -> float:
    """Type-token ratio: число уникальных слов, делённое на число всех слов."""
    words = _tokenize(text)
    return len(set(words)) / len(words) if words else 0.0


def _text_stats(text: str) -> tuple[int, float, float]:
    words = _tokenize(text)
    count = len(words)
    if count == 0:
        return 0, 0.0, 0.0
    text_ttr = ttr(text)
    avg_word_len = sum(len(word) for word in words) / count
    return count, text_ttr, avg_word_len


def permutation_test(group_a: list[float], group_b: list[float], n_permutations: int, seed: int) -> dict:
    """Перестановочный тест: [1,1] vs [3,3] -> pvalue == 2/6 (см. тесты)."""
    pooled = list(group_a) + list(group_b)
    n, na = len(pooled), len(group_a)
    observed = abs(sum(group_a) / na - sum(group_b) / (n - na))

    total = comb(n, na)
    if total <= n_permutations:
        diffs = []
        for idx in itertools.combinations(range(n), na):
            idx_set = set(idx)
            a = [pooled[i] for i in idx_set]
            b = [pooled[i] for i in range(n) if i not in idx_set]
            diffs.append(abs(sum(a) / na - sum(b) / (n - na)))
        used, exact = total, True
    else:
        rng = random.Random(seed)
        diffs = []
        for _ in range(n_permutations):
            shuffled = pooled[:]
            rng.shuffle(shuffled)
            a, b = shuffled[:na], shuffled[na:]
            diffs.append(abs(sum(a) / na - sum(b) / (n - na)))
        used, exact = n_permutations, False

    at_least = sum(1 for d in diffs if d >= observed - 1e-9)
    return {"statistic": observed, "pvalue": at_least / used, "used": used, "exact": exact}


def run(params: dict) -> dict:
    """Единственная точка входа ядра. Валидирует вход и возвращает JSON-совместимый dict."""
    validated = TextDiffParams.model_validate(params)
    started = perf_counter()

    by_group: dict[str, dict[str, list[float]]] = {}
    ttr_by_group: dict[str, list[float]] = {}
    words = Counter()

    for row in validated.rows:
        tokenized = _tokenize(row.text)
        count = len(tokenized)
        row_ttr = ttr(row.text)
        avg_word_len = sum(map(len, tokenized)) / count if count else 0.0
        words.update(tokenized)
        bucket = by_group.setdefault(row.group, {"n": [], "ttr": [], "avg_len": []})
        bucket["n"].append(count)
        bucket["ttr"].append(row_ttr)
        bucket["avg_len"].append(avg_word_len)
        ttr_by_group.setdefault(row.group, []).append(row_ttr)

    groups = {}
    for group, values in by_group.items():
        count = len(values["n"])
        groups[group] = {
            "n_texts": count,
            "avg_len_words": sum(values["n"]) / count,
            "avg_ttr": sum(values["ttr"]) / count,
            "avg_word_len": sum(values["avg_len"]) / count,
        }

    group_names = list(ttr_by_group)
    statistic = pvalue = None
    perm_used = perm_exact = None
    if len(group_names) == 2:
        first, second = (ttr_by_group[group_names[0]], ttr_by_group[group_names[1]])
        if validated.test == "permutation":
            perm = permutation_test(first, second, validated.n_permutations, validated.seed)
            statistic, pvalue = perm["statistic"], perm["pvalue"]
            perm_used, perm_exact = perm["used"], perm["exact"]
        else:
            if validated.test == "ttest":
                statistic, pvalue = stats.ttest_ind(first, second, equal_var=False)
            else:
                statistic, pvalue = stats.mannwhitneyu(first, second, alternative="two-sided")
            statistic, pvalue = float(statistic), float(pvalue)
            if sorted(first) == sorted(second):
                pvalue = 1.0
            if math.isnan(statistic) or math.isinf(statistic):
                statistic = None
            if math.isnan(pvalue) or math.isinf(pvalue):
                pvalue = None

    elapsed = perf_counter() - started
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
    result["elapsed_sec"] = round(elapsed, 4)
    return result
