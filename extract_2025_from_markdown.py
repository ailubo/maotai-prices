#!/usr/bin/env python3
"""Extract Maotai core prices and all product prices from saved 2025 markdown."""

from __future__ import annotations

import csv
import html
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE_DIR = BASE / "sources" / "jinri-jiujia-wechat-links"
LINKS_CSV = SOURCE_DIR / "2025-links.csv"
MD_DIR = SOURCE_DIR / "2025-md"
DATA_OUT = BASE / "data-2025-from-md.json"
ALL_OUT = BASE / "all_prices-2025-from-md.jsonl"
SUMMARY_OUT = SOURCE_DIR / "2025-md-summary.json"

SOLAR_TERMS = {
    "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
    "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
    "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
    "立冬", "小雪", "大雪", "冬至", "小寒", "大寒",
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_td = False
        self.in_tr = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag == "td":
            self.in_td = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_td:
            self.in_td = False
            self.current_row.append(clean_text("".join(self.current_cell)))
        elif tag == "tr" and self.in_tr:
            self.in_tr = False
            if any(cell for cell in self.current_row):
                self.rows.append(self.current_row)

    def handle_data(self, data: str) -> None:
        if self.in_td:
            self.current_cell.append(data)


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[⬆⬇➡↑↓]", "", value)
    return value.strip()


def markdown_meta(md: str) -> dict[str, str]:
    if not md.startswith("---"):
        return {}
    end = md.find("\n---", 3)
    if end < 0:
        return {}
    meta: dict[str, str] = {}
    for line in md[3:end].splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"')
    return meta


def extract_tables(md: str) -> list[str]:
    return re.findall(r"<table[\s\S]*?</table>", md, flags=re.I)


def parse_table(table_html: str) -> list[list[str]]:
    parser = TableParser()
    parser.feed(table_html)
    return parser.rows


def is_header_row(row: list[str]) -> bool:
    joined = "".join(row)
    return "品名" in joined and "规格" in joined and ("行情" in joined or "今日" in joined)


def choose_category(rows_before_header: list[list[str]]) -> str:
    candidates: list[str] = []
    for row in rows_before_header:
        for cell in row:
            if not cell:
                continue
            if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", cell):
                continue
            if "公众号" in cell or "今日酒价" in cell or cell in {"品名", "规格"}:
                continue
            if len(cell) > 32:
                continue
            candidates.append(cell)
    return candidates[-1] if candidates else "未知"


def price_to_int(value: str) -> int | None:
    m = re.search(r"\d{1,6}", clean_text(value))
    if not m:
        return None
    n = int(m.group(0))
    if n <= 0:
        return None
    return n


def row_to_product(date: str, url: str, category: str, row: list[str]) -> dict | None:
    if len(row) < 3:
        return None
    product = clean_text(row[0])
    spec = clean_text(row[1]) if len(row) > 1 else ""
    if not product or product in {"品名", "品牌", "昨日行情", "今日行情"}:
        return None
    if product in SOLAR_TERMS or product.replace("热!", "") in SOLAR_TERMS:
        return None
    if "注:数据和真实成交价" in product:
        return None
    if not spec or spec == "规格":
        return None

    price_cells = [price_to_int(c) for c in row[2:]]
    price_cells = [p for p in price_cells if p is not None]
    if not price_cells:
        return None
    if len(price_cells) >= 2:
        yesterday, today = price_cells[0], price_cells[1]
    else:
        yesterday, today = None, price_cells[0]
    if today is None:
        return None

    return {
        "date": date,
        "category": category,
        "product": product,
        "spec": spec,
        "yesterday": yesterday,
        "today": today,
        "change": today - yesterday if yesterday is not None else None,
        "url": url,
    }


def extract_products(md: str, expected_date: str, url: str) -> list[dict]:
    products: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for table_html in extract_tables(md):
        rows = parse_table(table_html)
        header_idx = next((i for i, row in enumerate(rows) if is_header_row(row)), -1)
        if header_idx < 0:
            continue
        category = choose_category(rows[:header_idx])
        for row in rows[header_idx + 1:]:
            item = row_to_product(expected_date, url, category, row)
            if not item:
                continue
            key = (item["category"], item["product"], item["spec"])
            if key in seen:
                continue
            seen.add(key)
            products.append(item)
    return products


def guide_price_for(date: str) -> int:
    # 2025 data uses the 1499 guide price throughout this project.
    return 1499


def signal_for(sanping: int | None, guide_price: int) -> str | None:
    if sanping is None:
        return None
    if sanping < guide_price:
        return "🔴"
    if sanping > 1800:
        return "🟢"
    return "🟡"


def pick_maotai_core(products: list[dict], year: int) -> tuple[int | None, int | None, list[dict]]:
    yy = str(year % 100)
    maotai = [p for p in products if "茅台" in p["category"] and "飞天" in p["product"]]
    preferred = [p for p in maotai if p["product"].startswith(f"{yy}年飞天")]
    search = preferred or maotai

    yuanxiang = None
    sanping = None
    matched: list[dict] = []
    for item in search:
        name = item["product"]
        if yuanxiang is None and ("原" in name or "原箱" in name):
            yuanxiang = item["today"]
            matched.append(item)
        elif sanping is None and "散" in name and "原" not in name:
            sanping = item["today"]
            matched.append(item)
        if yuanxiang is not None and sanping is not None:
            break
    return sanping, yuanxiang, matched


def read_links() -> list[dict[str, str]]:
    with LINKS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    links = read_links()
    all_rows: list[dict] = []
    core_prices: list[dict] = []
    missing_md: list[str] = []
    no_products: list[str] = []
    no_core: list[str] = []
    product_counts: dict[str, int] = {}

    for link in links:
        date = link["date"]
        url = link["url"]
        md_path = MD_DIR / f"{date}.md"
        if not md_path.exists():
            missing_md.append(date)
            continue
        md = md_path.read_text(encoding="utf-8")
        meta = markdown_meta(md)
        products = extract_products(md, date, url)
        product_counts[date] = len(products)
        if not products:
            no_products.append(date)
            continue
        all_rows.extend(products)

        sanping, yuanxiang, matched = pick_maotai_core(products, 2025)
        if sanping is None and yuanxiang is None:
            no_core.append(date)
            continue
        guide_price = guide_price_for(date)
        core_prices.append({
            "date": date,
            "source": "今日酒价",
            "guide_price": guide_price,
            "sanping": sanping,
            "yuanxiang": yuanxiang,
            "signal": signal_for(sanping, guide_price),
            "url": url,
            "markdown": str(md_path.relative_to(BASE)).replace(os.sep, "/"),
            "title": meta.get("title", ""),
            "matched_products": [
                {
                    "category": p["category"],
                    "product": p["product"],
                    "spec": p["spec"],
                    "today": p["today"],
                }
                for p in matched
            ],
        })

    core_prices.sort(key=lambda p: p["date"])
    all_rows.sort(key=lambda p: (p["date"], p["category"], p["product"], p["spec"]))

    DATA_OUT.write_text(json.dumps({
        "prices": core_prices,
        "note": "Extracted from baoyu markdown snapshots under sources/jinri-jiujia-wechat-links/2025-md.",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with ALL_OUT.open("w", encoding="utf-8", newline="\n") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    duplicate_dates = [d for d, c in Counter(p["date"] for p in core_prices).items() if c > 1]
    summary = {
        "sourceLinks": str(LINKS_CSV.relative_to(BASE)).replace(os.sep, "/"),
        "markdownDir": str(MD_DIR.relative_to(BASE)).replace(os.sep, "/"),
        "targetYear": 2025,
        "linkCount": len(links),
        "markdownFiles": len(list(MD_DIR.glob("*.md"))) if MD_DIR.exists() else 0,
        "coreRecords": len(core_prices),
        "allPriceRows": len(all_rows),
        "missingMarkdownDates": missing_md,
        "noProductDates": no_products,
        "noCoreMaotaiDates": no_core,
        "duplicateCoreDates": duplicate_dates,
        "productCounts": product_counts,
        "generatedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }
    SUMMARY_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"coreRecords={len(core_prices)}")
    print(f"allPriceRows={len(all_rows)}")
    print(f"missingMarkdownDates={len(missing_md)}")
    print(f"noProductDates={len(no_products)}")
    print(f"noCoreMaotaiDates={len(no_core)}")
    print(f"wrote {DATA_OUT.name}, {ALL_OUT.name}, {SUMMARY_OUT.relative_to(BASE)}")


if __name__ == "__main__":
    main()
