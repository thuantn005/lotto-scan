#!/usr/bin/env python3
"""
check_l1_per_draw.py - Ban thay the cho check_l1_merged.py, lam viec tren
THU MUC per-draw (l1-1/ hoac l1-2/, moi ky 1 file - xem split_l1_per_draw.py)
thay vi 1 file l1_merged/merged_seed{X}.json gop.

Y tuong GIU NGUYEN 100% tu check_l1_merged.py: vi thu muc L1 da quet FULL
moi seed trong dai qua TAT CA cac ky (dang nam trong cua so hien tai), mot
seed trung J1 >=2 lan se tu nhien XUAT HIEN >=2 lan trong "seeds" cua cac
file ky khac nhau - khong can full-scan lai qua CSV.

NGUONG THANG HANG LA SO CO DINH (PROMOTION_MIN_WEIGHT, mac dinh 2).

Hanh dong:
  1. Doc TAT CA file *.json trong L1_DIR (moi file = 1 ky)
  2. Dem so lan xuat hien cua tung seed tren toan bo cac ky
  3. Seed nao xuat hien >= PROMOTION_MIN_WEIGHT -> "thang hang":
       - Ghi vao l2_merged/promoted_seed{X}.json (gop voi du lieu cu neu
         co, khong ghi de mat lich su) - DAY LA NOI LUU "KY MA SEED QUET
         TRUNG" (khong lien quan gi den du doan).
       - XOA seed do khoi tung file ky trong L1_DIR (chi ghi lai NHUNG
         file ky co thay doi, khong dong vao file khong lien quan)

ENV:
    L1_DIR               - thu muc per-draw (bat buoc, vd l1-1 hoac l1-2)
    L2_MERGED_DIR         - thu muc ghi file l2_merged (mac dinh: l2_merged)
    PROMOTION_MIN_WEIGHT  - nguong thang hang (mac dinh 2)
"""
import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


def main():
    l1_dir = os.environ.get("L1_DIR", "")
    l2_dir = os.environ.get("L2_MERGED_DIR", "l2_merged")
    threshold = int(os.environ.get("PROMOTION_MIN_WEIGHT", "2"))

    if not l1_dir or not os.path.isdir(l1_dir):
        print(f"Khong tim thay thu muc L1_DIR: {l1_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(glob.glob(os.path.join(l1_dir, "*.json")))
    draws = []
    seed_start = None
    for fp in files:
        try:
            d = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Bo qua file loi: {fp} ({e})", file=sys.stderr)
            continue
        if "draw_id" not in d or "seeds" not in d:
            continue
        d["_file"] = fp
        draws.append(d)
        if seed_start is None:
            seed_start = d.get("seed_start")

    if not draws:
        print(f"Khong co file ky nao trong {l1_dir}, bo qua.", file=sys.stderr)
        print("PROMOTED_COUNT=0")
        return

    print(f"So ky trong {l1_dir}: {len(draws)}", file=sys.stderr)

    # Buoc 1: dem so lan xuat hien + luu vi tri hit cua tung seed
    seed_hits = defaultdict(list)  # seed -> [(draw_id, draw_date), ...]
    for d in draws:
        for s in d.get("seeds", []):
            seed_hits[s].append((d["draw_id"], d.get("draw_date")))

    promoted = {s: hits for s, hits in seed_hits.items() if len(hits) >= threshold}

    print(f"Tong so seed duy nhat trong {l1_dir}: {len(seed_hits)}", file=sys.stderr)
    print(f"So seed thang hang (weight>={threshold}): {len(promoted)}", file=sys.stderr)

    if not promoted:
        print("Khong co seed nao thang hang lan nay.", file=sys.stderr)
        print("PROMOTED_COUNT=0")
        return

    # Buoc 2: doc l2_merged cu (neu co) de gop, tranh mat lich su
    os.makedirs(l2_dir, exist_ok=True)
    l2_file = os.path.join(l2_dir, f"promoted_seed{seed_start}.json")

    existing_promoted = {}
    if os.path.exists(l2_file):
        old = json.loads(Path(l2_file).read_text(encoding="utf-8"))
        for entry in old.get("promoted", []):
            existing_promoted[entry["seed"]] = entry["hits"]

    for s, hits in promoted.items():
        existing_promoted[s] = [{"draw_id": did, "draw_date": dt} for did, dt in hits]

    by_draw = {}
    for s, hits in existing_promoted.items():
        for h in hits:
            entry = by_draw.setdefault(h["draw_id"], {"draw_id": h["draw_id"],
                                                      "draw_date": h.get("draw_date"), "seeds": []})
            entry["seeds"].append(s)
    draws_index = []
    for did in sorted(by_draw):
        e = by_draw[did]
        e["seeds"].sort()
        e["found"] = len(e["seeds"])
        draws_index.append(e)

    merged_promoted = {
        "seed_start": seed_start,
        "total_promoted": len(existing_promoted),
        "promoted": [
            {"seed": s, "j1_count": len(hits), "hits": hits}
            for s, hits in sorted(existing_promoted.items())
        ],
        "draws": draws_index,
    }
    Path(l2_file).write_text(json.dumps(merged_promoted, separators=(",", ":")), encoding="utf-8")

    # Buoc 3: xoa cac seed thang hang khoi TUNG FILE KY (chi ghi lai file
    # co thay doi thuc su, khong dong vao file khong lien quan).
    promoted_set = set(promoted.keys())
    total_removed = 0
    files_rewritten = 0
    for d in draws:
        before = len(d["seeds"])
        new_seeds = [s for s in d["seeds"] if s not in promoted_set]
        if len(new_seeds) == before:
            continue
        d["seeds"] = new_seeds
        d["found"] = len(new_seeds)
        total_removed += before - len(new_seeds)
        fp = d.pop("_file")
        payload = {k: v for k, v in d.items() if k != "_file"}
        Path(fp).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        files_rewritten += 1

    print(f"Da xoa {total_removed} luot xuat hien (cua {len(promoted)} seed) khoi {files_rewritten} file ky",
          file=sys.stderr)
    print(f"Da cap nhat {l2_file} (tong {len(existing_promoted)} seed da thang hang tu truoc den nay)",
          file=sys.stderr)
    print(f"PROMOTED_COUNT={len(promoted)}")


if __name__ == "__main__":
    main()
