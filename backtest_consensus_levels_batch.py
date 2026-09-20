#!/usr/bin/env python3
"""
backtest_consensus_levels_batch.py - Mo phong DUNG logic san xuat cua
predict_next_draw_consensus.py (nhieu ve/muc/model, model
682305800400/1903987714639 dung MODEL_LEVELS thu cong, cac model khac
dung PREFERRED_LEVELS tu dong) qua TAT CA cac ky da xac nhan trong 1
khoang, moi ky CHI dung seed da tung trung THAT TRUOC no (khong ro ri
tuong lai - dung KNOWN_UP_TO nhu backtest_consensus_batch.py), roi so
TAT CA cac ve sinh ra voi ket qua THAT de xem co ve nao tung trung cao
(dac biet la trung tuyet doi/J1) hay khong.

Dung lai TRUC TIEP cac ham tu predict_next_draw_consensus.py (import
module) de dam bao logic BACKTEST GIONG HET logic SAN XUAT (cung cong
thuc chon ve, cung random seed tai lap) - khong viet lai rieng.

ENV: giong backtest_consensus_batch.py (UPTO_DRAW_ID bat buoc,
FROM_DRAW_ID mac dinh 1, L1_GLOB/L2_GLOB, CSV_PATH, OUT_PATH) cong them
MODEL_LEVELS / PREFERRED_LEVELS / DEFAULT_LEVEL giong
predict_next_draw_consensus.py.
"""

import csv
import glob
import json
import os
import random
import warnings
from pathlib import Path

import numpy as np

import predict_next_draw_consensus as pc
from lotto_common import build_binom, build_rank_to_mask, M1, M2, MASK64, C

warnings.filterwarnings("ignore", category=RuntimeWarning)


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


def extract_ticket_at_level(counts, key, unique_seeds, target_level, rng, n_tickets=2):
    """Giong find_ticket_at_level() nhung dung LAI counts/key da tinh
    san TREN SEED DA KHU TRUNG (khong tinh lai hash) - de tai su dung
    cho NHIEU muc/model/ky ma chi phai tinh hash 1 LAN DUY NHAT. Tra ve
    toi da n_tickets ve PHAN BIET (khop voi
    predict_next_draw_consensus.py hien tai: 2 ve/muc mac dinh)."""
    nonzero_keys = np.where(counts > 0)[0]
    if nonzero_keys.size == 0:
        return []
    nonzero_counts = counts[nonzero_keys]
    exact = nonzero_keys[nonzero_counts == target_level]
    if exact.size > 0:
        candidates = sorted(exact.tolist())
        matched_exact = True
    else:
        diffs = np.abs(nonzero_counts.astype(np.int64) - target_level)
        min_diff = diffs.min()
        best = nonzero_keys[diffs == min_diff]
        best_counts = counts[best]
        top_available = int(best_counts.max())
        candidates = sorted(best[best_counts == top_available].tolist())
        matched_exact = False

    n_pick = min(n_tickets, len(candidates))
    chosen_keys = rng.sample(candidates, n_pick)
    results = []
    for chosen_key in chosen_keys:
        top_rank, top_sp_idx = divmod(chosen_key, 12)
        top_special = top_sp_idx + 1
        n_actual = int(counts[chosen_key])
        results.append((top_rank, top_special, n_actual, matched_exact))
    return results


def dedupe_seed_hits(seed_arr, hit_arr):
    """Khu trung 1 LAN DUY NHAT: gop theo seed, lay KY TRUNG SOM NHAT
    (min) cho tung seed - vi 1 seed chi can co MOT lan trung TRUOC ky d
    la da duoc tinh la 'da biet' tai thoi diem d, bat ke sau do con
    trung them may lan nua. Lam viec nay 1 LAN cho ca model (thay vi
    goi np.unique() MOI KY trong vong lap chinh - qua cham, ~8s/ky voi
    mang vai trieu phan tu x 890 ky = hang gio dong ho) giup vong lap
    chinh chi can 1 phep loc boolean re tien (hit_som_nhat < d) MOI
    KY, khong con phai sap xep/khu trung lai tu dau."""
    if seed_arr.size == 0:
        return seed_arr, hit_arr
    order = np.argsort(seed_arr, kind="stable")
    sorted_seed = seed_arr[order]
    sorted_hit = hit_arr[order]
    unique_seed, first_idx = np.unique(sorted_seed, return_index=True)
    earliest_hit = np.minimum.reduceat(sorted_hit, first_idx)
    return unique_seed, earliest_hit


