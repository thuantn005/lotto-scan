#!/usr/bin/env python3
"""
backtest_consensus_batch.py - Chay hang loat find_consensus_tickets.py
qua TAT CA cac ky da xac nhan TRUOC 1 ky moc (UPTO_DRAW_ID), moi ky chi
dung nhung seed da tung trung THAT o cac ky TRUOC no (khong ro ri du lieu
tuong lai - xem KNOWN_UP_TO_DRAW_ID cua find_consensus_tickets.py), lay
NHOM DONG THUAN CAO NHAT (nhieu seed doc lap dong y nhat) lam "du doan
dai dien" cho ky do, roi so voi ket qua THAT de tinh ty le trung trung
binh - so sanh voi moc ngau nhien (~0.714 so/5).

Dung numpy de vector hoa toan bo phep tinh mix64 (thay vi vong lap
Python thuan cho tung seed nhu find_consensus_tickets.py) - CAN THIET vi
phai lap lai phep tinh cho HANG TRAM ky khac nhau, moi ky co the len den
hang chuc trieu seed.

ENV:
    UPTO_DRAW_ID    - chi backtest cac ky < gia tri nay (BAT BUOC)
    FROM_DRAW_ID    - chi backtest cac ky >= gia tri nay (mac dinh 1 -
                      tuc TAT CA cac ky truoc UPTO_DRAW_ID)
    L1_GLOB / L2_GLOB - nhu find_consensus_tickets.py
    CSV_PATH        - data/all.csv
    OUT_PATH        - file CSV ket qua chi tiet tung ky (mac dinh
                      predict/backtest_consensus_{from}_{upto}.csv)
"""

import csv
import glob
import json
import os
import warnings
from pathlib import Path

import numpy as np

from lotto_common import build_binom, build_rank_to_mask, M1, M2, M3, M4, MASK64, C

warnings.filterwarnings("ignore", category=RuntimeWarning)


def load_all_seed_hit_pairs(l1_glob, l2_glob):
    """Doc TOAN BO seed+hit_draw_id tu L1 va L2 (1 dong / lan trung) vao
    2 mang numpy (seed uint64, hit_draw_id int32) - lam 1 LAN DUY NHAT
    cho toan bo backtest (khong doc lai file cho tung ky)."""
    seeds = []
    hits = []
    for fp in sorted(glob.glob(l1_glob)) if l1_glob else []:
        try:
            data = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Bo qua {fp}: {e}")
            continue
        for d in data.get("draws", []):
            did = d.get("draw_id")
            for s in d.get("seeds") or []:
                seeds.append(s)
                hits.append(did)
        print(f"  Da doc L1: {fp.split('/')[-1]} -> cong don {len(seeds):,} ban ghi")

    for fp in sorted(glob.glob(l2_glob)) if l2_glob else []:
        try:
            data = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Bo qua {fp}: {e}")
            continue
        for p in data.get("promoted", []):
            seed = p["seed"]
            for h in (p.get("hits") or []):
                seeds.append(seed)
                hits.append(h["draw_id"])
        print(f"  Da doc L2: {fp.split('/')[-1]} -> cong don {len(seeds):,} ban ghi")

    seed_arr = np.array(seeds, dtype=np.uint64)
    hit_arr = np.array(hits, dtype=np.int32)
    return seed_arr, hit_arr


def load_actual_results(csv_path):
    out = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 5 or row[3] != "confirmed":
                continue
            try:
                did = int(row[1])
                result = json.loads(row[4])
            except (ValueError, json.JSONDecodeError):
                continue
            out[did] = (sorted(result["numbers"]), result["special_numbers"][0])
    return out


def mix64_vec(x):
    x = x ^ (x >> np.uint64(30))
    x = x * np.uint64(M3)
    x = x ^ (x >> np.uint64(27))
    x = x * np.uint64(M4)
    x = x ^ (x >> np.uint64(31))
    return x


