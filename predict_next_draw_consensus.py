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
    "1903987714639": [2, 3, 4],
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


def find_ticket_at_level(seed_arr, hit_arr, next_draw_id, rank_to_mask, target_level, seed_start, n_tickets=2):
    """Tim toi da n_tickets VE PHAN BIET dat DUNG target_level seed doc
    lap dong thuan cho next_draw_id (mac dinh 2 ve/muc - neu muc do co
    >=2 ve khac nhau cung dat dung, lay 2 ve KHAC NHAU thay vi chi 1;
    neu muc do chi co 1 ve du dieu kien, chi tra ve 1). Neu KHONG co ve
    nao dat DUNG muc do, lay (toi da n_tickets) ve co muc dong thuan
    GAN target_level NHAT (uu tien cao hon neu hoa khoang cach). Chon
    ngau nhien co hat giong co dinh (tai lap duoc giua cac lan chay) -
    THAY VI luon lay ve nho nhat (se gay trung lap "01-02-03-04-05" o
    nhieu model, khong mang y nghia gi hon cac ve khac cung muc).

    QUAN TRONG: dem theo SEED DOC LAP (da khu trung), KHONG dem theo
    tung LUOT trung - vi 1 seed L2 co the co 2+ lan trung (2+ dong
    trong hit_arr voi CUNG 1 seed), nhung no VAN CHI LA 1 seed, khong
    phai 2 "phieu" khac nhau. Neu dem tho theo so dong (nhu ban truoc),
    seed L2 co nhieu lan trung se bi dem THUA, lam sai muc dong thuan
    that (vi du 3 seed doc lap nhung 1 trong so co 2 lan trung se bi
    dem thanh "4 seed" thay vi dung 3).

    Tra ve list cac tuple (numbers, special, so_seed_thuc_te,
    seed_dai_dien, dung_dung_muc_hay_khong, chi_tiet_seed) - toi da
    n_tickets phan tu, sap theo thu tu chon (khong sap theo bat ky tieu
    chi "chat luong" nao khac ngoai ngau nhien). List rong neu khong co
    du lieu."""
    if seed_arr.size == 0:
        return []

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
        return []

    nonzero_counts = counts[nonzero_keys]
    exact = nonzero_keys[nonzero_counts == target_level]
    rng = random.Random(f"{next_draw_id}:{seed_start}:consensus")
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
        n_actual = int(counts[chosen_key])  # so seed DOC LAP that, khong con dem thua

        distinct_seeds = unique_seeds[key == chosen_key]
        seed_dai_dien = int(distinct_seeds[0])

        chi_tiet_seed = []
        for s in distinct_seeds.tolist():
            # Lay lai TAT CA ky trung that cua seed nay tu mang GOC (chua
            # khu trung) - 1 seed co the co nhieu ky trung, muon liet ke
            # DAY DU.
            ky_trung = sorted(set(int(h) for h in hit_arr[seed_arr == s].tolist()))
            chi_tiet_seed.append((int(s), ky_trung))

        mask_bits = rank_to_mask[top_rank]
        numbers = [i + 1 for i in range(35) if mask_bits & (1 << i)]

        results.append((numbers, top_special, n_actual, seed_dai_dien, matched_exact, chi_tiet_seed))

    return results


