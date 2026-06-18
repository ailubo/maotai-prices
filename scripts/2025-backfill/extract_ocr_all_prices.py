#!/usr/bin/env python3
"""Extract all visible product price rows from OCR word coordinates."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
SOURCE_DIR = BASE / "sources" / "jinri-jiujia-wechat-links"
KNOWN_CATEGORY_BRANDS = [
    "茅台飞天",
    "茅台酱香",
    "茅台醇",
    "五粮液",
    "泸州老窖",
    "剑南春",
    "钓鱼台",
    "水井坊",
    "古井贡",
    "牛栏山",
    "白云边",
    "口子窖",
    "今世缘",
    "金种子",
    "贵州醇",
    "老白干",
    "仰韶",
    "习酒",
    "郎酒",
    "洋河",
    "汾酒",
    "西凤",
    "董酒",
    "酒鬼",
    "国台",
    "舍得",
    "金沙",
    "珍酒",
    "四特",
    "杜康",
    "赊店",
    "全兴",
    "丹泉",
]


def normalize(text: str) -> str:
    text = re.sub(r"\s+", "", text or "")
    return text.replace("（", "(").replace("）", ")")


def row_text(row: list[dict], x_min: int = 0, x_max: int = 10_000) -> str:
    return normalize("".join(str(w.get("text", "")) for w in row if x_min <= int(w.get("x", 0)) <= x_max))


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


def prices_in_range(row: list[dict], x_min: int, x_max: int) -> list[tuple[int, int]]:
    prices: list[tuple[int, int]] = []
    for word in row:
        x = int(word.get("x", 0))
        if not (x_min <= x <= x_max):
            continue
        text = normalize(str(word.get("text", "")))
        if not re.fullmatch(r"\d{1,5}", text):
            continue
        value = int(text)
        if 1 <= value <= 50000:
            prices.append((x, value))
    prices.sort()
    return prices


def pick_price(row: list[dict], x_min: int, x_max: int) -> int | None:
    prices = [(x, p) for x, p in prices_in_range(row, x_min, x_max) if p >= 10]
    if not prices:
        return None
    return prices[-1][1]


def clean_product(text: str) -> str:
    text = normalize(text)
    text = re.sub(r"^[0oO。·'\"《]+", "", text)
    text = re.sub(r"[，,。．、]+$", "", text)
    return text


def clean_category(text: str) -> str | None:
    text = clean_product(text)
    text = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日", "", text)
    if "系列" in text:
        text = text[:text.find("系列") + 2]
    if "五粮浓香" in text:
        return "五粮液系列"
    for brand in KNOWN_CATEGORY_BRANDS:
        if brand in text:
            return f"{brand}系列"
    text = re.sub(r"^[^一-龥A-Za-z0-9]+", "", text)
    text = re.sub(r"^[`@．。·0oO》>的下乙仆]+", "", text)
    text = re.sub(r"[^一-龥A-Za-z0-9]+$", "", text)
    if 2 <= len(text) <= 20 and "系列" in text:
        return text
    return None


def is_noise_product(product: str) -> bool:
    if not product:
        return True
    if product in {"品名", "规格", "昨日行情", "今日行情"}:
        return True
    if any(token in product for token in ["注：", "数据", "真实成交", "酒商群", "权利声明", "今日酒价"]):
        return True
    if re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日", product):
        return True
    return False


def category_from_row(row: list[dict]) -> str | None:
    text = row_text(row)
    if any(token in text for token in ["品名", "规格", "行情", "注："]):
        return None
    if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", text):
        if "飞天" in text:
            return "茅台飞天系列"
        detected = clean_category(text)
        if detected:
            return detected
    if "系列" not in text:
        return None
    idx = text.find("系列")
    if idx < 0:
        return None
    candidate = text[:idx + 2]
    candidate = re.sub(r"^\d{4}年\d{1,2}月\d{1,2}日", "", candidate)
    candidate = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日$", "", candidate)
    return clean_category(candidate)


def extract_row_price_rows(words: list[dict], date: str, image: dict) -> list[dict]:
    rows_out: list[dict] = []
    category = "未知"
    for row in cluster_rows(words):
        detected = category_from_row(row)
        if detected:
            category = detected
            continue

        full = row_text(row)
        if "品名" in full and ("行情" in full or "规格" in full):
            continue

        product = clean_product(row_text(row, 0, 240))
        spec = normalize(row_text(row, 240, 510))
        yesterday = pick_price(row, 520, 760)
        today = pick_price(row, 780, 1010)
        if today is None:
            continue
        if is_noise_product(product):
            continue
        if not spec:
            continue

        rows_out.append({
            "date": date,
            "category": category,
            "product": product,
            "spec": spec,
            "yesterday": yesterday,
            "today": today,
            "change": today - yesterday if yesterday is not None else None,
            "url": image.get("articleUrl", ""),
            "source_kind": "image-ocr",
            "imageIndex": image.get("index", ""),
            "imageUrl": image.get("url", ""),
            "ocrWords": image.get("words", ""),
        })
    return rows_out


def extract_column_price_rows(words: list[dict], date: str, image: dict) -> list[dict]:
    rows_out: list[dict] = []
    category = ""
    for row in cluster_rows(words):
        detected = category_from_row(row)
        if detected:
            category = detected
            continue
        full = row_text(row)
        if not ("飞天" in full and ("原" in full or "散" in full)):
            continue

        product = clean_product(row_text(row, 0, 240))
        spec = normalize(row_text(row, 240, 510))
        yuanxiang = pick_price(row, 560, 730)
        sanping = pick_price(row, 820, 980)
        if is_noise_product(product) or not spec:
            continue
        if yuanxiang is not None:
            rows_out.append({
                "date": date,
                "category": category or "茅台飞天系列",
                "product": product,
                "spec": f"{spec} 原箱价",
                "yesterday": None,
                "today": yuanxiang,
                "change": None,
                "url": image.get("articleUrl", ""),
                "source_kind": "image-ocr",
                "imageIndex": image.get("index", ""),
                "imageUrl": image.get("url", ""),
                "ocrWords": image.get("words", ""),
            })
        if sanping is not None:
            rows_out.append({
                "date": date,
                "category": category or "茅台飞天系列",
                "product": product,
                "spec": f"{spec} 散瓶价",
                "yesterday": None,
                "today": sanping,
                "change": None,
                "url": image.get("articleUrl", ""),
                "source_kind": "image-ocr",
                "imageIndex": image.get("index", ""),
                "imageUrl": image.get("url", ""),
                "ocrWords": image.get("words", ""),
            })
    return rows_out


def dedupe(rows: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for row in rows:
        key = (row["date"], row["category"], row["product"], row["spec"], row["today"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def load_link_urls(year: int) -> dict[str, str]:
    path = SOURCE_DIR / f"{year}-links.json"
    if not path.exists():
        return {}
    links = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(links, list):
        return {}
    return {item["date"]: item.get("url", "") for item in links if item.get("date")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--date", default="")
    args = parser.parse_args()

    ocr_dir = SOURCE_DIR / f"{args.year}-ocr"
    manifests = sorted(ocr_dir.glob("*/manifest.json"))
    if args.date:
        manifests = [ocr_dir / args.date / "manifest.json"]

    all_rows: list[dict] = []
    image_counts: dict[str, int] = {}
    missing: list[str] = []
    link_urls = load_link_urls(args.year)

    for manifest_path in manifests:
        if not manifest_path.exists():
            missing.append(manifest_path.parent.name)
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        date = manifest["date"]
        article_url = manifest.get("url") or manifest.get("articleUrl") or link_urls.get(date, "")
        date_rows: list[dict] = []
        for image in manifest.get("images", []):
            image = {**image, "articleUrl": article_url}
            words_path = BASE / image["words"]
            words = json.loads(words_path.read_text(encoding="utf-8-sig"))
            date_rows.extend(extract_row_price_rows(words, date, image))
            date_rows.extend(extract_column_price_rows(words, date, image))
        date_rows = dedupe(date_rows)
        image_counts[date] = len(date_rows)
        all_rows.extend(date_rows)

    all_rows = dedupe(all_rows)
    all_rows.sort(key=lambda r: (r["date"], r["category"], r["product"], r["spec"]))

    rows_out = BASE / f"all_prices-{args.year}-ocr.jsonl"
    summary_out = SOURCE_DIR / f"{args.year}-ocr-all-summary.json"
    with rows_out.open("w", encoding="utf-8", newline="\n") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary_out.write_text(json.dumps({
        "targetYear": args.year,
        "manifestCount": len(manifests),
        "ocrAllPriceRows": len(all_rows),
        "missingOcrDates": missing,
        "rowCounts": image_counts,
        "generatedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"ocrAllPriceRows={len(all_rows)}")
    print(f"missingOcrDates={len(missing)}")
    print(f"wrote {rows_out.name}, {summary_out.relative_to(BASE)}")


if __name__ == "__main__":
    main()
