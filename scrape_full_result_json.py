#!/usr/bin/env python3
"""
Cao ket qua day du (so + gia tri giai Doc Dac + bang 7 giai) tu nhieu
nguon, ghi ra 1 file JSON (data/full_results.json).

Khac voi scrape_xosominhngoc_fallback.py (chi lay 6 so de gop vao all.csv),
script nay lay THEM:
  - Gia tri giai Doc Dac cua ky do
  - Bang so luong + gia tri trung giai cho ca 7 hang giai
    (Doc Dac, Nhat, Nhi, Ba, Tu, Nam, Khuyen Khich)

NHIEU NGUON (thu lan luot theo SOURCES, nguon nao cao duoc thi dung,
khong can thu tiep). Moi nguon co PARSER RIENG vi cau truc HTML khac nhau:
  1. xosominhngoc.net.vn - da test khop 100% voi mau du lieu thuc.
     URL: kqxs-lotto-535-ngay-DD-MM-YYYY
     Dinh dang: "Ky QSMT: #00856 ... Ngay: DD/MM/YYYY ... 6 so ...
     Gia tri giai Doc Dac ... 7.563.375.000" (dau CHAM ngan hang nghin).
  2. minhchinh.com - da test khop 100% voi mau HTML that nguoi dung gui.
     URL: xs-lotto-535-ket-qua-lotto-535-ngay-DD-MM-YYYY.html
     Dinh dang: "Ket qua QSMT ky #856 ngay DD/MM/YYYY - Luc HH:MM ...
     6 so ... Gia tri Doc Dac ... 7,563,375,000" (dau PHAY ngan hang nghin,
     ky khong co so 0 dem -> zfill(5) khi luu). Ten hang giai cung khac:
     "Doc dac", "Giai nhat"..."Giai kk" (khong phai "Giai Doc Dac" nhu
     xosominhngoc) -> duoc chuan hoa ve cung 1 bo ten qua CANON_MAP de
     JSON dau ra nhat quan giua cac nguon.

  vietlott.vn (chinh thuc) KHONG dua vao day: WAF cua trang nay chan IP
  datacenter nen GitHub Actions luon bi 403 (da ghi nhan trong du an).

Cach dung:
    python3 scrape_full_result_json.py --json data/full_results.json

Script se:
  1. Doc draw_id lon nhat da co trong file JSON (neu co).
  2. Quet tu ngay cua ky cuoi -> hom nay (gio VN).
  3. Voi moi ngay, thu tung nguon (theo dung parser cua nguon do) toi khi
     co du lieu; tim TAT CA cac ky quay tren trang do (co the co 2 ky/ngay:
     13h & 21h).
  4. Voi moi ky chua co trong file -> them vao.
  5. Ghi lai JSON, sap xep theo draw_id tang dan.
"""

import argparse
import html
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))

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


def parse_money(s: str) -> int:
    """Bo ca dau cham (xosominhngoc) lan dau phay (minhchinh) ngan hang nghin."""
    return int(s.replace(".", "").replace(",", "").strip())


# ===========================================================================
# Parser rieng cho xosominhngoc.net.vn
# ===========================================================================

XOSO_HEADER_RE = re.compile(
    r"K[ỳy]\s*QSMT:\s*#(\d{5}).{0,80}?"
    r"Ng[àa]y:\s*(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2}):(\d{2})",
    re.DOTALL,
)

XOSO_NUMBERS_RE = re.compile(
    r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})"
)

XOSO_JACKPOT_RE = re.compile(
    r"Gi[áa]\s*tr[ịi]\s*gi[ảa]i\s*[ĐD][ộo]c\s*[ĐĐ][ắa]c\s*([\d\.]+)"
)

# Ten hang giai + dieu kien trung giai theo dung thu tu bang cua Vietlott
# Lotto 5/35. Dieu kien trung giai la co dinh theo luat choi nen hardcode
# luon (tranh loi tach nham voi cot so luong/gia tri khi parse tu van ban).
XOSO_TIER_MATCH_MAP = [
    ("Giải Độc Đắc", "5 số & ĐB"),
    ("Giải Nhất", "5 số"),
    ("Giải Nhì", "4 số & ĐB"),
    ("Giải Ba", "4 số"),
    ("Giải Tư", "3 số & ĐB"),
    ("Giải Năm", "3 số"),
    ("Giải Khuyến Khích", "ĐB"),
]