def find_ticket_for_group(seed_arr, hit_arr, next_draw_id, rank_to_mask, level, seed_start, tag, n_tickets=2):
    """level LUON la 1 so nguyen - MOI muc trong danh sach cua 1 model se
    sinh ra toi da n_tickets VE RIENG (mac dinh 2). Tra ve
    (list_ket_qua, target_level) - list co the rong neu khong co du
    lieu."""
    results = find_ticket_at_level(seed_arr, hit_arr, next_draw_id, rank_to_mask, level,
                                    f"{seed_start}:{tag}", n_tickets=n_tickets)
    return results, level


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    l2_glob = os.environ.get("L2_GLOB", "l2_merged/promoted_seed*.json")
    default_level = int(os.environ.get("DEFAULT_LEVEL", "2"))
    preferred_levels_raw = os.environ.get("PREFERRED_LEVELS", "4")
    preferred_levels = [int(x) for x in preferred_levels_raw.split(",") if x.strip()]
    tickets_per_level = int(os.environ.get("TICKETS_PER_LEVEL", "2"))
    min_model_seeds = int(os.environ.get("MIN_MODEL_SEEDS", "100000"))
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

        if combined_seeds.size < min_model_seeds:
            print(f"Model {seed_start}: BO QUA (chi co {combined_seeds.size:,} ban ghi, duoi nguong MIN_MODEL_SEEDS={min_model_seeds:,} - du lieu qua it de dang tin cay)")
            lines_out.append(f"Model {seed_start}: BO QUA (du lieu qua it: {combined_seeds.size:,} < {min_model_seeds:,})")
            continue

        groups = model_levels.get(str(seed_start))
        if groups is None:
            groups = list(preferred_levels)  # moi muc trong danh sach = 1 ve rieng
            level_source = f"tu dong (moi muc trong {preferred_levels} ra 1 ve rieng)"
        else:
            level_source = "chi dinh thu cong"

        seen_fallback_tickets = set()  # (numbers_tuple, special) da tung fallback cho model nay
        for tag_i, level in enumerate(groups, start=1):
            results, target_level = find_ticket_for_group(
                combined_seeds, combined_hits, next_draw_id, rank_to_mask, level, seed_start, tag_i,
                n_tickets=tickets_per_level)
            if not results:
                continue

            for sub_i, result in enumerate(results, start=1):
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
                ve_label = f"muc {target_level} - ve {sub_i}/{len(results)}" if len(results) > 1 else f"muc {target_level}"
                line = (f"Model {seed_start} ({ve_label}): {nums_str} + DB {special:02d} "
                        f"([{level_source}], thuc te ve nay dat {n_actual} seed - {match_note})")
                print(line)
                lines_out.append(line)
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


def collect_candidates_for_ai(l1_fp, l2_fp, seed_start, next_draw_id, rank_to_mask, levels, tickets_per_level=3):
    """Doc L1(+L2) cho 1 model, dung LAI find_ticket_at_level() cho tung
    muc trong `levels` (vi du [5,6,7]) de lam UNG VIEN cho AI chon -
    THAY VI script tu dong chon ngau nhien nhu chien luoc "consensus".
    Loai trung cac ve giong het nhau (cung so + dac biet) neu nhieu muc
    cung tra ve 1 ve (thuong xay ra khi model khong dat duoc muc cao,
    fallback ve cung 1 ve cho nhieu muc).

    Tra ve dict {seed_start, total_seeds, candidates: [...]} - moi phan
    tu candidates la {requested_level, achieved_level, matched_exact,
    numbers, special, seeds: [(seed,[ky_trung,...]), ...]}. Tra ve None
    neu khong doc duoc du lieu nao."""
    seed_parts, hit_parts = [], []
    if l1_fp:
        _, seeds, hits = load_l1_file(l1_fp)
        seed_parts.append(seeds)
        hit_parts.append(hits)
    if l2_fp:
        _, seeds, hits = load_l2_file(l2_fp)
        seed_parts.append(seeds)
        hit_parts.append(hits)
    if not seed_parts:
        return None
    combined_seeds = np.concatenate(seed_parts) if len(seed_parts) > 1 else seed_parts[0]
    combined_hits = np.concatenate(hit_parts) if len(hit_parts) > 1 else hit_parts[0]

    raw_candidates = []
    for level in levels:
        results = find_ticket_at_level(combined_seeds, combined_hits, next_draw_id, rank_to_mask, level,
                                        f"{seed_start}:ai:{level}", n_tickets=tickets_per_level)
        for numbers, special, n_actual, seed_dai_dien, matched_exact, chi_tiet_seed in results:
            raw_candidates.append({
                "requested_level": level,
                "achieved_level": n_actual,
                "matched_exact": matched_exact,
                "numbers": numbers,
                "special": special,
                "seeds": chi_tiet_seed,
            })

    seen = set()
    candidates = []
    for c in raw_candidates:
        key = (tuple(c["numbers"]), c["special"])
        if key in seen:
            continue
        seen.add(key)
        candidates.append(c)

    return {
        "seed_start": seed_start,
        "total_seeds": int(np.unique(combined_seeds).size),
        "candidates": candidates,
        "file": ";".join(x for x in [l1_fp, l2_fp] if x),
    }


