"""Вычислительное ядро TextDiff. Не зависит от Django, HTTP или БД."""
import math
import re
from collections import Counter
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
    if len(group_names) == 2:
        first, second = (ttr_by_group[group_names[0]], ttr_by_group[group_names[1]])
        if validated.test == "ttest":
            statistic, pvalue = stats.ttest_ind(first, second, equal_var=False)
        else:
            statistic, pvalue = stats.mannwhitneyu(first, second, alternative="two-sided")
        statistic, pvalue = float(statistic), float(pvalue)
        # При одинаковых выборках различия отсутствуют по определению. Некоторые версии
        # SciPy возвращают NaN для полностью связанных рангов, поэтому фиксируем p-value.
        if sorted(first) == sorted(second):
            pvalue = 1.0
        # при полностью совпадающих значениях в группах (все TTR равны) scipy
        # возвращает NaN — это не число и не проходит JSON_VALID в SQLite при
        # сохранении в JSONField, поэтому явно превращаем в null
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
    ).model_dump()
    result["core_version"] = VERSION
    result["elapsed_sec"] = round(elapsed, 4)
    return result
