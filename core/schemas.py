"""Pydantic-контракт вычислительного ядра TextDiff."""
import re

from pydantic import BaseModel, Field, field_validator, model_validator

WORD_RE = re.compile(r"[а-яa-zё]+", re.IGNORECASE)  # что считается словом (используют схема и solver)
LIMIT = 40_000_000  # граница входа: строк × перестановок (по замеру ≈ 10–15 секунд, см. README)


class Row(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    group: str = Field(min_length=1, max_length=100)


class TextDiffParams(BaseModel):
    rows: list[Row] = Field(min_length=2, max_length=50_000)
    text_col: str = Field(default="text", min_length=1, max_length=100)
    group_col: str = Field(default="group", min_length=1, max_length=100)
    test: str = Field(default="mannwhitney", pattern=r"^(mannwhitney|ttest|permutation)$")
    top_n: int = Field(default=20, ge=1, le=200)
    n_permutations: int = Field(default=1000, ge=1, le=200_000)
    seed: int = Field(default=0)

    @field_validator("rows")
    @classmethod
    def exactly_two_groups_and_words_in_texts(cls, rows: list[Row]) -> list[Row]:
        groups = {row.group for row in rows}
        if len(groups) != 2:
            raise ValueError(f"Нужно ровно две группы текстов для сравнения, найдено: {len(groups)}")
        for index, row in enumerate(rows):
            if not WORD_RE.search(row.text):
                # +2: первая строка CSV — заголовок, нумерация строк данных идёт с 2 (как в services.parse_csv_file)
                raise ValueError(f"Строка {index + 2}: в тексте нет ни одного слова")
        return rows

    @model_validator(mode="after")
    def work_is_within_limit(self):
        # n_permutations влияет на время расчёта только у перестановочного теста
        if self.test == "permutation" and len(self.rows) * self.n_permutations > LIMIT:
            raise ValueError(
                f"Слишком большой расчёт: строк × перестановок = {len(self.rows) * self.n_permutations}, "
                f"допустимо не больше {LIMIT}"
            )
        return self


class GroupStats(BaseModel):
    n_texts: int
    avg_len_words: float
    avg_ttr: float
    avg_word_len: float


class TextDiffResult(BaseModel):
    n_texts: int
    groups: dict[str, GroupStats]
    test: str
    statistic: float | None
    pvalue: float | None
    top_words: list[tuple[str, int]]
    permutations_used: int | None = None
    permutations_exact: bool | None = None
