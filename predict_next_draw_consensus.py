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
    DEFAULT_LEVEL   - muc dong thuan dung khi model KHONG co du lieu L2
                      rieng VA khong co trong MODEL_LEVELS (mac dinh 2)
    PREFERRED_LEVELS - khoang muc dong thuan MAC DINH cho MOI model KHONG
                      co trong MODEL_LEVELS (danh sach cach nhau dau phay,
                      mac dinh "4,5,6,7,8" - gop 5 muc lai, tim muc CAO
                      NHAT trong do THUC SU CO ve cho ky dang du doan; neu
                      khong muc nao trong khoang co ve, fallback ve muc
                      GAN 8 NHAT thuc te co)
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
    "1903987714639": [2, 3, 4, 5, 6, 7],
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


def compute_model_target_level(l2_hits, default_level, preferred_level=4):
    """MUC DAC TRUNG cua 1 model = UU TIEN preferred_level (mac dinh 4)
    NEU model do TUNG dat duoc muc nay it nhat 1 lan trong lich su L2
    cua no (>= 2 seed cung trung 1 ky). Muc 2 tuy la PHO BIEN NHAT
    (mode) o hau het cac model, nhung qua pho bien (hang nghin ve/ky)
    nen KEM CHON LOC - uu tien muc 4 (hiem hon, dang tin cay hon ve mat
    thong ke) lam mac dinh THAY VI mode.

    Neu model CHUA BAO GIO dat duoc preferred_level (vi du model qua
    nho, L2 con it), fallback ve muc THUC TE GAN preferred_level NHAT
    (uu tien muc CAO HON neu khoang cach bang nhau - vi du model chi
    dat toi da 2 va 3, se chon 3 chu khong chon 2).

    Tra ve default_level neu model khong co ky nao dat >= 2 seed (chua
    du du lieu L2 de tinh gi ca)."""
    if l2_hits.size == 0:
        return default_level

    draw_count = Counter(l2_hits.tolist())
    counts_ge2 = [c for c in draw_count.values() if c >= 2]
    if not counts_ge2:
        return default_level

    level_freq = Counter(counts_ge2)
    if preferred_level in level_freq:
        return preferred_level

    # Model chua tung dat duoc preferred_level - lay muc THUC TE co ton
    # tai GAN preferred_level nhat, uu tien cao hon khi hoa khoang cach.
    available_levels = sorted(level_freq.keys())
    return min(available_levels, key=lambda lvl: (abs(lvl - preferred_level), -lvl))


def find_ticket_at_level(seed_arr, hit_arr, next_draw_id, rank_to_mask, target_level, seed_start):
    """Tim 1 ve dat DUNG target_level seed doc lap dong thuan cho
    next_draw_id. Neu khong co ve nao dat DUNG muc do, lay ve co muc
    dong thuan GAN target_level NHAT (uu tien cao hon neu hoa khoang
    cach). Khi co NHIEU ve cung dat muc do da chon (rat pho bien o muc
    thap nhu 2), CHON NGAU NHIEN 1 trong so do (hat giong co dinh theo
    next_draw_id+seed_start de tai lap duoc giua cac lan chay) - THAY
    VI luon lay ve nho nhat (se gay trung lap "01-02-03-04-05" o nhieu
    model, vi do la vé/rank dau tien theo thu tu, khong mang y nghia
    gi hon cac ve khac cung muc).

    QUAN TRONG: dem theo SEED DOC LAP (da khu trung), KHONG dem theo
    tung LUOT trung - vi 1 seed L2 co the co 2+ lan trung (2+ dong
    trong hit_arr voi CUNG 1 seed), nhung no VAN CHI LA 1 seed, khong
    phai 2 "phieu" khac nhau. Neu dem tho theo so dong (nhu ban truoc),
    seed L2 co nhieu lan trung se bi dem THUA, lam sai muc dong thuan
    that (vi du 3 seed doc lap nhung 1 trong so co 2 lan trung se bi
    dem thanh "4 seed" thay vi dung 3).

    Tra ve (numbers, special, so_seed_thuc_te, seed_dai_dien,
    dung_dung_muc_hay_khong, chi_tiet_seed) - chi_tiet_seed la list
    [(seed, [ky_trung_truoc,...]), ...] cho TAT CA seed trong nhom da
    chon, sap theo seed tang dan."""
    if seed_arr.size == 0:
        return None

    unique_seeds = np.unique(seed_arr)  # KHU TRUNG truoc khi tinh hash/dem

    m1, m2, mask64 = np.uint64(M1), np.uint64(M2), np.uint64(MASK64)
    combined = (unique_seeds * m1 + np.uint64(next_draw_id) * m2) & mask64
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
    n_actual = int(counts[chosen_key])  # gio DA la so seed DOC LAP that, khong con dem thua

    distinct_seeds = unique_seeds[key == chosen_key]
    seed_dai_dien = int(distinct_seeds[0])

    chi_tiet_seed = []
    for s in distinct_seeds.tolist():
        # Lay lai TAT CA ky trung that cua seed nay tu mang GOC (chua khu
        # trung) - 1 seed co the co nhieu ky trung, muon liet ke DAY DU.
        ky_trung = sorted(set(int(h) for h in hit_arr[seed_arr == s].tolist()))
        chi_tiet_seed.append((int(s), ky_trung))

    mask_bits = rank_to_mask[top_rank]
    numbers = [i + 1 for i in range(35) if mask_bits & (1 << i)]

    return numbers, top_special, n_actual, seed_dai_dien, matched_exact, chi_tiet_seed