def main():
    upto_draw_id = os.environ.get("UPTO_DRAW_ID")
    if not upto_draw_id:
        raise SystemExit("Can bien moi truong UPTO_DRAW_ID (vi du: UPTO_DRAW_ID=848)")
    upto_draw_id = int(upto_draw_id)
    from_draw_id = int(os.environ.get("FROM_DRAW_ID", "1"))

    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    l2_glob = os.environ.get("L2_GLOB", "l2_merged/promoted_seed*.json")
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    out_path = os.environ.get("OUT_PATH", f"predict/backtest_consensus_{from_draw_id:05d}_{upto_draw_id:05d}.csv")

    print("Dang doc du lieu seed (1 lan duy nhat cho toan bo backtest)...")
    seed_arr, hit_arr = load_all_seed_hit_pairs(l1_glob, l2_glob)
    n_all = seed_arr.size
    print(f"TONG so ban ghi seed+hit: {n_all:,}\n")

    actual_results = load_actual_results(csv_path)
    target_draws = sorted(d for d in actual_results if from_draw_id <= d < upto_draw_id)
    print(f"So ky se backtest ({from_draw_id} <= ky < {upto_draw_id}): {len(target_draws)}\n")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)
    m1 = np.uint64(M1)
    m2 = np.uint64(M2)
    mask64 = np.uint64(MASK64)
    total_tickets_possible = C * 12

    rows_out = []
    total_matches = 0
    total_special_hits = 0
    n_evaluated = 0
    n_j1 = 0

    for i, d in enumerate(target_draws):
        known_mask = hit_arr < d
        n_known = int(known_mask.sum())
        if n_known == 0:
            continue
        sub_seed = seed_arr[known_mask]

        combined = (sub_seed * m1 + np.uint64(d) * m2) & mask64
        mixed = mix64_vec(combined) & mask64
        rank = (mixed % np.uint64(C)).astype(np.int64)
        mixed2 = mix64_vec(mixed) & mask64
        special_idx = (mixed2 % np.uint64(12)).astype(np.int64)
        key = rank * 12 + special_idx

        counts = np.bincount(key, minlength=total_tickets_possible)
        top_key = int(np.argmax(counts))
        top_count = int(counts[top_key])
        top_rank, top_special_idx = divmod(top_key, 12)
        top_special = top_special_idx + 1

        distinct_count = int(np.unique(sub_seed[key == top_key]).size)

        mask_bits = rank_to_mask[top_rank]
        numbers = [k + 1 for k in range(35) if mask_bits & (1 << k)]

        actual_numbers, actual_special = actual_results[d]
        n_match = len(set(numbers) & set(actual_numbers))
        special_hit = (top_special == actual_special)
        is_j1 = (n_match == 5 and special_hit)

        total_matches += n_match
        total_special_hits += int(special_hit)
        n_evaluated += 1
        n_j1 += int(is_j1)

        rows_out.append({
            "draw_id": d,
            "n_known_seeds": n_known,
            "n_distinct_seeds_top_group": distinct_count,
            "top_group_size_raw": top_count,
            "predicted_numbers": "-".join(f"{x:02d}" for x in numbers),
            "predicted_special": top_special,
            "actual_numbers": "-".join(f"{x:02d}" for x in actual_numbers),
            "actual_special": actual_special,
            "n_match": n_match,
            "special_hit": special_hit,
            "is_j1": is_j1,
        })

        if (i + 1) % 50 == 0:
            avg_so_far = total_matches / n_evaluated
            print(f"  ... da xong {i+1}/{len(target_draws)} ky | trung binh so trung tam thoi: {avg_so_far:.4f}")

    print(f"\n=== KET QUA BACKTEST ({n_evaluated} ky co du lieu de danh gia) ===")
    if n_evaluated:
        avg_match = total_matches / n_evaluated
        print(f"Trung binh so TRUNG cua nhom dong thuan cao nhat: {avg_match:.4f} / 5")
        print(f"Moc ngau nhien tham khao (EXPECTED_RANDOM_MATCHES): ~0.7143 / 5")
        print(f"Ty le trung dac biet: {total_special_hits}/{n_evaluated} = {total_special_hits/n_evaluated*100:.2f}% (ngau nhien ~8.33%)")
        print(f"So lan trung TUYET DOI (J1, 5/5 + dac biet): {n_j1}")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        if rows_out:
            writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)
    print(f"\nDa ghi chi tiet tung ky vao {out_path}")


if __name__ == "__main__":
    main()