def main():
    upto_draw_id = os.environ.get("UPTO_DRAW_ID")
    if not upto_draw_id:
        raise SystemExit("Can bien moi truong UPTO_DRAW_ID (vi du: UPTO_DRAW_ID=895)")
    upto_draw_id = int(upto_draw_id)
    from_draw_id = int(os.environ.get("FROM_DRAW_ID", "1"))

    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    l2_glob = os.environ.get("L2_GLOB", "l2_merged/promoted_seed*.json")
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    out_path = os.environ.get("OUT_PATH", f"predict/backtest_consensus_levels_{from_draw_id:05d}_{upto_draw_id:05d}.csv")

    default_level = int(os.environ.get("DEFAULT_LEVEL", "2"))
    preferred_levels_raw = os.environ.get("PREFERRED_LEVELS", "4,5,6,7")
    preferred_levels = [int(x) for x in preferred_levels_raw.split(",") if x.strip()]
    tickets_per_level = int(os.environ.get("TICKETS_PER_LEVEL", "2"))
    model_levels_raw = os.environ.get("MODEL_LEVELS")
    if model_levels_raw:
        model_levels = {str(k): v for k, v in json.loads(model_levels_raw).items()}
    else:
        model_levels = dict(pc.DEFAULT_MODEL_LEVELS)

    print("Dang doc du lieu seed (1 lan duy nhat cho toan bo backtest)...")
    l1_files = {}
    for fp in sorted(__import__("glob").glob(l1_glob)) if l1_glob else []:
        seed_start, seeds, hits = pc.load_l1_file(fp)
        l1_files[seed_start] = (fp, seeds, hits)
        print(f"  L1: {fp.split('/')[-1]} -> {seeds.size:,} ban ghi")

    l2_files = {}
    for fp in sorted(__import__("glob").glob(l2_glob)) if l2_glob else []:
        seed_start, seeds, hits = pc.load_l2_file(fp)
        l2_files[seed_start] = (fp, seeds, hits)
        print(f"  L2: {fp.split('/')[-1]} -> {seeds.size:,} ban ghi")

    all_seed_starts = sorted(set(l1_files) | set(l2_files))
    print(f"Tong so model: {len(all_seed_starts)}")

    print("Dang gop L1+L2 va khu trung 1 lan cho tung model (chi lam 1 LAN, khong lap lai moi ky)...")
    model_pool = {}  # seed_start -> (unique_seeds, earliest_hit) - DA khu trung
    for seed_start in all_seed_starts:
        parts_s, parts_h = [], []
        if seed_start in l1_files:
            _, s, h = l1_files[seed_start]
            parts_s.append(s); parts_h.append(h)
        if seed_start in l2_files:
            _, s, h = l2_files[seed_start]
            parts_s.append(s); parts_h.append(h)
        raw_seed = np.concatenate(parts_s) if len(parts_s) > 1 else parts_s[0]
        raw_hit = np.concatenate(parts_h) if len(parts_h) > 1 else parts_h[0]
        model_pool[seed_start] = dedupe_seed_hits(raw_seed, raw_hit)
        print(f"  Model {seed_start}: {raw_seed.size:,} ban ghi tho -> {model_pool[seed_start][0].size:,} seed doc lap (da khu trung)")
    print()

    actual_results = load_actual_results(csv_path)
    target_draws = sorted(d for d in actual_results if from_draw_id <= d < upto_draw_id)
    print(f"So ky se backtest ({from_draw_id} <= ky < {upto_draw_id}): {len(target_draws)}\n")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    rows_out = []
    best_matches = []  # luu cac lan trung >=3 so de bao cao rieng
    total_tickets = 0
    total_matches_sum = 0
    n_j1 = 0
    n_special_hit = 0

    for i, d in enumerate(target_draws):
        actual_numbers, actual_special = actual_results[d]
        actual_set = set(actual_numbers)

        for seed_start in all_seed_starts:
            unique_seeds_all, earliest_hit_all = model_pool[seed_start]
            m = earliest_hit_all < d
            if not m.any():
                continue
            unique_seeds = unique_seeds_all[m]

            groups = model_levels.get(str(seed_start))
            if groups is None:
                groups = list(preferred_levels)

            # Tinh hash 1 LAN DUY NHAT (tren SEED DA KHU TRUNG SAN) cho
            # model+ky nay, dung lai cho MOI muc.
            m1, m2, mask64 = np.uint64(M1), np.uint64(M2), np.uint64(MASK64)
            combined = (unique_seeds * m1 + np.uint64(d) * m2) & mask64
            mixed = pc.mix64_vec(combined) & mask64
            rank = (mixed % np.uint64(C)).astype(np.int64)
            mixed2 = pc.mix64_vec(mixed) & mask64
            special_idx = (mixed2 % np.uint64(12)).astype(np.int64)
            key = rank * 12 + special_idx
            counts = np.bincount(key, minlength=C * 12)

            seen_fallback = set()
            for tag_i, level in enumerate(groups, start=1):
                rng = random.Random(f"{d}:{seed_start}:{tag_i}:consensus")
                extracted_list = extract_ticket_at_level(counts, key, unique_seeds, level, rng, n_tickets=tickets_per_level)
                for top_rank, special, n_actual, matched_exact in extracted_list:
                    mask_bits = rank_to_mask[top_rank]
                    numbers = [k + 1 for k in range(35) if mask_bits & (1 << k)]

                    if not matched_exact:
                        tk = (tuple(numbers), special)
                        if tk in seen_fallback:
                            continue
                        seen_fallback.add(tk)

                    n_match = len(actual_set & set(numbers))
                    special_hit = (special == actual_special)
                    is_j1 = (n_match == 5 and special_hit)

                    total_tickets += 1
                    total_matches_sum += n_match
                    n_special_hit += int(special_hit)
                    n_j1 += int(is_j1)

                    if n_match >= 3:
                        best_matches.append({
                            "draw_id": d, "seed_start": seed_start, "target_level": level,
                            "ticket": "-".join(f"{x:02d}" for x in numbers), "special": special,
                            "n_match": n_match, "special_hit": special_hit, "is_j1": is_j1,
                            "actual": "-".join(f"{x:02d}" for x in actual_numbers) + f"+{actual_special}",
                        })

                    rows_out.append({
                        "draw_id": d, "seed_start": seed_start, "target_level": level,
                        "matched_exact": matched_exact, "n_seed_actual": n_actual,
                        "ticket": "-".join(f"{x:02d}" for x in numbers), "special": special,
                        "n_match": n_match, "special_hit": special_hit, "is_j1": is_j1,
                    })

        if (i + 1) % 50 == 0:
            avg_so_far = total_matches_sum / total_tickets if total_tickets else 0
            print(f"  ... da xong {i+1}/{len(target_draws)} ky | {total_tickets} ve | trung binh tam thoi: {avg_so_far:.4f}/5")

    print(f"\n=== KET QUA BACKTEST ({len(target_draws)} ky, {total_tickets} ve TONG CONG) ===")
    if total_tickets:
        avg_match = total_matches_sum / total_tickets
        print(f"Trung binh so TRUNG / ve: {avg_match:.4f} / 5")
        print(f"Moc ngau nhien tham khao: ~0.7143 / 5")
        print(f"Ty le trung dac biet: {n_special_hit}/{total_tickets} = {n_special_hit/total_tickets*100:.2f}% (ngau nhien ~8.33%)")
        print(f"So lan trung TUYET DOI (J1, 5/5 + dac biet): {n_j1}")
        print(f"So ve trung >=3/5 so: {len(best_matches)}")

    if best_matches:
        print(f"\n--- Chi tiet cac ve trung >=3/5 so (top 20 theo n_match giam dan) ---")
        for r in sorted(best_matches, key=lambda x: -x["n_match"])[:20]:
            j1_tag = " *** J1 - TRUNG TUYET DOI ***" if r["is_j1"] else ""
            print(f"  Ky {r['draw_id']:05d} | model {r['seed_start']} muc {r['target_level']}: "
                  f"{r['ticket']}+{r['special']} vs that {r['actual']} -> {r['n_match']}/5"
                  f"{' +DB' if r['special_hit'] else ''}{j1_tag}")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        if rows_out:
            writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)
    print(f"\nDa ghi {len(rows_out)} dong (moi ve/ky/model 1 dong) vao {out_path}")


if __name__ == "__main__":
    main()
