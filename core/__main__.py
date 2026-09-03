"""CLI ядра: python -m core input.json [output.json]."""
import json
import sys

from core.solver import run


def main(argv: list[str]) -> int:
    if not argv:
        print("Использование: python -m core input.json [output.json]", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as fh:
            params = json.load(fh)
        result = run(params)
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка расчёта: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