def _parse_xoso_prize_table(block: str):
    names = [t[0] for t in XOSO_TIER_MATCH_MAP]
    match_map = dict(XOSO_TIER_MATCH_MAP)
    pattern = "(" + "|".join(re.escape(n) for n in names) + ")"
    parts = re.split(pattern, block)
    prizes = []
    for i in range(1, len(parts) - 1, 2):
        tier = parts[i]
        segment = parts[i + 1]
        nums = re.findall(r"\d[\d\.]*", segment)
        if len(nums) < 2:
            continue
        count_str, value_str = nums[-2], nums[-1]
        prizes.append(
            {
                "tier": tier,
                "match": match_map.get(tier, ""),
                "count": int(count_str.replace(".", "")),
                "value": parse_money(value_str),
            }
        )
    return prizes


def parse_xosominhngoc(raw_html: str, page_url: str, fetched_at: str):
    text = strip_html(raw_html)
    headers = list(XOSO_HEADER_RE.finditer(text))
    results = []

    for idx, hm in enumerate(headers):
        draw_id = hm.group(1)
        dd, mm, yyyy = hm.group(2), hm.group(3), hm.group(4)
        hh, minute = hm.group(5), hm.group(6)
        draw_date = f"{yyyy}-{mm}-{dd}"
        draw_time = f"{hh}:{minute}"

        block_start = hm.end()
        block_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        block = text[block_start:block_end]

        nm = XOSO_NUMBERS_RE.search(block)
        if not nm:
            continue
        nums = [int(nm.group(i)) for i in range(1, 7)]
        main_numbers = sorted(nums[:5])
        special_number = nums[5]

        jm = XOSO_JACKPOT_RE.search(block)
        jackpot_value = parse_money(jm.group(1)) if jm else None

        results.append(
            {
                "product": "lotto535",
                "draw_id": draw_id,
                "draw_date": draw_date,
                "draw_time": draw_time,
                "numbers": main_numbers,
                "special_number": special_number,
                "jackpot_value": jackpot_value,
                "prizes": _parse_xoso_prize_table(block),
                "source_url": page_url,
                "fetched_at": fetched_at,
            }
        )
    return results


# ===========================================================================
# Parser rieng cho minhchinh.com
# ===========================================================================

MINHCHINH_HEADER_RE = re.compile(
    r"K[ếe]t\s*qu[ảa]\s*QSMT\s*k[ỳy]\s*#(\d+)\s*ng[àa]y\s*(\d{2})/(\d{2})/(\d{4})\s*"
    r"-\s*L[úu]c\s*(\d{2}):(\d{2})\s*"
    r"((?:\d{1,2}\s*){6})"
    r"Gi[áa]\s*tr[ịi]\s*[ĐĐ][ộo]c\s*[ĐĐ][ắa]c\s*"
    r"([\d,]+)"
)

MINHCHINH_TIER_RE = re.compile(
    r"(Đ[ộo]c\s*đ[ắa]c|Gi[ảa]i\s*nh[ấa]t|Gi[ảa]i\s*nh[ìi]|Gi[ảa]i\s*ba|"
    r"Gi[ảa]i\s*t[ưu]|Gi[ảa]i\s*n[ăa]m|Gi[ảa]i\s*kk)\s*"
    r"([\d,]+)\s+([\d,]+)"
)

# minhchinh.com dung ten hang giai khac xosominhngoc (vd "Doc dac" thay vi
# "Giai Doc Dac") -> chuan hoa ve cung 1 bo ten de JSON nhat quan giua cac nguon.
MINHCHINH_TIER_CANON = {
    "Độc đắc": "Giải Độc Đắc",
    "Giải nhất": "Giải Nhất",
    "Giải nhì": "Giải Nhì",
    "Giải ba": "Giải Ba",
    "Giải tư": "Giải Tư",
    "Giải năm": "Giải Năm",
    "Giải kk": "Giải Khuyến Khích",
}

MINHCHINH_TIER_MATCH_MAP = dict(XOSO_TIER_MATCH_MAP)


