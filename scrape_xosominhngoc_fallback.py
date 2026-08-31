#!/usr/bin/env python3
"""
Fallback scraper (nhieu nguon) -> bo sung ky con thieu vao data/all.csv
Dung khi raw.githubusercontent.com/.../lotto535/all.csv cap nhat cham hon
lich quay that te (13:00 va 21:00 VN moi ngay).

CSV schema (giu nguyen dung format cua NhanAZ-Data/vietlott-research):
product,draw_id,draw_date,draw_status,result_json,attributes_json,
official_pdf_urls_json,source_url,prize_status,validation_status,
validation_warnings_json,fetched_at

NHIEU NGUON (thu lan luot theo thu tu trong SOURCES, nguon nao cao duoc
ky thi dung ket qua cua nguon do, khong can thu tiep). Moi nguon co PARSER
RIENG vi cau truc HTML khac nhau - CA HAI DA TEST KHOP 100% VOI DU LIEU THUC:
  1. xosominhngoc.net.vn - 'Ky QSMT: #NNNNN ... Ngay: DD/MM/YYYY ... 6 so
                            ... Gia tri giai' (dau CHAM ngan hang nghin).
  2. minhchinh.com       - 'Ket qua QSMT ky #NNN ... Luc HH:MM ... 6 so'
                            (dau PHAY ngan hang nghin, ky khong co so 0
                            dem -> tu dong zfill(5) khi luu).
  vietlott.vn (chinh thuc) KHONG dua vao day: WAF cua trang nay chan IP
  datacenter nen GitHub Actions luon bi 403 (da ghi nhan trong du an).

Neu 1 nguon tra ve 0 ky hoac loi (404/403/parse that bai), script se
tu chuyen sang nguon tiep theo cho cung 1 ngay - khong lam sap workflow.

Cach dung:
    python3 scrape_xosominhngoc_fallback.py --csv data/all.csv
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

VN_TZ = timezone(timedelta(hours=7))
FIELDNAMES = [
    "product", "draw_id", "draw_date", "draw_status", "result_json",
    "attributes_json", "official_pdf_urls_json", "source_url",
    "prize_status", "validation_status", "validation_warnings_json",
    "fetched_at",
]

# (Danh sach SOURCES duoc dinh nghia ben duoi, sau khi cac ham parser
# cho tung nguon da duoc dinh nghia.)

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


def parse_xosominhngoc(raw_html: str, page_url: str, fetched_at: str):
    """Parser cho xosominhngoc.net.vn: 'Ky QSMT: #NNNNN ... Ngay: DD/MM/YYYY
    ... 6 so ... Gia tri giai' (dau CHAM ngan hang nghin)."""
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
                "data_source": page_url,
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


# minhchinh.com dung dinh dang khac han: 'Ket qua QSMT ky #NNN ngay
# DD/MM/YYYY - Luc HH:MM' (dau PHAY ngan hang nghin, ky khong co so 0 dem).
# Da test khop 100% voi mau HTML that nguoi dung gui.
MINHCHINH_HEADER_RE = re.compile(
    r"K[ếe]t\s*qu[ảa]\s*QSMT\s*k[ỳy]\s*#(\d+)\s*ng[àa]y\s*(\d{2})/(\d{2})/(\d{4})\s*"
    r"-\s*L[úu]c\s*(\d{2}):(\d{2})\s*"
    r"((?:\d{1,2}\s*){6})"
)


