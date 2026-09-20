#!/usr/bin/env python3
"""
backtest_coverage_batch.py - Model "PHU RONG": voi MOI model, moi ky,
lay TOP-N ve KHAC NHAU (xep theo so seed doc lap dong thuan GIAM DAN,
ve nao nhieu seed dong thuan nhat xep truoc) - CANG NHIEU N cang "phu"
duoc nhieu to hop hon trong 3.895.584 to hop co the.

Y TUONG: giong dung nhu chuyen xay ra o ky 00392 (xem backtest truoc) -
khi model chi co it seed, no dung HET moi seed sinh ra HET cac ve khac
nhau ma no co. Model nay TONG QUAT HOA dieu do: LUON dung N ve khac
nhau/model/ky (khong quan tam "muc dong thuan" cu the la bao nhieu),
N cang lon thi cang "phu" duoc nhieu to hop, xac suat trung THUAN TUY
THEO TOAN HOC se tang tuyen tinh theo N/3.895.584 - KHONG phai vi doan
"thong minh" hon, chi la mua/thu nhieu ve hon.

Script nay chay backtest voi NHIEU gia tri N khac nhau (xem N_LIST) de
CHUNG MINH BANG SO LIEU THAT ty le trung tang dung theo ty le N, giup
thay ro day la phep toan phu so hoc chu khong phai "mo hinh thong minh
hon".

CANH BAO: N cang lon thi so VE PHAI MUA moi ky cang nhieu (N x so
model) - hoan toan khong thuc te de mua tay (vi du N=1000 x 6 model =
6000 ve/ky). Day la cong cu MO PHONG/CHUNG MINH THONG KE, KHONG phai
goi y nen mua bao nhieu ve that.

ENV:
    UPTO_DRAW_ID    - bat buoc
    FROM_DRAW_ID    - mac dinh 1
    N_LIST          - danh sach cac gia tri N can thu, cach nhau dau
                      phay (mac dinh "10,50,200,1000")
    L1_GLOB/L2_GLOB - nhu cac script khac
    CSV_PATH        - data/all.csv
    OUT_PATH        - file CSV ket qua tong hop theo tung N
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


def mix64_vec(x):
    x = x ^ (x >> np.uint64(30))
    x = x * np.uint64(M3)
    x = x ^ (x >> np.uint64(27))
    x = x * np.uint64(M4)
    x = x ^ (x >> np.uint64(31))
    return x


def load_l1_file(fp):
    data = json.loads(Path(fp).read_text(encoding="utf-8"))
    seeds, hits = [], []
    for d in data.get("draws", []):
        did = d.get("draw_id")
        for s in d.get("seeds") or []:
            seeds.append(s)
            hits.append(did)
    return data.get("seed_start"), np.array(seeds, dtype=np.uint64), np.array(hits, dtype=np.int32)


def load_l2_file(fp):
    data = json.loads(Path(fp).read_text(encoding="utf-8"))
    seeds, hits = [], []
    for p in data.get("promoted", []):
        for h in (p.get("hits") or []):
            seeds.append(p["seed"])
            hits.append(h["draw_id"])
    return data.get("seed_start"), np.array(seeds, dtype=np.uint64), np.array(hits, dtype=np.int32)


def dedupe_seed_hits(seed_arr, hit_arr):
    if seed_arr.size == 0:
        return seed_arr, hit_arr
    order = np.argsort(seed_arr, kind="stable")
    sorted_seed = seed_arr[order]
    sorted_hit = hit_arr[order]
    unique_seed, first_idx = np.unique(sorted_seed, return_index=True)
    earliest_hit = np.minimum.reduceat(sorted_hit, first_idx)
    return unique_seed, earliest_hit


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


def top_n_keys(counts, n):
    """Lay N key co count LON NHAT (giam dan), dung argpartition O(n)
    thay vi sort toan bo (nhanh hon nhieu khi so luong key khac 0 lon)."""
    nonzero_keys = np.where(counts > 0)[0]
    if nonzero_keys.size <= n:
        order = np.argsort(-counts[nonzero_keys])
        return nonzero_keys[order]
    nz_counts = counts[nonzero_keys]
    part = np.argpartition(-nz_counts, n)[:n]
    top = nonzero_keys[part]
    order = np.argsort(-counts[top])
    return top[order]


def main():
    upto_draw_id = os.environ.get("UPTO_DRAW_ID")
    if not upto_draw_id:
        raise SystemExit("Can bien moi truong UPTO_DRAW_ID")
    upto_draw_id = int(upto_draw_id)
    from_draw_id = int(os.environ.get("FROM_DRAW_ID", "1"))
    n_list = [int(x) for x in os.environ.get("N_LIST", "10,50,200,1000").split(",") if x.strip()]

    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    l2_glob = os.environ.get("L2_GLOB", "l2_merged/promoted_seed*.json")
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    out_path = os.environ.get("OUT_PATH", f"predict/backtest_coverage_{from_draw_id:05d}_{upto_draw_id:05d}.csv")

    print("Dang doc du lieu seed...")
    l1_files, l2_files = {}, {}
    for fp in sorted(glob.glob(l1_glob)) if l1_glob else []:
        seed_start, seeds, hits = load_l1_file(fp)
        l1_files[seed_start] = (seeds, hits)
    for fp in sorted(glob.glob(l2_glob)) if l2_glob else []:
        seed_start, seeds, hits = load_l2_file(fp)
        l2_files[seed_start] = (seeds, hits)
    all_seed_starts = sorted(set(l1_files) | set(l2_files))

    model_pool = {}
    for seed_start in all_seed_starts:
        parts_s, parts_h = [], []
        if seed_start in l1_files:
            s, h = l1_files[seed_start]; parts_s.append(s); parts_h.append(h)
        if seed_start in l2_files:
            s, h = l2_files[seed_start]; parts_s.append(s); parts_h.append(h)
        raw_seed = np.concatenate(parts_s) if len(parts_s) > 1 else parts_s[0]
        raw_hit = np.concatenate(parts_h) if len(parts_h) > 1 else parts_h[0]
        model_pool[seed_start] = dedupe_seed_hits(raw_seed, raw_hit)
    print(f"So model: {len(all_seed_starts)}")

    actual_results = load_actual_results(csv_path)
    target_draws = sorted(d for d in actual_results if from_draw_id <= d < upto_draw_id)
    print(f"So ky backtest: {len(target_draws)}\n")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)
    m1, m2, mask64 = np.uint64(M1), np.uint64(M2), np.uint64(MASK64)
    max_n = max(n_list)

    # Voi moi N trong n_list: tong so ve, tong so trung, so dac biet, so J1.
    stats = {n: {"tickets": 0, "matches": 0, "special": 0, "j1": 0} for n in n_list}

    for i, d in enumerate(target_draws):
        actual_numbers, actual_special = actual_results[d]
        actual_set = set(actual_numbers)

        for seed_start in all_seed_starts:
            unique_seeds_all, earliest_hit_all = model_pool[seed_start]
            m = earliest_hit_all < d
            if not m.any():
                continue
            unique_seeds = unique_seeds_all[m]

            combined = (unique_seeds * m1 + np.uint64(d) * m2) & mask64
            mixed = mix64_vec(combined) & mask64
            rank = (mixed % np.uint64(C)).astype(np.int64)
            mixed2 = mix64_vec(mixed) & mask64
            special_idx = (mixed2 % np.uint64(12)).astype(np.int64)
            key = rank * 12 + special_idx
            counts = np.bincount(key, minlength=C * 12)

            top_keys = top_n_keys(counts, max_n)  # tinh 1 LAN cho max_n, cat dan cho cac N nho hon

            for n in n_list:
                sub_keys = top_keys[:n]
                for ck in sub_keys.tolist():
                    r_, sp_idx = divmod(ck, 12)
                    special = sp_idx + 1
                    mask_bits = rank_to_mask[r_]
                    numbers = [k + 1 for k in range(35) if mask_bits & (1 << k)]
                    n_match = len(actual_set & set(numbers))
                    special_hit = (special == actual_special)
                    is_j1 = (n_match == 5 and special_hit)

                    stats[n]["tickets"] += 1
                    stats[n]["matches"] += n_match
                    stats[n]["special"] += int(special_hit)
                    stats[n]["j1"] += int(is_j1)

        if (i + 1) % 50 == 0:
            print(f"  ... da xong {i+1}/{len(target_draws)} ky")

    print(f"\n=== KET QUA - MODEL 'PHU RONG' (top-N ve/model/ky, {len(target_draws)} ky) ===\n")
    print(f"{'N':>6} | {'Tong ve':>10} | {'TB trung/5':>10} | {'%dac biet':>10} | {'So lan J1':>10} | {'Ky vong J1 (ngau nhien)':>24}")
    rows_out = []
    total_possible = C * 12
    for n in n_list:
        s = stats[n]
        avg = s["matches"] / s["tickets"] if s["tickets"] else 0
        pct_special = s["special"] / s["tickets"] * 100 if s["tickets"] else 0
        expected_j1 = s["tickets"] / total_possible
        print(f"{n:>6} | {s['tickets']:>10,} | {avg:>10.4f} | {pct_special:>9.2f}% | {s['j1']:>10} | {expected_j1:>24.4f}")
        rows_out.append({"N": n, "tong_ve": s["tickets"], "trung_binh": round(avg, 4),
                          "pct_dac_biet": round(pct_special, 2), "so_lan_j1": s["j1"],
                          "ky_vong_j1_ngau_nhien": round(expected_j1, 4)})

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    print(f"\nDa ghi {out_path}")


if __name__ == "__main__":
    main()
