"""Замер времени расчёта: python measure.py. Результат — таблица «текстов → секунды» для README."""
import random
from time import perf_counter

from core import run

SIZES = (100, 1000, 4000)
N_PERMUTATIONS = 1000  # значение по умолчанию из формы
WORDS = [f"слово{a}{b}" for a in "абвгдежзик" for b in "лмнопрстуф"]  # 100 разных слов


def make_rows(n: int) -> list[dict]:
    rng = random.Random(0)  # фиксированный seed — один и тот же набор при каждом замере
    return [
        {"text": " ".join(rng.choices(WORDS, k=rng.randint(20, 60))), "group": "A" if i % 2 else "B"}
        for i in range(n)
    ]


def measure(n: int) -> float:
    params = {"rows": make_rows(n), "test": "permutation", "n_permutations": N_PERMUTATIONS, "seed": 0}
    started = perf_counter()
    run(params)
    return perf_counter() - started


if __name__ == "__main__":
    print("| текстов | секунд |")
    print("|---|---|")
    for size in SIZES:
        print(f"| {size} | {measure(size):.2f} |")
