#!/usr/bin/env python3
"""
check_l1_merged.py - Thay the buoc "check_l1" cu, lam viec truc tiep tren
1 file l1_merged/merged_seed{X}.json thay vi thu muc l1/ nhieu file.

Y tuong: vi file l1_merged da quet FULL moi seed trong dai qua TAT CA cac ky,
mot seed trung J1 >=2 lan se tu nhien XUAT HIEN >=2 lan trong cac mang
"seeds" cua cac ky khac nhau trong CHINH file nay - khong can full-scan lai
qua CSV.

NGUONG THANG HANG LA SO CO DINH (PROMOTION_MIN_WEIGHT, mac dinh 2) - GIONG
NHAU cho MOI model, KHONG tu dong dieu chinh theo tung model.

Chi de THAM KHAO (khong anh huong toi quyet dinh thang hang): script van
in ra so seed KY VONG dat duoc nguong nay THUAN TUY NGAU NHIEN (khong lien
quan gi den ket qua that) tren toan bo dai seed cua model do - xem
lotto_common.expected_false_positive_count(). Con so nay giup biet nguong
hien tai "chat" hay "long" voi model cu the, nhung KHONG duoc dung de tu
dong doi nguong.

Hanh dong:
  1. Doc l1_merged/merged_seed{X}.json
  2. Dem so lan xuat hien cua tung seed tren toan bo cac ky
  3. Seed nao xuat hien >= PROMOTION_MIN_WEIGHT -> "thang hang":
       - Ghi vao l2_merged/promoted_seed{X}.json (gop voi du lieu cu neu co,
         khong ghi de mat lich su)
       - XOA seed do khoi tung mang "seeds" trong l1_merged (chi xoa dung seed,
         giu nguyen cac seed khac va giu nguyen file, khong xoa ca ky)
  4. Ghi lai l1_merged (da loai seed thang hang) va l2_merged (da cap nhat)

ENV:
    L1_MERGED_FILE       - duong dan file l1_merged (bat buoc phai ton tai)
    L2_MERGED_DIR        - thu muc ghi file l2_merged (mac dinh: l2_merged)
    PROMOTION_MIN_WEIGHT - nguong thang hang CO DINH, ap dung cho MOI model
                           giong nhau (mac dinh 2, giu nguyen hanh vi cu)
"""

import json
import os
import sys
from collections import defaultdict

from lotto_common import expected_false_positive_count


def main():
    l1_file = os.environ.get("L1_MERGED_FILE", "")
    l2_dir = os.environ.get("L2_MERGED_DIR", "l2_merged")
    threshold = int(os.environ.get("PROMOTION_MIN_WEIGHT", "2"))

    if not l1_file or not os.path.exists(l1_file):
        print(f"Khong tim thay file l1_merged: {l1_file}", file=sys.stderr)
        sys.exit(1)

    with open(l1_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    seed_start = data.get("seed_start")
    seed_end = data.get("seed_end")
    draws = data.get("draws", [])
    seed_count = (seed_end - seed_start + 1) if (seed_start is not None and seed_end is not None) else None
    num_draws = len(draws)

    # Chi de THAM KHAO trong log - KHONG dung de doi nguong.
    if seed_count:
        expected_at_threshold = expected_false_positive_count(seed_count, num_draws, threshold)
        print(f"So ky trong file: {num_draws}, seed_count: {seed_count}", file=sys.stderr)
        print(f"Nguong thang hang (CO DINH, khong tu dieu chinh): weight >= {threshold} "
              f"(tham khao: ky vong ~{expected_at_threshold:.4g} seed dat nguong nay THUAN TUY "
              f"NGAU NHIEN tren toan bo dai)", file=sys.stderr)

    # Buoc 1: dem so lan xuat hien + luu vi tri hit cua tung seed
    seed_hits = defaultdict(list)  # seed -> [(draw_id, draw_date), ...]
    for d in draws:
        for s in d.get("seeds", []):
            seed_hits[s].append((d["draw_id"], d["draw_date"]))

    promoted = {s: hits for s, hits in seed_hits.items() if len(hits) >= threshold}

    print(f"Tong so seed duy nhat trong file: {len(seed_hits)}", file=sys.stderr)
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
