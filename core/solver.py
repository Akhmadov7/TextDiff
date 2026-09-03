"""Вычислительное ядро TextDiff. Не зависит от Django, HTTP или БД."""
import re
from collections import Counter
from time import perf_counter

from scipy import stats

from core.schemas import TextDiffParams, TextDiffResult

VERSION = "0.1.0"
WORD_RE = re.compile(r"[а-яa-zё]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _text_stats(text: str) -> tuple[int, float, float]:
    words = _tokenize(text)
    count = len(words)
    if count == 0:
        return 0, 0.0, 0.0
    ttr = len(set(words)) / count
    avg_word_len = sum(len(word) for word in words) / count
    return count, ttr, avg_word_len


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
        ttr = len(set(tokenized)) / count if count else 0.0
        avg_word_len = sum(map(len, tokenized)) / count if count else 0.0
        words.update(tokenized)
        bucket = by_group.setdefault(row.group, {"n": [], "ttr": [], "avg_len": []})
        bucket["n"].append(count)
        bucket["ttr"].append(ttr)
        bucket["avg_len"].append(avg_word_len)
        ttr_by_group.setdefault(row.group, []).append(ttr)

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
