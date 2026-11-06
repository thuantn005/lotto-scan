#!/usr/bin/env python3
"""Cao ket qua Mega 6/45 (du phong) tu xosominhngoc.net.vn, bo sung ky con thieu vao data/mega_all.csv.
Dung khi dataset NhanAZ-Data cap nhat cham. Mega quay Thu 4 / Thu 6 / Chu nhat luc 18:00 (gio VN).
  python3 scrape_mega_fallback.py --csv data/mega_all.csv --lookback-days 14
Parser theo CUNG khuon trang voi Lotto 5/35 ('Ky QSMT: #NNNNN ... Ngay: DD/MM/YYYY ... 6 so'); neu trang doi cau truc se
bo qua (khong ghi gi) - nguon chinh van la dataset. Chi them dong co 6 so khac nhau trong 1..45."""
import argparse, csv, json, re, sys
from datetime import datetime, timedelta, timezone
from scrape_xosominhngoc_fallback import strip_html, fetch, FIELDNAMES, load_csv, save_csv, daterange

VN = timezone(timedelta(hours=7))
BLOCK = re.compile(
    r"K[ỳy]\s*QSMT:\s*#(\d{5}).{0,300}?Ng[àa]y:\s*(\d{2})/(\d{2})/(\d{4}).{0,600}?"
    r"((?:\d{2}\s+){5}\d{2})(?!\d)", re.DOTALL)
URLS = ["https://xosominhngoc.net.vn/kqxs-mega-645-ngay-{dd}-{mm}-{yyyy}",
        "https://xosominhngoc.net.vn/kqxs-mega-6-45-ngay-{dd}-{mm}-{yyyy}"]

def parse(raw, url, fetched_at):
    rows = []
    for m in BLOCK.finditer(strip_html(raw)):
        nums = sorted(int(x) for x in m.group(5).split())
        if len(set(nums)) != 6 or not all(1 <= n <= 45 for n in nums):
            continue
        did, dd, mm, yy = m.group(1), m.group(2), m.group(3), m.group(4)
        rows.append({"product": "mega645", "draw_id": did, "draw_date": f"{yy}-{mm}-{dd}", "draw_status": "confirmed",
                     "result_json": json.dumps({"numbers": nums, "special_numbers": []}, ensure_ascii=False),
                     "attributes_json": json.dumps({"data_source": url, "detail_title": f"Kỳ quay thưởng #{did} ngày {dd}/{mm}/{yy}",
                                                    "official_list_verified_at": fetched_at}, ensure_ascii=False),
                     "official_pdf_urls_json": "[]", "source_url": url, "prize_status": "complete",
                     "validation_status": "valid", "validation_warnings_json": "[]", "fetched_at": fetched_at})
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", default="data/mega_all.csv"); ap.add_argument("--lookback-days", type=int, default=14)
    a = ap.parse_args()
    rows = load_csv(a.csv)
    if not rows: print("CSV Mega rong, bo qua fallback.", file=sys.stderr); return
    have = {int(r["draw_id"]) for r in rows}
    last = datetime.strptime(max(r["draw_date"] for r in rows), "%Y-%m-%d").date()
    today = datetime.now(VN).date(); start = min(last - timedelta(days=a.lookback_days), today)
    print(f"CSV Mega {len(rows)} ky, moi nhat {last}; quet {start} -> {today}")
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"); new = {}
    for d in daterange(start, today):
        if d.weekday() not in (2, 4, 6): continue          # Thu 4 / Thu 6 / Chu nhat
        for t in URLS:
            url = t.format(dd=d.strftime("%d"), mm=d.strftime("%m"), yyyy=d.strftime("%Y"))
            try: got = parse(fetch(url), url, fetched_at)
            except Exception as e: print(f"  loi {url}: {type(e).__name__}: {e}", file=sys.stderr); continue
            got = [r for r in got if r["draw_date"] == d.isoformat()]
            if got:
                for r in got:
                    if int(r["draw_id"]) not in have: new[int(r["draw_id"])] = r; print(f"    + ky {r['draw_id']} {r['draw_date']}: {r['result_json']}")
                break
    if not new: print("Khong co ky Mega moi."); return
    save_csv(a.csv, rows + [new[k] for k in sorted(new)]); print(f"Da them {len(new)} ky Mega.")
if __name__ == "__main__": main()