def build_ai_prompt_levels(next_draw_id, recent_draws, models):
    """Dung ket qua cua collect_candidates_for_ai() (1 phan tu/model)
    de dung 1 prompt van ban, yeu cau AI tra ve JSON
    {"picks": [{"model_index", "seed", "reasoning"}, ...]} - moi model
    DUNG 1 pick, seed PHAI la 1 trong cac "seed dai dien" cua 1 ung
    vien CUA CHINH model do (khong duoc bia seed moi)."""
    lines = [
        "Ban dang tham gia 1 bai tap THONG KE/NGHIEN CUU ve du lieu xo so "
        "da cong bo cong khai - day la du lieu NGAU NHIEN THAT SU, khong "
        "co cach nao du doan chinh xac, KHONG phai loi khuyen tai chinh "
        "hay danh bac.",
        f"Ky ke tiep can du doan: {next_draw_id:05d} (5 so tu 01-35 + 1 so dac biet tu 01-12).",
        "",
        f"Ket qua {len(recent_draws)} ky GAN NHAT (cu truoc -> moi sau):",
    ]
    for draw_id, numbers, special in recent_draws:
        nums_str = "-".join(f"{n:02d}" for n in numbers)
        lines.append(f"  Ky {draw_id:05d}: {nums_str} + DB {special:02d}")

    lines += [
        "",
        f"Co {len(models)} 'model' doc lap (danh so tu 0), moi model la 1 tap "
        "seed rieng sinh boi cong thuc hash mix64 co dinh. Voi moi model, "
        "cac ve ung vien la nhung ve ma NHIEU seed DOC LAP (khac gia tri "
        "seed, tung trung THAT o cac ky KHAC NHAU trong qua khu) CUNG cho "
        "ra GIONG NHAU khi ap cong thuc cho ky sap toi - 'achieved_level' "
        "cang cao nghia la cang NHIEU seed doc lap cung dong y (hiem hon ve "
        "mat thong ke thuan tuy, KHONG phai bang chung du doan duoc). Danh "
        "sach duoi day da loai trung, sap theo achieved_level giam dan:",
        "",
    ]
    for i, m in enumerate(models):
        lines.append(f"--- Model {i} (seed_start={m['seed_start']}, {m['total_seeds']} seed kha dung) ---")
        for c in sorted(m["candidates"], key=lambda x: -x["achieved_level"]):
            nums_str = "-".join(f"{n:02d}" for n in c["numbers"])
            seeds_str = "; ".join(
                f"seed={s} (tung trung: {', '.join(f'ky {k:05d}' for k in ks)})"
                for s, ks in c["seeds"]
            )
            lines.append(
                f"  Ve {nums_str} + DB {c['special']:02d} | yeu cau muc {c['requested_level']}, "
                f"THUC TE dat {c['achieved_level']} seed doc lap{'​ (dung muc)' if c['matched_exact'] else ' (KHONG dung muc yeu cau, day la muc gan nhat thuc co)'} "
                f"| {seeds_str}"
            )
        lines.append("")

    lines += [
        "YEU CAU: voi MOI model o tren, chon DUNG 1 ve trong danh sach ung "
        "vien CUA CHINH model do (KHONG duoc bia ve khac, khong duoc bo qua "
        "model nao) ma ban thay 'hop ly nhat' dua tren achieved_level va "
        "bat ky quy luat nao ban quan sat duoc tu lich su gan day (chi mang "
        "tinh tham khao thong ke, khong co co so khoa hoc de du doan chinh "
        "xac 1 RNG that). Tra ve seed la 1 trong cac seed lien quan den ve "
        "ban chon (bat ky seed nao trong danh sach 'seeds' cua ve do).",
        "CHI tra loi DUNG 1 JSON object, KHONG markdown, KHONG chu thich gi "
        "them ngoai JSON, dung dinh dang:",
        '{"picks": [{"model_index": 0, "seed": 123456, "reasoning": "..."}, ...]}',
        "reasoning viet ngan gon (1-2 cau), bang tieng Viet.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