def find_ticket_for_group(seed_arr, hit_arr, next_draw_id, rank_to_mask, level, seed_start, tag):
    """level LUON la 1 so nguyen - MOI muc trong danh sach cua 1 model se
    sinh ra 1 VE RIENG (KHONG con gop nhieu muc lai chi lay 1 ve 'tot
    nhat trong khoang' nhu ban truoc). Tra ve (result_tuple_hoac_None,
    target_level)."""
    result = find_ticket_at_level(seed_arr, hit_arr, next_draw_id, rank_to_mask, level, f"{seed_start}:{tag}")
    return result, level


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    l2_glob = os.environ.get("L2_GLOB", "l2_merged/promoted_seed*.json")
    default_level = int(os.environ.get("DEFAULT_LEVEL", "2"))
    preferred_levels_raw = os.environ.get("PREFERRED_LEVELS", "4,5,6,7")
    preferred_levels = [int(x) for x in preferred_levels_raw.split(",") if x.strip()]
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
        seed_parts, hit_parts = [], []
        fps = []
        l2_hits = np.array([], dtype=np.int32)

        if seed_start in l1_files:
            fp, seeds, hits = l1_files[seed_start]
            seed_parts.append(seeds)
            hit_parts.append(hits)
            fps.append(fp)
        if seed_start in l2_files:
            fp, seeds, hits = l2_files[seed_start]
            seed_parts.append(seeds)
            hit_parts.append(hits)
            fps.append(fp)
            l2_hits = hits

        if not seed_parts:
            continue
        combined_seeds = np.concatenate(seed_parts) if len(seed_parts) > 1 else seed_parts[0]
        combined_hits = np.concatenate(hit_parts) if len(hit_parts) > 1 else hit_parts[0]

        groups = model_levels.get(str(seed_start))
        if groups is None:
            groups = list(preferred_levels)  # moi muc trong danh sach = 1 ve rieng
            level_source = f"tu dong (moi muc trong {preferred_levels} ra 1 ve rieng)"
        else:
            level_source = "chi dinh thu cong"

        seen_fallback_tickets = set()  # (numbers_tuple, special) da tung fallback cho model nay
        for tag_i, level in enumerate(groups, start=1):
            result, target_level = find_ticket_for_group(
                combined_seeds, combined_hits, next_draw_id, rank_to_mask, level, seed_start, tag_i)
            if result is None:
                continue
            numbers, special, n_actual, seed_dai_dien, matched_exact, chi_tiet_seed = result

            if not matched_exact:
                # Model nay KHONG dat duoc muc yeu cau -> dang fallback ve
                # muc THUC TE cao nhat co. Neu da in 1 ve fallback GIONG HET
                # (cung so + dac biet) cho muc khac cua CHINH model nay roi,
                # BO QUA lan nay - tranh hien thi 2+ "ve" trung lap y het
                # nhau (chi khac nhan "muc X" tren nhan) gay hieu lam la co
                # nhieu tin hieu doc lap trong khi thuc chat chi la 1.
                ticket_key = (tuple(numbers), special)
                if ticket_key in seen_fallback_tickets:
                    continue
                seen_fallback_tickets.add(ticket_key)

            nums_str = "-".join(f"{n:02d}" for n in numbers)
            match_note = "dung muc" if matched_exact else f"KHONG co ve nao dung {target_level}, lay gan nhat (thuc te cao nhat model nay dat duoc = {n_actual})"
            ve_label = f"ve {tag_i}/{len(groups)}" if len(groups) > 1 else "ve"
            line = (f"Model {seed_start} ({ve_label}): {nums_str} + DB {special:02d} "
                    f"(muc {target_level} seed [{level_source}], thuc te ve nay dat {n_actual} seed - {match_note})")
            print(line)
            lines_out.append(line)
            for s, ky_list in chi_tiet_seed:
                ky_str = ", ".join(f"ky {k:05d}" for k in ky_list)
                detail = f"    seed={s} - da tung trung THAT o: {ky_str}"
                print(detail)
                lines_out.append(detail)

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
