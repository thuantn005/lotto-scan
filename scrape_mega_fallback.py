#!/usr/bin/env python3
"""Cao ket qua Mega 6/45 (du phong khi dataset NhanAZ-Data cham) vao data/mega_all.csv.
Mega quay Thu 4 / Thu 6 / Chu nhat 18:00 (gio VN). Nguon (da kiem chung voi trang that ngay 09/11/2026):
  1) https://xosominhngoc.net.vn/kqxs-mega-645-ngay-DD-MM-YYYY   (moi ngay 1 trang; co 'ky #01586 ... ngay 08/11/2026: bo so 01 02 14 20 23 36' va 'Ky ve #01586 ... Bo so trung thuong')
  2) https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-mega-645.html  (ky moi nhat: 'Ket qua QSMT ky #1585 ngay 06/11/2026 01 10 37 38 39 45')
  python3 scrape_mega_fallback.py --csv data/mega_all.csv --lookback-days 14
Chi them dong khi: 6 so khac nhau trong 1..45, ngay trang == ngay can lay, ky chua co trong CSV."""
import argparse, json, re, sys
from datetime import datetime, timedelta, timezone
from scrape_xosominhngoc_fallback import strip_html, fetch, FIELDNAMES, load_csv, save_csv, daterange
VN = timezone(timedelta(hours=7))
NUM6 = r"((?:\d{2}[\s,;-]+){5}\d{2})(?!\d)"
# xosominhngoc: cau tom tat o cuoi trang va khung ket qua
P_SUM = re.compile(r"k[ỳy]\s*#?\s*(\d{4,6})\s*[^\d]{0,40}?ng[àa]y\s*(\d{2})/(\d{2})/(\d{4})\s*:?\s*b[ộo]\s*s[ốo]\s*" + NUM6, re.I | re.S)
P_BOX = re.compile(r"K[ỳy]\s*v[ée]\s*#?\s*(\d{4,6}).{0,300}?B[ộo]\s*s[ốo]\s*tr[úu]ng\s*th[ưu][ởo]ng\s*" + NUM6, re.I | re.S)
P_DATE = re.compile(r"M[ởo]\s*th[ưu][ởo]ng.{0,40}?ng[àa]y\s*(\d{2})/(\d{2})/(\d{4})", re.I | re.S)
# minhchinh: 'Ket qua QSMT ky #1585 ngay 06/11/2026  01 10 37 38 39 45'
P_MC = re.compile(r"k[ỳy]\s*#?\s*(\d{3,6})\s*ng[àa]y\s*(\d{2})/(\d{2})/(\d{4})\s*" + NUM6, re.I | re.S)

def nums_of(s):
    n = sorted(int(x) for x in re.findall(r"\d{2}", s))
    return n if len(n) == 6 and len(set(n)) == 6 and all(1 <= x <= 45 for x in n) else None

def parse_xsmn(raw, want):                      # want = date.isoformat
    t = strip_html(raw); out = []
    for m in P_SUM.finditer(t):
        n = nums_of(m.group(5))
        if n: out.append((int(m.group(1)), f"{m.group(4)}-{m.group(3)}-{m.group(2)}", n))
    for m in P_BOX.finditer(t):
        n = nums_of(m.group(2)); d = P_DATE.search(t[max(0, m.start() - 300):m.end()])
        if n and d: out.append((int(m.group(1)), f"{d.group(3)}-{d.group(2)}-{d.group(1)}", n))
    return [r for r in out if r[1] == want]

def parse_minhchinh(raw, want):
    out = []
    for m in P_MC.finditer(strip_html(raw)):
        n = nums_of(m.group(5))
        if n: out.append((int(m.group(1)), f"{m.group(4)}-{m.group(3)}-{m.group(2)}", n))
    return [r for r in out if r[1] == want]

SOURCES = [("xosominhngoc.net.vn", "https://xosominhngoc.net.vn/kqxs-mega-645-ngay-{dd}-{mm}-{yyyy}", parse_xsmn),
           ("minhchinh.com", "https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-mega-645.html", parse_minhchinh)]

def make_row(did, date, nums, url, fetched_at):
    return {"product": "mega645", "draw_id": f"{did:05d}", "draw_date": date, "draw_status": "confirmed",
            "result_json": json.dumps({"numbers": nums}, ensure_ascii=False, separators=(",", ":")),
            "attributes_json": json.dumps({"data_source": "xosominhngoc_net_vn" if "xosominhngoc" in url else "minhchinh_com", "official_verification_status": "pending",
                                           "secondary_source_url": url, "upstream_claimed_source": "Vietlott"}, ensure_ascii=False, separators=(",", ":")),
            "official_pdf_urls_json": "[]", "source_url": url, "prize_status": "secondary_complete", "validation_status": "valid",
            "validation_warnings_json": "[]", "fetched_at": fetched_at}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", default="data/mega_all.csv"); ap.add_argument("--lookback-days", type=int, default=14)
    a = ap.parse_args(); rows = load_csv(a.csv)
    if not rows: print("CSV Mega rong, bo qua fallback.", file=sys.stderr); return
    have = {int(r["draw_id"]) for r in rows}; mx = max(have); have_dates = {r["draw_date"] for r in rows}
    last = datetime.strptime(max(r["draw_date"] for r in rows), "%Y-%m-%d").date()
    today = datetime.now(VN).date(); start = min(last - timedelta(days=a.lookback_days), today)
    print(f"CSV Mega {len(rows)} ky, moi nhat ky {mx} ngay {last}; quet {start} -> {today}")
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"); new = {}
    for d in daterange(start, today):
        if d.weekday() not in (2, 4, 6) or d.isoformat() in have_dates: continue   # Thu 4 / Thu 6 / Chu nhat; bo ngay da co
        got = None
        for name, tpl, parser in SOURCES:
            url = tpl.format(dd=d.strftime("%d"), mm=d.strftime("%m"), yyyy=d.strftime("%Y"))
            try: res = parser(fetch(url), d.isoformat())
            except Exception as e: print(f"  [{name}] {d}: loi {type(e).__name__}: {e}", file=sys.stderr); continue
            if res: got = (res[0], url, name); break
            print(f"  [{name}] {d}: khong thay ket qua (chua cap nhat hoac doi cau truc)")
        if got:
            (did, date, nums), url, name = got
            if did not in have: new[did] = make_row(did, date, nums, url, fetched_at); print(f"    + ky {did:05d} {date} {nums} [{name}]")
    if not new: print("Khong co ky Mega moi."); return
    ids = sorted(new)
    if ids[0] != mx + 1: print(f"::warning::ky moi {ids[0]} khong lien tiep voi ky cuoi {mx} (thieu ky?) - van them", file=sys.stderr)
    save_csv(a.csv, rows + [new[k] for k in ids]); print(f"Da them {len(new)} ky Mega.")
if __name__ == "__main__": main()