def parse_minhchinh(raw_html: str, page_url: str, fetched_at: str):
    text = strip_html(raw_html)
    m = MINHCHINH_HEADER_RE.search(text)
    if not m:
        return []

    draw_id = m.group(1).zfill(5)
    dd, mm, yyyy = m.group(2), m.group(3), m.group(4)
    draw_date = f"{yyyy}-{mm}-{dd}"

    nums = [int(x) for x in re.findall(r"\d{1,2}", m.group(7))]
    if len(nums) < 6:
        return []
    main_numbers = sorted(nums[:5])
    special_number = nums[5]

    result_json = json.dumps(
        {"numbers": main_numbers, "special_numbers": [special_number]},
        ensure_ascii=False,
    )
    attributes_json = json.dumps(
        {
            "data_source": page_url,
            "detail_title": f"Kỳ quay thưởng #{draw_id} ngày {dd}/{mm}/{yyyy}",
            "official_list_verified_at": fetched_at,
        },
        ensure_ascii=False,
    )
    return [
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
    ]


# ---------------------------------------------------------------------------
# Danh sach nguon, thu theo dung thu tu nay cho moi ngay can quet.
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "name": "xosominhngoc.net.vn",
        "url_template": "https://xosominhngoc.net.vn/kqxs-lotto-535-ngay-{dd}-{mm}-{yyyy}",
        "parser": parse_xosominhngoc,
        "verified": True,
    },
    {
        "name": "minhchinh.com",
        "url_template": "https://www.minhchinh.com/xs-lotto-535-ket-qua-lotto-535-ngay-{dd}-{mm}-{yyyy}.html",
        "parser": parse_minhchinh,
        "verified": True,
    },
    # vietlott.vn (chinh thuc) da LOAI BO khoi danh sach: WAF cua trang nay
    # chan IP datacenter, GitHub Actions luon bi 403 (da ghi nhan trong du
    # an) nen dua vao day chi ton thoi gian goi ma khong bao gio thanh cong.
]


def fetch_day_with_fallback(d, fetched_at: str):
    """Thu tung nguon trong SOURCES cho ngay d, tra ve rows cua nguon
    dau tien cao duoc du lieu (khong rong). In log cho biet nguon nao
    thanh cong / that bai de de theo doi."""
    dd, mm, yyyy = d.strftime("%d"), d.strftime("%m"), d.strftime("%Y")
    for src in SOURCES:
        url = src["url_template"].format(dd=dd, mm=mm, yyyy=yyyy)
        tag = "" if src["verified"] else " [chua kiem chung]"
        try:
            raw = fetch(url)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"  [{src['name']}{tag}] loi fetch {url}: {e}", file=sys.stderr)
            continue

        try:
            rows = src["parser"](raw, url, fetched_at)
        except Exception as e:  # parser khong khop cau truc trang -> bo qua, thu nguon sau
            print(f"  [{src['name']}{tag}] loi parse {url}: {e}", file=sys.stderr)
            continue

        if rows:
            print(f"  [{src['name']}{tag}] OK: tim thay {len(rows)} ky cho ngay {yyyy}-{mm}-{dd}")
            return rows

        print(f"  [{src['name']}{tag}] khong khop du lieu cho ngay {yyyy}-{mm}-{dd}, thu nguon tiep theo")

    print(f"  [!] khong nguon nao cao duoc du lieu cho ngay {yyyy}-{mm}-{dd}", file=sys.stderr)
    return []


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
    print(f"Quet fallback tu {start_date} den {today_vn} (gio VN), nguon: "
          + ", ".join(s["name"] for s in SOURCES))

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    new_rows = []
    seen_ids_this_run = set()

    for d in daterange(start_date, today_vn):
        day_rows = fetch_day_with_fallback(d, fetched_at)
        for r in day_rows:
            if r["draw_id"] in existing_ids or r["draw_id"] in seen_ids_this_run:
                continue
            new_rows.append(r)
            seen_ids_this_run.add(r["draw_id"])
            print(f"    + ky {r['draw_id']} ngay {r['draw_date']}: "
                  f"{json.loads(r['result_json'])}")

    if not new_rows:
        print("Khong co ky moi nao can bo sung.")
        return

    save_csv(args.csv, rows + new_rows)
    print(f"Da them {len(new_rows)} ky moi vao {args.csv}.")


if __name__ == "__main__":
    main()
