#!/usr/bin/env python3
"""
predict_next_draw_consensus.py - CHIEN LUOC "consensus": voi KY SAP TOI
(lay tu data/all.csv, CHUA co ket qua that), voi MOI model, tu tinh
MUC DO DONG THUAN DAC TRUNG cua CHINH model do (xem
compute_model_target_level() - la MODE, tuc gia tri PHO BIEN NHAT,
trong phan bo "so seed L2 cung trung 1 ky" cua model, TINH TU >= 2 -
vi du model 682305800400 chi tung dat toi da 2 seed/ky (=> muc dac
trung = 2), model 1903987714639 co muc 4 seed la PHO BIEN NHAT trong
lich su (16/20 ky top, nhieu hon ca muc 5-6 seed le te - xem
=> muc dac trung = 4), roi tim trong L1 cac ve dat DUNG (hoac gan nhat,
neu khong co ve nao dat dung) muc do dong thuan DAC TRUNG do cho ky sap
toi - THAY VI lay mu quang ve co dong thuan CAO NHAT (co the la 1 gia
tri ngoai le/outlier khong dai dien cho model do).

Y TUONG NEN TANG: xem chi tiet o find_consensus_tickets.py/
backtest_consensus_batch.py (cung repo).

**CANH BAO QUAN TRONG - DOC TRUOC KHI TIN DUNG CHIEN LUOC NAY**:
backtest_consensus_batch.py da chay THAT tren 846 ky lich su gan day
nhat (dung cach lay TOP/argmax, khong ro ri tuong lai) va cho ket qua:
trung binh so trung cua ve "dong thuan cao nhat" CHI DAT 0.70/5 - THAP
HON CA moc ngau nhien thuan tuy (0.7143/5). Ban than doi cach chon (lay
muc dac trung thay vi top) trong ban nay CHUA duoc backtest rieng -
NEN tu chay lai backtest_consensus_batch.py (co the can sua de dung
cung logic chon theo muc dac trung) truoc khi tin tuong ket qua. Script
nay duoc cung cap de chay san xuat/thu nghiem/doi chieu song song voi
cac chien luoc khac (base/app/ai/ai2/ai3), KHONG phai vi da duoc chung
minh hieu qua.

ENV:
    CSV_PATH        - data/all.csv
    L1_GLOB         - "l1_merged/merged_seed*.json" (de trong "" de bo qua L1)
    L2_GLOB         - "l2_merged/promoted_seed*.json" (BAT BUOC co du lieu L2
                      it nhat 1 model de tinh duoc muc dac trung; model nao
                      thieu L2 se dung DEFAULT_LEVEL lam du phong)
    DEFAULT_LEVEL   - muc dong thuan dung cho model KHONG co trong MODEL_LEVELS
                      VA khong tinh duoc mode tu L2 rieng (mac dinh 2)
    MODEL_LEVELS    - JSON mapping "seed_start" -> DANH SACH cac "nhom muc
                      dong thuan" cho model do, MOI NHOM se cho ra 1 VE
                      RIENG (1 model co the co NHIEU ve). Moi nhom la:
                        - 1 so nguyen: tim ve dat DUNG muc do (hoac gan
                          nhat neu khong co ve nao dung).
                        - 1 danh sach [a,b,c,...]: tim ve co muc do CAO
                          NHAT trong danh sach ma THUC SU TON TAI cho ky
                          nay (thu tu uu tien: cao -> thap trong danh
                          sach); neu KHONG co muc nao trong danh sach ton
                          tai, fallback ve muc GAN GIA TRI LON NHAT trong
                          danh sach nhat.
                      Mac dinh: {"682305800400": [2],
                      "1903987714639": [2, [3,4,5,6,7]]} - model
                      1903987714639 se ra 2 ve: 1 ve muc 2 (pho bien nhat
                      trong lich su L2 cua no) va 1 ve o muc cao nhat co
                      that trong khoang 3-7. Model KHONG co trong danh
                      sach nay se tu tinh mode tu L2 rieng va CHI ra 1 ve.
    OUT_PATH        - file ghi du doan (mac dinh predict/next_draw_predict_consensus.txt)
    HISTORY_DIR     - thu muc luu lich su (mac dinh predict/history) - CUNG
                      dinh dang voi cac chien luoc khac de
                      check_prediction_result.py/dashboard tu nhan dien.
"""

DEFAULT_MODEL_LEVELS = {
    "682305800400": [2],
    "1903987714639": [2, [3, 4, 5, 6, 7]],
}

import glob
import json
import os
import random
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

from lotto_common import (
    build_binom,
    build_rank_to_mask,
    get_next_draw_id,
    save_prediction_history,
    M1,
    M2,
    M3,
    M4,
    MASK64,
    C,
)

warnings.filterwarnings("ignore", category=RuntimeWarning)

