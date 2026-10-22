"""Быстрая проверка распознавания: python -m invoice_kit.cli накладная.pdf [--json] [--tesseract ПУТЬ]."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .recognize import RecognitionError, extract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Распознать PDF-накладную и показать таблицу строк")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--json", action="store_true", help="вывести результат в JSON")
    parser.add_argument("--tesseract", default="", help="путь к tesseract.exe или его папке")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # английская Windows: иначе cp1252 и ошибка на кириллице
    try:
        ex = extract(args.pdf, args.tesseract)
    except RecognitionError as e:
        print(f"Не распознано: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(asdict(ex), ensure_ascii=False, indent=1))
        return 0
    print(f"Накладная № {ex.number or '?'} от {ex.date or '?'}, поставщик: {ex.supplier or '?'}")
    print(f"{'Наименование':60} {'Кол-во':>9} {'Ед.':5} {'Цена':>10} {'НДС':>10} {'С НДС':>10}")
    fmt = lambda v: "" if v is None else f"{v:.2f}"
    for line in ex.lines:
        print(f"{line.name[:60]:60} {line.qty:>9g} {line.unit[:5]:5} {fmt(line.price):>10} "
              f"{fmt(line.vat):>10} {fmt(line.total):>10}")
    total = sum(l.total or 0 for l in ex.lines)
    vat = sum(l.vat or 0 for l in ex.lines)
    print(f"Строк: {len(ex.lines)}; итого с НДС {total:.2f}, НДС {vat:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
