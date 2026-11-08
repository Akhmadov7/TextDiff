"""Замер времени расчёта трёх тестов: python measure.py. Результат — таблица для README."""
import random
from time import perf_counter

from core import run

SIZES = (100, 1000, 4000, 10000)
N_PERMUTATIONS = 1000
TESTS = ("mannwhitney", "ttest", "permutation")
WORDS = [f"слово{a}{b}" for a in "абвгдежзик" for b in "лмнопрстуф"]


def make_rows(n: int) -> list[dict]:
    rng = random.Random(0)
    return [
        {"text": " ".join(rng.choices(WORDS, k=rng.randint(20, 60))), "group": "A" if i % 2 else "B"}
        for i in range(n)
    ]


def measure(n: int, test: str) -> float:
    params = {"rows": make_rows(n), "test": test, "n_permutations": N_PERMUTATIONS, "seed": 0}
    started = perf_counter()
    run(params)
    return perf_counter() - started


if __name__ == "__main__":
    print("| текстов | Манна—Уитни | t-критерий | перестановочный |")
    print("|---|---|---|---|")
    for size in SIZES:
        print(f"| {size} | " + " | ".join(f"{measure(size, test):.2f}" for test in TESTS) + " |")
