#!/usr/bin/env python3
"""Kiem tra data/mega_all.csv: khong thung lo trong 300 ky gan nhat; ky moi nhat so voi lich Thu 4/Thu 6/CN 18:00 VN (+30 phut).
Chi canh bao (luon exit 0)."""
import csv, sys
from datetime import datetime, timedelta, timezone
VN = timezone(timedelta(hours=7)); path = sys.argv[1] if len(sys.argv) > 1 else "data/mega_all.csv"
rows = [r for r in csv.DictReader(open(path, encoding="utf-8", newline="")) if (r.get("draw_id") or "").isdigit()]
ids = sorted({int(r["draw_id"]) for r in rows})
if not ids: print("::warning::CSV Mega rong"); sys.exit(0)
holes = [h for h in set(range(ids[0], ids[-1] + 1)) - set(ids) if h > ids[-1] - 300]
if holes: print(f"::warning::Mega THIEU ky gan day: {sorted(holes)[:30]}")
t = datetime.now(VN) - timedelta(minutes=30); d = t.date()
while True:
    s = datetime(d.year, d.month, d.day, 18, tzinfo=VN)
    if d.weekday() in (2, 4, 6) and s <= t: break
    d -= timedelta(days=1)
cnt = sum(1 for r in rows if r["draw_date"] == d.isoformat())
print(f"Mega ky cuoi {ids[-1]} | ky quay gan nhat theo lich: {d} 18:00 | so ky ngay do trong CSV: {cnt}")
if cnt < 1: print(f"::warning::Mega chua co ky ngay {d} (nguon cap nhat tre?) - se thu lai o lan chay sau")
