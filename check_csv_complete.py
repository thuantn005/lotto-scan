#!/usr/bin/env python3
"""Kiem tra data/all.csv khong thieu ky:
 1) khong thung lo draw_id trong 300 ky gan nhat (lo xa hon -> canh bao)
 2) co ky moi nhat theo lich quay 13:00 va 21:00 VN (tru 30 phut cho ket qua len)
Ghi bad=true/false vao $GITHUB_OUTPUT (luon exit 0 de buoc commit van chay)."""
import csv, os, sys
from datetime import datetime, timedelta, timezone

VN = timezone(timedelta(hours=7))
path = sys.argv[1] if len(sys.argv) > 1 else "data/all.csv"
rows = [r for r in csv.DictReader(open(path, encoding="utf-8", newline="")) if (r.get("draw_id") or "").isdigit()]
ids = sorted({int(r["draw_id"]) for r in rows})
bad = []
if not ids:
    bad.append("CSV rong")
else:
    full = set(range(ids[0], ids[-1] + 1))
    holes = sorted(full - set(ids))
    recent_holes = [h for h in holes if h > ids[-1] - 300]
    if recent_holes:
        bad.append(f"THIEU ky trong 300 ky gan nhat: {recent_holes[:30]}")
    elif holes:
        print(f"::warning::CSV thieu ky xa hon (khong anh huong quet gan): {holes[:20]}")

    now = datetime.now(VN)
    if os.environ.get("FAKE_NOW"):
        now = datetime.fromisoformat(os.environ["FAKE_NOW"]).replace(tzinfo=VN)
    t = now - timedelta(minutes=30)
    slots = []
    for off in (0, 1, 2):
        d = (t - timedelta(days=off)).date()
        for h in (13, 21):
            s = datetime(d.year, d.month, d.day, h, 0, tzinfo=VN)
            if s <= t:
                slots.append((s, h))
    s, h = max(slots)
    sd = s.strftime("%Y-%m-%d")
    cnt = sum(1 for r in rows if r["draw_date"] == sd)
    need = 1 if h == 13 else 2
    print(f"Ky cuoi: {ids[-1]} | ky quay gan nhat theo lich: {sd} {h}:00 | so ky ngay {sd} trong CSV: {cnt} (can >= {need})")
    if cnt < need:
        bad.append(f"CHUA co ky {sd} {h}:00 trong CSV (co {cnt}/{need})")
for b in bad:
    print("::error::" + b)
if not bad:
    print("OK: CSV day du")
if os.environ.get("GITHUB_OUTPUT"):
    open(os.environ["GITHUB_OUTPUT"], "a").write(f"bad={'true' if bad else 'false'}\n")
