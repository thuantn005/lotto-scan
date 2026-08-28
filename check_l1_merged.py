#!/usr/bin/env python3
"""
check_l1_merged.py — Thay the buoc "check_l1" cu, lam viec truc tiep tren
1 file l1_merged/merged_seed{X}.json thay vi thu muc l1/ nhieu file.

Y tuong: vi file l1_merged da quet FULL moi seed trong dai qua TAT CA cac ky,
mot seed trung J1 >=2 lan se tu nhien XUAT HIEN >=2 lan trong cac mang "seeds"
cua cac ky khac nhau trong CHINH file nay - khong can full-scan lai qua CSV.

Hanh dong:
  1. Doc l1_merged/merged_seed{X}.json
  2. Dem so lan xuat hien cua tung seed tren toan bo cac ky
  3. Seed nao xuat hien >=2 lan -> "thang hang":
       - Ghi vao l2_merged/promoted_seed{X}.json (gop voi du lieu cu neu co,
         khong ghi de mat lich su)
       - XOA seed do khoi tung mang "seeds" trong l1_merged (chi xoa dung seed,
         giu nguyen cac seed khac va giu nguyen file, khong xoa ca ky)
  4. Ghi lai l1_merged (da loai seed thang hang) va l2_merged (da cap nhat)

ENV:
    L1_MERGED_FILE  - duong dan file l1_merged (bat buoc phai ton tai)
    L2_MERGED_DIR   - thu muc ghi file l2_merged (mac dinh: l2_merged)
"""

import json
import os
import sys
from collections import defaultdict


def main():
    l1_file = os.environ.get("L1_MERGED_FILE", "")
    l2_dir = os.environ.get("L2_MERGED_DIR", "l2_merged")

    if not l1_file or not os.path.exists(l1_file):
        print(f"Khong tim thay file l1_merged: {l1_file}", file=sys.stderr)
        sys.exit(1)

    with open(l1_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    seed_start = data.get("seed_start")
    draws = data.get("draws", [])

    # Buoc 1: dem so lan xuat hien + luu vi tri hit cua tung seed
    seed_hits = defaultdict(list)  # seed -> [(draw_id, draw_date), ...]
    for d in draws:
        for s in d.get("seeds", []):
            seed_hits[s].append((d["draw_id"], d["draw_date"]))

    promoted = {s: hits for s, hits in seed_hits.items() if len(hits) >= 2}

    print(f"Tong so seed duy nhat trong file: {len(seed_hits)}", file=sys.stderr)
    print(f"So seed thang hang (J1>=2 lan): {len(promoted)}", file=sys.stderr)

    if not promoted:
        print("Khong co seed nao thang hang lan nay.", file=sys.stderr)
        print("PROMOTED_COUNT=0")
        return

    # Buoc 2: doc l2_merged cu (neu co) de gop, tranh mat lich su
    os.makedirs(l2_dir, exist_ok=True)
    l2_file = os.path.join(l2_dir, f"promoted_seed{seed_start}.json")

    existing_promoted = {}
    if os.path.exists(l2_file):
        with open(l2_file, "r", encoding="utf-8") as f:
            old = json.load(f)
        for entry in old.get("promoted", []):
            existing_promoted[entry["seed"]] = entry["hits"]

    # Gop: uu tien du lieu moi nhat vua tinh duoc (day du hon vi file l1_merged
    # cang ngay cang co nhieu ky hon)
    for s, hits in promoted.items():
        existing_promoted[s] = [{"draw_id": did, "draw_date": dt} for did, dt in hits]

    merged_promoted = {
        "seed_start": seed_start,
        "total_promoted": len(existing_promoted),
        "promoted": [
            {"seed": s, "j1_count": len(hits), "hits": hits}
            for s, hits in sorted(existing_promoted.items())
        ],
    }
    with open(l2_file, "w", encoding="utf-8") as f:
        json.dump(merged_promoted, f, separators=(",", ":"))

    # Buoc 3: xoa cac seed thang hang khoi tung mang "seeds" trong l1_merged
    promoted_set = set(promoted.keys())
    total_removed = 0
    for d in draws:
        before = len(d["seeds"])
        d["seeds"] = [s for s in d["seeds"] if s not in promoted_set]
        d["found"] = len(d["seeds"])
        total_removed += before - len(d["seeds"])

    data["total_found"] = sum(d["found"] for d in draws)

    with open(l1_file, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))

    print(f"Da xoa {total_removed} luot xuat hien (cua {len(promoted)} seed) khoi l1_merged", file=sys.stderr)
    print(f"Da cap nhat {l2_file} (tong {len(existing_promoted)} seed da thang hang tu truoc den nay)", file=sys.stderr)
    print(f"PROMOTED_COUNT={len(promoted)}")


if __name__ == "__main__":
    main()
