#!/usr/bin/env python3
"""Merge all_prices-YYYY-ocr.jsonl into all_prices-YYYY.jsonl."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    html_path = BASE / f"all_prices-{args.year}.jsonl"
    ocr_path = BASE / f"all_prices-{args.year}-ocr.jsonl"
    out_path = html_path

    html_rows = read_jsonl(html_path)
    ocr_rows = read_jsonl(ocr_path)
    ocr_dates = {row["date"] for row in ocr_rows}
    merged = [row for row in html_rows if row.get("date") not in ocr_dates]
    merged.extend(ocr_rows)
    merged.sort(key=lambda r: (r.get("date", ""), r.get("category", ""), r.get("product", ""), r.get("spec", "")))

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in merged:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"htmlRows={len(html_rows)}")
    print(f"ocrRows={len(ocr_rows)}")
    print(f"mergedRows={len(merged)}")
    print(f"ocrDates={len(ocr_dates)}")
    print(f"wrote {out_path.name}")


if __name__ == "__main__":
    main()
