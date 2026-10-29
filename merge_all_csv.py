#!/usr/bin/env python3
"""Gop CSV tai ve (data/all.new) voi data/all.csv dang co trong repo, theo draw_id.
Khong bao gio mat ky: ky nao co o 1 trong 2 file deu duoc giu (uu tien dong cua file moi tai ve).
Dung: python3 merge_all_csv.py --new data/all.new --old data/all.csv"""
import argparse, csv, os, sys

def load(p):
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return [], []
    with open(p, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        rows = [x for x in r if (x.get("draw_id") or "").strip().isdigit()]
        return list(r.fieldnames or []), rows

ap = argparse.ArgumentParser()
ap.add_argument("--new", required=True)
ap.add_argument("--old", required=True)
a = ap.parse_args()
fn_new, new = load(a.new)
fn_old, old = load(a.old)
fields = fn_new or fn_old
if not fields:
    print("::error::Khong co du lieu (ca file moi lan cu deu rong)"); sys.exit(1)
by_id = {int(r["draw_id"]): r for r in old}
n_old = len(by_id)
for r in new:
    by_id[int(r["draw_id"])] = r
with open(a.old, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for k in sorted(by_id):
        w.writerow(by_id[k])
print(f"Cu: {n_old} ky | tai ve: {len(new)} ky | sau khi gop: {len(by_id)} ky (moi nhat {max(by_id)})")
if new and old and len(new) < n_old:
    print(f"::warning::File tai ve ({len(new)}) ngan hon file cu ({n_old}) - da giu cac ky cu")
