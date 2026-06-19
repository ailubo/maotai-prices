#!/usr/bin/env python3
"""Extract all visible product price rows from OCR word coordinates."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
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


def table_layout_from_header(row: list[dict]) -> str | None:
    text = row_text(row)
    if "品名" not in text or "规格" not in text:
        return None
    if "原箱价" in text and "散瓶价" in text:
        return "box-bottle"
    if "昨日" in text and "今日" in text and "行情" in text:
        return "daily-change"
    return None


def append_price_row(
    rows_out: list[dict],
    *,
    date: str,
    category: str,
    product: str,
    spec: str,
    yesterday: int | None,
    today: int,
    image: dict,
    layout: str,
) -> None:
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
        "ocrLayout": layout,
        "imageIndex": image.get("index", ""),
        "imageUrl": image.get("url", ""),
        "ocrWords": image.get("words", ""),
    })


def box_bottle_product_and_spec(product: str, spec: str, price_kind: str) -> tuple[str, str]:
    match = re.fullmatch(r"飞天\((\d{4})\)", product)
    if not match:
        return product, f"{spec} {price_kind}"

    year = match.group(1)[-2:]
    kind = "原" if price_kind == "原箱价" else "散"
    if "43" in spec:
        return f"{year}年43度飞天({kind})", spec
    return f"{year}年飞天({kind})", spec


def normalize_feitian_degree_product(product: str, spec: str) -> str:
    match = re.fullmatch(r"(\d{2})年飞天\((原|散)\)", product)
    if match and "43" in spec:
        return f"{match.group(1)}年43度飞天({match.group(2)})"
    return product


def clean_product(text: str) -> str:
    text = normalize(text)
    text = re.sub(r"^[0oO。·'\"《]+", "", text)
    text = re.sub(r"[，,。．、]+$", "", text)
    text = text.replace("精品矛口", "精品茅台").replace("精品茅口", "精品茅台")
    if text == "迎宾(飞天":
        text = "迎宾(飞天)"
    text = re.sub(r"^四年飞天", "19年飞天", text)
    return text


def clean_spec(text: str) -> str:
    text = normalize(text)
    text = text.replace("％", "%")
    text = text.replace("·", ".")
    text = re.sub(r"^[，,品)]+", "", text)
    text = text.rstrip("。《，,．。")
    text = (
        text.replace("V01", "vol")
        .replace("v01", "vol")
        .replace("vo1", "vol")
        .replace("voI", "vol")
        .replace("v引", "vol")
        .replace("寸ol", "vol")
    )
    text = text.replace("m1", "ml").replace("mt", "ml").replace("m]", "ml").replace("mL", "ml")
    text = re.sub(r"^[币é§]3%", "53%", text)
    text = re.sub(r"^币2%", "52%", text)
    text = re.sub(r"^5300vol", "53%vol", text)
    text = re.sub(r"^5200vol", "52%vol", text)
    text = text.replace("500/ovol", "50%vol")
    text = re.sub(r"^(\d{2})%v(\d+ml)$", r"\1%vol\2", text)
    text = re.sub(r"^(\d{2})%1(500ml)$", r"\1%vol\2", text)
    text = re.sub(r"^(\d{2})%vol(\d+)$", r"\1%vol\2ml", text)
    text = re.sub(r"5001$", "500ml", text)
    text = re.sub(r"^3%vol500ml", "53%vol500ml", text)
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
    layout: str | None = None
    for row in cluster_rows(words):
        detected = category_from_row(row)
        if detected:
            category = detected
            layout = None
            continue

        full = row_text(row)
        header_layout = table_layout_from_header(row)
        if header_layout:
            layout = header_layout
            continue
        if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", full):
            layout = None
            continue
        if layout is None:
            continue
        if "品名" in full and ("行情" in full or "规格" in full):
            continue

        product = clean_product(row_text(row, 0, 240))
        spec = clean_spec(row_text(row, 240, 510))
        product = normalize_feitian_degree_product(product, spec)
        if is_noise_product(product):
            continue
        if not spec:
            continue

        left_price = pick_price(row, 520, 760)
        right_price = pick_price(row, 780, 930)
        if layout == "box-bottle":
            if left_price is not None:
                row_product, row_spec = box_bottle_product_and_spec(product, spec, "原箱价")
                append_price_row(
                    rows_out,
                    date=date,
                    category=category,
                    product=row_product,
                    spec=row_spec,
                    yesterday=None,
                    today=left_price,
                    image=image,
                    layout=layout,
                )
            if right_price is not None:
                row_product, row_spec = box_bottle_product_and_spec(product, spec, "散瓶价")
                append_price_row(
                    rows_out,
                    date=date,
                    category=category,
                    product=row_product,
                    spec=row_spec,
                    yesterday=None,
                    today=right_price,
                    image=image,
                    layout=layout,
                )
            continue

        if layout == "daily-change" and right_price is not None:
            if left_price is not None and right_price == left_price * 10:
                right_price = left_price
            append_price_row(
                rows_out,
                date=date,
                category=category,
                product=product,
                spec=spec,
                yesterday=left_price,
                today=right_price,
                image=image,
                layout=layout,
            )
    return rows_out


def dedupe(rows: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for row in rows:
        key = (
            row["date"],
            row["category"],
            row["product"],
            row["spec"],
            row.get("yesterday"),
            row["today"],
            row.get("ocrLayout", ""),
        )
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
        "layoutCounts": dict(Counter(row.get("ocrLayout", "") for row in all_rows)),
        "generatedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"ocrAllPriceRows={len(all_rows)}")
    print(f"missingOcrDates={len(missing)}")
    print(f"wrote {rows_out.name}, {summary_out.relative_to(BASE)}")


if __name__ == "__main__":
    main()
