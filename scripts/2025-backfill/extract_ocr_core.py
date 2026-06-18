#!/usr/bin/env python3
"""Extract core Moutai prices from Windows OCR word coordinates."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
SOURCE_DIR = BASE / "sources" / "jinri-jiujia-wechat-links"


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def price_from_words(words: list[dict], x_min: int, x_max: int) -> int | None:
    candidates: list[tuple[int, int]] = []
    for word in words:
        x = int(word.get("x", 0))
        if x < x_min or x > x_max:
            continue
        text = normalize(str(word.get("text", "")))
        if not re.fullmatch(r"\d{3,5}", text):
            continue
        value = int(text)
        if 100 <= value <= 50000:
            candidates.append((x, value))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def cluster_rows(words: list[dict], tolerance: int = 26) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (int(w.get("y", 0)), int(w.get("x", 0)))):
        y = int(word.get("y", 0))
        placed = False
        for row in rows:
            row_y = sum(int(w.get("y", 0)) for w in row) / len(row)
            if abs(y - row_y) <= tolerance:
                row.append(word)
                placed = True
                break
        if not placed:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: int(w.get("x", 0)))
    return rows


def extract_from_words(words: list[dict], year: int) -> list[dict]:
    yy = str(year % 100)
    fallback_yy = str((year - 1) % 100)
    rows = []
    for row in cluster_rows(words):
        product = normalize("".join(str(w.get("text", "")) for w in row if int(w.get("x", 0)) < 240))
        if "飞天" not in product:
            continue

        full_year = str(year)
        fallback_year = str(year - 1)
        if full_year in product or fallback_year in product:
            vintage = yy if full_year in product else fallback_yy
            yuanxiang = price_from_words(row, 560, 730)
            sanping = price_from_words(row, 820, 980)
            if yuanxiang is not None:
                rows.append({
                    "kind": "yuanxiang",
                    "vintage": vintage,
                    "layout": "ocr-column-price",
                    "productOcr": product,
                    "yesterday": None,
                    "today": yuanxiang,
                    "rowWords": row,
                })
            if sanping is not None:
                rows.append({
                    "kind": "sanping",
                    "vintage": vintage,
                    "layout": "ocr-column-price",
                    "productOcr": product,
                    "yesterday": None,
                    "today": sanping,
                    "rowWords": row,
                })
            continue

        if f"{yy}年" not in product:
            if f"{fallback_yy}年" in product:
                vintage = fallback_yy
            else:
                continue
        else:
            vintage = yy
        kind = ""
        if "散" in product:
            kind = "sanping"
        elif "原" in product:
            kind = "yuanxiang"
        else:
            continue
        yesterday = price_from_words(row, 520, 730)
        today = price_from_words(row, 780, 980)
        if today is None:
            continue
        rows.append({
            "kind": kind,
            "vintage": vintage,
            "layout": "ocr-row-price",
            "productOcr": product,
            "yesterday": yesterday,
            "today": today,
            "rowWords": row,
        })
    return rows


def signal_for(sanping: int | None) -> str | None:
    if sanping is None:
        return None
    if sanping < 1499:
        return "🔴"
    if sanping > 1800:
        return "🟢"
    return "🟡"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--date", default="")
    args = parser.parse_args()

    ocr_dir = SOURCE_DIR / f"{args.year}-ocr"
    manifests = sorted(ocr_dir.glob("*/manifest.json"))
    if args.date:
        manifests = [ocr_dir / args.date / "manifest.json"]

    core_prices: list[dict] = []
    image_rows: list[dict] = []
    missing: list[str] = []
    no_core: list[str] = []

    for manifest_path in manifests:
        if not manifest_path.exists():
            missing.append(manifest_path.parent.name)
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        date = manifest["date"]
        matches: list[dict] = []
        for image in manifest.get("images", []):
            words_path = BASE / image["words"]
            words = json.loads(words_path.read_text(encoding="utf-8-sig"))
            found = extract_from_words(words, args.year)
            for row in found:
                row["image"] = image["image"]
                row["imageUrl"] = image.get("url", "")
                row["imageIndex"] = image["index"]
            matches.extend(found)
            image_rows.extend({
                "date": date,
                "imageIndex": image["index"],
                "image": image["image"],
                "imageUrl": image.get("url", ""),
                "kind": row["kind"],
                "vintage": row.get("vintage", ""),
                "layout": row.get("layout", ""),
                "productOcr": row["productOcr"],
                "yesterday": row["yesterday"],
                "today": row["today"],
            } for row in found)

        target_yy = str(args.year % 100)
        sanping = next((row for row in matches if row["kind"] == "sanping" and row.get("vintage") == target_yy), None)
        yuanxiang = next((row for row in matches if row["kind"] == "yuanxiang" and row.get("vintage") == target_yy), None)
        sanping = sanping or next((row for row in matches if row["kind"] == "sanping"), None)
        yuanxiang = yuanxiang or next((row for row in matches if row["kind"] == "yuanxiang"), None)
        if not sanping and not yuanxiang:
            no_core.append(date)
            continue
        core_prices.append({
            "date": date,
            "source": "今日酒价",
            "source_kind": "image-ocr",
            "guide_price": 1499,
            "sanping": sanping["today"] if sanping else None,
            "yuanxiang": yuanxiang["today"] if yuanxiang else None,
            "signal": signal_for(sanping["today"] if sanping else None),
            "ocr_manifest": str(manifest_path.relative_to(BASE)).replace(os.sep, "/"),
            "matched_products": [
                {
                    "kind": row["kind"],
                    "vintage": row.get("vintage", ""),
                    "layout": row.get("layout", ""),
                    "productOcr": row["productOcr"],
                    "today": row["today"],
                    "yesterday": row["yesterday"],
                    "image": row["image"],
                    "imageUrl": row.get("imageUrl", ""),
                    "imageIndex": row["imageIndex"],
                }
                for row in matches
            ],
        })

    core_prices.sort(key=lambda p: p["date"])
    image_rows.sort(key=lambda p: (p["date"], p["imageIndex"], p["kind"]))

    data_out = BASE / f"data-{args.year}-ocr-core.json"
    rows_out = BASE / f"core_prices-{args.year}-ocr.jsonl"
    summary_out = SOURCE_DIR / f"{args.year}-ocr-summary.json"

    data_out.write_text(json.dumps({
        "prices": core_prices,
        "note": f"Core Moutai prices extracted from image OCR under sources/jinri-jiujia-wechat-links/{args.year}-ocr.",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with rows_out.open("w", encoding="utf-8", newline="\n") as f:
        for row in image_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    duplicate_dates = [date for date, count in Counter(p["date"] for p in core_prices).items() if count > 1]
    summary_out.write_text(json.dumps({
        "targetYear": args.year,
        "manifestCount": len(manifests),
        "coreRecords": len(core_prices),
        "ocrCoreRows": len(image_rows),
        "missingOcrDates": missing,
        "noCoreOcrDates": no_core,
        "duplicateCoreDates": duplicate_dates,
        "generatedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"coreRecords={len(core_prices)}")
    print(f"ocrCoreRows={len(image_rows)}")
    print(f"missingOcrDates={len(missing)}")
    print(f"noCoreOcrDates={len(no_core)}")
    print(f"wrote {data_out.name}, {rows_out.name}, {summary_out.relative_to(BASE)}")


if __name__ == "__main__":
    main()