STRATEGY = "consensus"


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
    return (
        data.get("seed_start"),
        np.array(seeds, dtype=np.uint64),
        np.array(hits, dtype=np.int32),
    )


def compute_model_target_level(l2_hits, default_level):
    """MUC DAC TRUNG cua 1 model = gia tri PHO BIEN NHAT (mode) trong
    phan bo 'so seed L2 CUNG tung trung 1 ky' cua CHINH model do, tinh
    tu >= 2 (bo qua cac ky chi co 1 seed - khong tinh la 'dong thuan').
    Vi du: model chi tung dat toi da 2 seed/ky (khong co ky nao khac
    dat >=2) => muc dac trung = 2. Model co nhieu ky dat 4 seed hon so
    voi so ky dat 5 hay 6 seed => muc dac trung = 4 (du 6 la max tung
    thay, no chi xay ra 1 lan - khong dai dien bang muc 4 pho bien
    hon).

    Tra ve default_level neu model khong co ky nao dat >= 2 seed (chua
    du du lieu L2 de tinh)."""
    if l2_hits.size == 0:
        return default_level

    draw_count = Counter(l2_hits.tolist())
    counts_ge2 = [c for c in draw_count.values() if c >= 2]
    if not counts_ge2:
        return default_level

    level_freq = Counter(counts_ge2)
    max_freq = max(level_freq.values())
    # Neu hoa tan suat, uu tien muc CAO HON (dang tin cay hon ve mat
    # thong ke) trong so cac muc co cung tan suat cao nhat.
    candidates = [lvl for lvl, freq in level_freq.items() if freq == max_freq]
    return max(candidates)


def find_ticket_at_level(seed_arr, next_draw_id, rank_to_mask, target_level, seed_start):
    """Tim 1 ve dat DUNG target_level seed doc lap dong thuan cho
    next_draw_id. Neu khong co ve nao dat DUNG muc do, lay ve co muc
    dong thuan GAN target_level NHAT (uu tien cao hon neu hoa khoang
    cach). Khi co NHIEU ve cung dat muc do da chon (rat pho bien o muc
    thap nhu 2), CHON NGAU NHIEN 1 trong so do (hat giong co dinh theo
    next_draw_id+seed_start de tai lap duoc giua cac lan chay) - THAY
    VI luon lay ve nho nhat (se gay trung lap "01-02-03-04-05" o nhieu
    model, vi do la vé/rank dau tien theo thu tu, khong mang y nghia
    gi hon cac ve khac cung muc). Tra ve (numbers, special,
    so_seed_thuc_te, seed_dai_dien, dung_dung_muc_hay_khong)."""
    if seed_arr.size == 0:
        return None

    m1, m2, mask64 = np.uint64(M1), np.uint64(M2), np.uint64(MASK64)
    combined = (seed_arr * m1 + np.uint64(next_draw_id) * m2) & mask64
    mixed = mix64_vec(combined) & mask64
    rank = (mixed % np.uint64(C)).astype(np.int64)
    mixed2 = mix64_vec(mixed) & mask64
    special_idx = (mixed2 % np.uint64(12)).astype(np.int64)
    key = rank * 12 + special_idx

    total_possible = C * 12
    counts = np.bincount(key, minlength=total_possible)
    nonzero_keys = np.where(counts > 0)[0]
    if nonzero_keys.size == 0:
        return None

    nonzero_counts = counts[nonzero_keys]
    exact = nonzero_keys[nonzero_counts == target_level]
    rng = random.Random(f"{next_draw_id}:{seed_start}:consensus")
    if exact.size > 0:
        chosen_key = int(rng.choice(sorted(exact.tolist())))
        matched_exact = True
    else:
        diffs = np.abs(nonzero_counts.astype(np.int64) - target_level)
        min_diff = diffs.min()
        best = nonzero_keys[diffs == min_diff]
        best_counts = counts[best]
        top_available = int(best_counts.max())
        tied = sorted(best[best_counts == top_available].tolist())
        chosen_key = int(rng.choice(tied))
        matched_exact = False

    top_rank, top_sp_idx = divmod(chosen_key, 12)
    top_special = top_sp_idx + 1
    n_actual = int(counts[chosen_key])

    group_mask = (key == chosen_key)
    distinct_seeds = np.unique(seed_arr[group_mask])
    seed_dai_dien = int(distinct_seeds[0])

    mask_bits = rank_to_mask[top_rank]
    numbers = [i + 1 for i in range(35) if mask_bits & (1 << i)]

    return numbers, top_special, n_actual, seed_dai_dien, matched_exact