def parse_minhchinh(raw_html: str, page_url: str, fetched_at: str):
    text = strip_html(raw_html)
    m = MINHCHINH_HEADER_RE.search(text)
    if not m:
        return []

    draw_id = m.group(1).zfill(5)
    dd, mm, yyyy = m.group(2), m.group(3), m.group(4)
    hh, minute = m.group(5), m.group(6)
    draw_date = f"{yyyy}-{mm}-{dd}"
    draw_time = f"{hh}:{minute}"

    nums = [int(x) for x in re.findall(r"\d{1,2}", m.group(7))]
    if len(nums) < 6:
        return []
    main_numbers = sorted(nums[:5])
    special_number = nums[5]
    jackpot_value = parse_money(m.group(8))

    # Bang 7 giai nam ngay sau phan header trong cung trang.
    rest = text[m.end():]
    prizes = []
    for tier_raw, count_str, value_str in MINHCHINH_TIER_RE.findall(rest)[:7]:
        tier = MINHCHINH_TIER_CANON.get(tier_raw.strip(), tier_raw.strip())
        prizes.append(
            {
                "tier": tier,
                "match": MINHCHINH_TIER_MATCH_MAP.get(tier, ""),
                "count": int(count_str.replace(",", "")),
                "value": parse_money(value_str),
            }
        )

    return [
        {
            "product": "lotto535",
            "draw_id": draw_id,
            "draw_date": draw_date,
            "draw_time": draw_time,
            "numbers": main_numbers,
            "special_number": special_number,
            "jackpot_value": jackpot_value,
            "prizes": prizes,
            "source_url": page_url,
            "fetched_at": fetched_at,
        }
    ]


# ===========================================================================
# Danh sach nguon (thu theo dung thu tu nay cho moi ngay can quet)
# ===========================================================================

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
]


def fetch_day_with_fallback(d, fetched_at: str):
    """Thu tung nguon trong SOURCES cho ngay d (dung parser rieng cua tung
    nguon), tra ve ket qua cua nguon dau tien cao duoc du lieu."""
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
            results = src["parser"](raw, url, fetched_at)
        except Exception as e:
            print(f"  [{src['name']}{tag}] loi parse {url}: {e}", file=sys.stderr)
            continue

        if results:
            print(f"  [{src['name']}{tag}] OK: tim thay {len(results)} ky cho ngay {yyyy}-{mm}-{dd}")
            return results

        print(f"  [{src['name']}{tag}] khong khop du lieu cho ngay {yyyy}-{mm}-{dd}, thu nguon tiep theo")

    print(f"  [!] khong nguon nao cao duoc du lieu cho ngay {yyyy}-{mm}-{dd}", file=sys.stderr)
    return []


def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_json(path: str, rows):
    rows_sorted = sorted(rows, key=lambda r: int(r["draw_id"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows_sorted, f, ensure_ascii=False, indent=2)


def daterange(start_date, end_date):
    d = start_date
    while d <= end_date:
        yield d
        d += timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="data/full_results.json", help="Duong dan file JSON")
    ap.add_argument(
        "--lookback-days",
        type=int,
        default=2,
        help="Quet them tu N ngay truoc ky cuoi cung trong JSON (phong khi thieu sot)",
    )
    args = ap.parse_args()

    rows = load_json(args.json)
    existing_ids = {r["draw_id"] for r in rows}

    now_vn = datetime.now(VN_TZ)
    today_vn = now_vn.date()

    if rows:
        latest_date_str = max(r["draw_date"] for r in rows)
        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
        start_date = latest_date - timedelta(days=args.lookback_days)
    else:
        start_date = today_vn - timedelta(days=args.lookback_days)

    if start_date > today_vn:
        start_date = today_vn

    print(f"JSON hien co {len(rows)} ky.")
    print(f"Quet tu {start_date} den {today_vn} (gio VN), nguon: "
          + ", ".join(s["name"] for s in SOURCES))

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    new_rows = []
    seen_ids_this_run = set()

    for d in daterange(start_date, today_vn):
        day_results = fetch_day_with_fallback(d, fetched_at)
        for r in day_results:
            if r["draw_id"] in existing_ids or r["draw_id"] in seen_ids_this_run:
                continue
            new_rows.append(r)
            seen_ids_this_run.add(r["draw_id"])
            print(
                f"    + ky {r['draw_id']} {r['draw_date']} {r['draw_time']}: "
                f"{r['numbers']} + {r['special_number']} | "
                f"jackpot={r['jackpot_value']}"
            )

    if not new_rows:
        print("Khong co ky moi nao can bo sung.")
        return

    save_json(args.json, rows + new_rows)
    print(f"Da them {len(new_rows)} ky moi vao {args.json}.")


if __name__ == "__main__":
    main()
