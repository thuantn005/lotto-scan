#!/usr/bin/env python3
"""
Fallback scraper: xosominhngoc.net.vn -> bo sung ky con thieu vao data/all.csv
Dung khi raw.githubusercontent.com/.../lotto535/all.csv cap nhat cham hon
lich quay that te (13:00 va 21:00 VN moi ngay).

CSV schema (giu nguyen dung format cua NhanAZ-Data/vietlott-research):
product,draw_id,draw_date,draw_status,result_json,attributes_json,
official_pdf_urls_json,source_url,prize_status,validation_status,
validation_warnings_json,fetched_at

Cach dung:
    python3 scrape_xosominhngoc_fallback.py --csv data/all.csv

Script se:
  1. Doc draw_id lon nhat hien co trong CSV.
  2. Xac dinh cac ngay can kiem tra (tu ngay cua ky cuoi -> hom nay, gio VN).
  3. Cao tung trang kqxs-lotto-535-ngay-DD-MM-YYYY.
  4. Voi moi ky tim duoc ma chua co trong CSV -> them dong moi.
  5. Ghi lai CSV, sap xep theo draw_id tang dan.
"""

import argparse
import csv
import html
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

BASE_URL = "https://xosominhngoc.net.vn/kqxs-lotto-535-ngay-{dd}-{mm}-{yyyy}"
VN_TZ = timezone(timedelta(hours=7))
FIELDNAMES = [
    "product", "draw_id", "draw_date", "draw_status", "result_json",
    "attributes_json", "official_pdf_urls_json", "source_url",
    "prize_status", "validation_status", "validation_warnings_json",
    "fetched_at",
]

BLOCK_RE = re.compile(
    r"K[ỳy]\s*QSMT:\s*#(\d{5}).{0,300}?"
    r"Ng[àa]y:\s*(\d{2})/(\d{2})/(\d{4}).{0,600}?"
    r"(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s*"
    r"Gi[áa]\s*tr[ịi]\s*gi[ảa]i",
    re.DOTALL,
)

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")


def strip_html(raw_html: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw_html)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def parse_day_page(raw_html: str, page_url: str, fetched_at: str):
    text = strip_html(raw_html)
    rows = []
    for m in BLOCK_RE.finditer(text):
        draw_id = m.group(1)
        dd, mm, yyyy = m.group(2), m.group(3), m.group(4)
        nums = [int(m.group(i)) for i in range(5, 11)]
        main_numbers = sorted(nums[:5])
        special_number = nums[5]
        draw_date = f"{yyyy}-{mm}-{dd}"
        result_json = json.dumps(
            {"numbers": main_numbers, "special_numbers": [special_number]},
            ensure_ascii=False,
        )
        attributes_json = json.dumps(
            {
                "data_source": "xosominhngoc_fallback",
                "detail_title": f"Kỳ quay thưởng #{draw_id} ngày {dd}/{mm}/{yyyy}",
                "official_list_verified_at": fetched_at,
            },
            ensure_ascii=False,
        )
        rows.append(
            {
                "product": "lotto535",
                "draw_id": draw_id,
                "draw_date": draw_date,
                "draw_status": "confirmed",
                "result_json": result_json,
                "attributes_json": attributes_json,
                "official_pdf_urls_json": "[]",
                "source_url": page_url,
                "prize_status": "complete",
                "validation_status": "valid",
                "validation_warnings_json": "[]",
                "fetched_at": fetched_at,
            }
        )
    return rows


def load_csv(path: str):
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def save_csv(path: str, rows):
    rows_sorted = sorted(rows, key=lambda r: int(r["draw_id"]))
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows_sorted:
            writer.writerow(r)


def daterange(start_date, end_date):
    d = start_date
    while d <= end_date:
        yield d
        d += timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/all.csv", help="Duong dan file all.csv")
    ap.add_argument(
        "--lookback-days",
        type=int,
        default=1,
        help="Quet them tu N ngay truoc ky cuoi cung trong CSV (phong khi thieu sot)",
    )
    args = ap.parse_args()

    rows = load_csv(args.csv)
    if not rows:
        print("CSV rong, bo qua fallback scrape.", file=sys.stderr)
        return

    existing_ids = {r["draw_id"] for r in rows}
    latest_date_str = max(r["draw_date"] for r in rows)
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()

    now_vn = datetime.now(VN_TZ)
    today_vn = now_vn.date()
    start_date = latest_date - timedelta(days=args.lookback_days)
    if start_date > today_vn:
        start_date = today_vn

    print(f"CSV hien co {len(rows)} ky, moi nhat ngay {latest_date_str}.")
    print(f"Quet fallback tu {start_date} den {today_vn} (gio VN).")

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    new_rows = []
    seen_ids_this_run = set()

    for d in daterange(start_date, today_vn):
        dd, mm, yyyy = d.strftime("%d"), d.strftime("%m"), d.strftime("%Y")
        url = BASE_URL.format(dd=dd, mm=mm, yyyy=yyyy)
        try:
            raw = fetch(url)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"  [bo qua] loi fetch {url}: {e}", file=sys.stderr)
            continue

        day_rows = parse_day_page(raw, url, fetched_at)
        for r in day_rows:
            if r["draw_id"] in existing_ids or r["draw_id"] in seen_ids_this_run:
                continue
            new_rows.append(r)
            seen_ids_this_run.add(r["draw_id"])
            print(f"  + ky {r['draw_id']} ngay {r['draw_date']}: "
                  f"{json.loads(r['result_json'])}")

    if not new_rows:
        print("Khong co ky moi nao can bo sung.")
        return

    save_csv(args.csv, rows + new_rows)
    print(f"Da them {len(new_rows)} ky moi vao {args.csv}.")


if __name__ == "__main__":
    main()