def find_ticket_for_group(seed_arr, next_draw_id, rank_to_mask, level_group, seed_start, tag):
    """level_group la 1 so nguyen (tim dung muc do) HOAC 1 danh sach so
    nguyen (1 khoang - tim muc CAO NHAT trong khoang ma THUC SU CO ve,
    uu tien cao truoc; neu khong muc nao trong khoang co ve thi fallback
    ve gan gia tri LON NHAT trong khoang nhat, dung logic 'gan nhat' cua
    find_ticket_at_level). Tra ve (result_tuple_hoac_None, target_level_hien_thi)."""
    if isinstance(level_group, int):
        result = find_ticket_at_level(seed_arr, next_draw_id, rank_to_mask, level_group, f"{seed_start}:{tag}")
        return result, level_group

    # level_group la 1 danh sach (khoang) - thu tu CAO xuong THAP.
    for lvl in sorted(level_group, reverse=True):
        result = find_ticket_at_level(seed_arr, next_draw_id, rank_to_mask, lvl, f"{seed_start}:{tag}")
        if result is not None and result[4]:  # matched_exact=True nghia la muc nay THUC SU CO ve
            return result, lvl
    # Khong muc nao trong khoang co ve THUC SU - fallback ve gan gia tri
    # LON NHAT trong khoang (giu tinh than "uu tien cao").
    fallback_target = max(level_group)
    result = find_ticket_at_level(seed_arr, next_draw_id, rank_to_mask, fallback_target, f"{seed_start}:{tag}")
    return result, fallback_target


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    l2_glob = os.environ.get("L2_GLOB", "l2_merged/promoted_seed*.json")
    default_level = int(os.environ.get("DEFAULT_LEVEL", "2"))
    model_levels_raw = os.environ.get("MODEL_LEVELS")
    if model_levels_raw:
        model_levels = {str(k): v for k, v in json.loads(model_levels_raw).items()}
    else:
        model_levels = dict(DEFAULT_MODEL_LEVELS)
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_consensus.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")

    next_draw_id = get_next_draw_id(csv_path)
    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    l1_files = {}
    for fp in sorted(glob.glob(l1_glob)) if l1_glob else []:
        seed_start, seeds, hits = load_l1_file(fp)
        l1_files[seed_start] = (fp, seeds, hits)

    l2_files = {}
    for fp in sorted(glob.glob(l2_glob)) if l2_glob else []:
        seed_start, seeds, hits = load_l2_file(fp)
        l2_files[seed_start] = (fp, seeds, hits)

    all_seed_starts = sorted(set(l1_files) | set(l2_files))
    print(f"Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"So model tim thay: {len(all_seed_starts)}\n")

    predictions = []
    lines_out = [
        f"KY MUC TIEU: {next_draw_id:05d} (chien luoc 'consensus' - xem CANH BAO trong docstring script)",
        "",
    ]

    for seed_start in all_seed_starts:
        pool_parts = []
        fps = []
        l2_hits = np.array([], dtype=np.int32)

        if seed_start in l1_files:
            fp, seeds, hits = l1_files[seed_start]
            pool_parts.append(seeds)
            fps.append(fp)
        if seed_start in l2_files:
            fp, seeds, hits = l2_files[seed_start]
            pool_parts.append(seeds)
            fps.append(fp)
            l2_hits = hits

        if not pool_parts:
            continue
        combined_seeds = np.concatenate(pool_parts) if len(pool_parts) > 1 else pool_parts[0]

        groups = model_levels.get(str(seed_start))
        if groups is None:
            groups = [compute_model_target_level(l2_hits, default_level)]
            level_source = "tu tinh (mode)"
        else:
            level_source = "chi dinh thu cong"

        for tag_i, level_group in enumerate(groups, start=1):
            result, target_level = find_ticket_for_group(
                combined_seeds, next_draw_id, rank_to_mask, level_group, seed_start, tag_i)
            if result is None:
                continue
            numbers, special, n_actual, seed_dai_dien, matched_exact = result

            group_label = f"muc {target_level}" if isinstance(level_group, int) else f"cao nhat trong khoang {level_group}, chon duoc {target_level}"
            nums_str = "-".join(f"{n:02d}" for n in numbers)
            match_note = "dung muc" if matched_exact else f"KHONG co ve nao dung {target_level}, lay gan nhat"
            ve_label = f"ve {tag_i}/{len(groups)}" if len(groups) > 1 else "ve"
            line = (f"Model {seed_start} ({ve_label}): {nums_str} + DB {special:02d} "
                    f"({group_label} seed [{level_source}], thuc te ve nay dat {n_actual} seed - {match_note})")
            print(line)
            lines_out.append(line)

            predictions.append({
                "seed_start": seed_start,
                "seed": seed_dai_dien,
                "numbers": numbers,
                "special": special,
                "file": ";".join(fps),
            })

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    Path(out_path).write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(f"\nDa ghi {len(predictions)} du doan vao {out_path}")

    if predictions:
        hist_path = save_prediction_history(history_dir, next_draw_id, STRATEGY, predictions)
        print(f"Da luu lich su du doan (consensus) vao {hist_path} (de doi chieu sau nay)")

    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_MODELS={len(predictions)}")


if __name__ == "__main__":
    main()
