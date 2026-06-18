#!/usr/bin/env python3
"""Merge image-OCR core Moutai records into data-YYYY.json."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    data_path = BASE / f"data-{args.year}.json"
    ocr_path = BASE / f"data-{args.year}-ocr-core.json"
    if not data_path.exists():
        raise FileNotFoundError(data_path)
    if not ocr_path.exists():
        raise FileNotFoundError(ocr_path)

    data = json.loads(data_path.read_text(encoding="utf-8"))
    ocr = json.loads(ocr_path.read_text(encoding="utf-8"))

    by_date = {record["date"]: record for record in data.get("prices", [])}
    for record in ocr.get("prices", []):
        by_date[record["date"]] = record

    merged = sorted(by_date.values(), key=lambda record: record["date"])
    data["prices"] = merged
    data["note"] = (
        f"Merged from HTML table extraction and image-OCR core extraction for {args.year}. "
        "Full product rows remain limited to HTML table sources."
    )
    data["generated_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"mergedRecords={len(merged)}")
    print(f"ocrRecords={len(ocr.get('prices', []))}")
    print(f"wrote {data_path.name}")


if __name__ == "__main__":
    main()
