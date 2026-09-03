"""Pydantic-контракт вычислительного ядра TextDiff."""
from pydantic import BaseModel, Field, field_validator


class Row(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    group: str = Field(min_length=1, max_length=100)


class TextDiffParams(BaseModel):
    rows: list[Row] = Field(min_length=2, max_length=50_000)
    text_col: str = Field(default="text", min_length=1, max_length=100)
    group_col: str = Field(default="group", min_length=1, max_length=100)
    test: str = Field(default="mannwhitney", pattern=r"^(mannwhitney|ttest)$")
    top_n: int = Field(default=20, ge=1, le=200)

    @field_validator("rows")
    @classmethod
    def at_least_two_groups(cls, rows: list[Row]) -> list[Row]:
        groups = {row.group for row in rows}
        if len(groups) < 2:
            raise ValueError("Нужно минимум две группы текстов для сравнения")
        return rows


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
