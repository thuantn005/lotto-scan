#!/usr/bin/env python3
"""
predict_next_draw_gap.py - CHIEN LUOC DUY NHAT con lai (thay the toan bo
base/app/ai/ai2/ai3/consensus cu). Chi ap dung cho 2 MODEL con duoc giu lai:
    l1-1/ (seed_start 900477750639)
    l1-2/ (seed_start 682305800400)
Moi model, du doan duoc tinh THEO 2 BUOC, CA 2 BUOC DEU CHON THEO KHOANG
CACH (khong con buoc nao chon ngau nhien deu nhu ban "app" truoc day):

  BUOC 1 - CHON KY (draw_id) theo khoang cach GIUA CAC KY TRUNG:
    - "Ky trung" = cac ky ma 1 seed da THANG HANG (l2_merged/promoted_
      seed{X}.json - seed da tung trung J1 >=2 lan, xem check_l1_per_draw.py).
    - Tinh avg_draw_gap = trung binh cac khoang cach (so ky) GIUA 2 LAN
      TRUNG LIEN TIEP cua MOI seed da thang hang trong L2 CUA CHINH model
      nay (lotto_common.get_gaps_from_l2_file). Model chua co L2 rieng thi
      du phong bang L2 GOP TOAN CUC (get_gaps_from_l2_dir).
    - Voi TUNG seed CON DANG CHO trong L1 (chua thang hang), tinh
      gap = next_draw_id - lan_xuat_hien_gan_nhat_trong_L1.
    - CHON nhom gap GAN avg_draw_gap NHAT (|gap - avg_draw_gap| nho nhat,
      hoa thi gap nho hon truoc - on dinh, khong random).

  BUOC 2 - Trong nhom gap da chon (co the nhieu seed cung gap), CHON SEED
    theo khoang cach GIUA CAC GIA TRI SEED (thay vi random deu nhu truoc):
    - Tinh avg_seed_gap = trung binh khoang cach GIUA 2 GIA TRI SEED lien
      tiep (sap tang dan) trong so cac seed da thang hang (L2) cua model
      nay (lotto_common.get_seed_values_from_l2_file). Du phong: gop tu
      TAT CA file L2 (moi model, sort chung) neu model chua co L2 rieng.
    - Voi TUNG seed trong nhom gap da chon, tinh seed_distance = khoang
      cach TUYET DOI toi gia tri seed DA THANG HANG gan no nhat.
    - CHON seed co |seed_distance - avg_seed_gap| NHO NHAT (hoa thi seed
      nho hon truoc). Khong co du lieu seed nao lam co so -> chon seed
      NHO NHAT trong nhom (van la quy tac CO DINH, khong random).

QUAN TRONG: day van CHI la 1 gia thuyet thong ke tren du lieu qua khu, ap
dung tren pool L1 - KHONG co bao dam gi ve tuong lai vi RNG thuc su khong
the du doan duoc.

ENV:
    CSV_PATH     - file CSV cac ky quay (mac dinh data/all.csv)
    L1_DIRS      - danh sach thu muc L1 (per-draw), phan cach boi dau phay
                   (mac dinh "l1-1,l1-2")
    L2_DIR       - thu muc chua file L2 (mac dinh l2_merged)
    OUT_PATH     - file .txt ket qua (mac dinh predict/next_draw_predict.txt)
    HISTORY_DIR  - thu muc luu lich su du doan (mac dinh predict/history)
"""
import bisect
import glob
import json
import os
from pathlib import Path

from lotto_common import (
    build_binom,
    build_rank_to_mask,
    predict_ticket,
    get_next_draw_id,
    get_gaps_from_l2_file,
    get_gaps_from_l2_dir,
    get_seed_values_from_l2_file,
    load_l1_dir,
    save_prediction_history,
)

STRATEGY = "gap"


def all_seed_values_global(l2_dir):
    """Du phong: gop gia tri seed tu MOI file l2_merged/*.json (dung khi
    model hien tai chua co L2 rieng)."""
    values = []
    for fp in sorted(glob.glob(os.path.join(str(l2_dir), "promoted_seed*.json"))):
        values.extend(get_seed_values_from_l2_file(fp))
    return sorted(values)


def nearest_distance(seed, sorted_values):
    """Khoang cach tuyet doi tu seed toi gia tri GAN NHAT trong sorted_values
    (danh sach da sap xep tang dan). Tra ve None neu danh sach rong."""
    if not sorted_values:
        return None
    i = bisect.bisect_left(sorted_values, seed)
    candidates = []
    if i < len(sorted_values):
        candidates.append(abs(sorted_values[i] - seed))
    if i > 0:
        candidates.append(abs(seed - sorted_values[i - 1]))
    return min(candidates) if candidates else None


def predict_for_model(l1_dir, l2_dir, next_draw_id, rank_to_mask):
    seed_start, seed_end, draws = load_l1_dir(l1_dir)
    if not draws:
        return None

    seed_last_hit = {}
    for d in draws:
        did = d["draw_id"]
        for s in d.get("seeds", []):
            prev = seed_last_hit.get(s)
            if prev is None or did > prev:
                seed_last_hit[s] = did
    if not seed_last_hit:
        return None

    l2_file = Path(l2_dir) / f"promoted_seed{seed_start}.json"

    # --- BUOC 1: chon KY (gap giua cac ky trung) ---
    own_draw_gaps = get_gaps_from_l2_file(l2_file)
    draw_gaps = own_draw_gaps if own_draw_gaps else get_gaps_from_l2_dir(l2_dir)
    avg_draw_gap = (sum(draw_gaps) / len(draw_gaps)) if draw_gaps else None
    draw_gap_source = "own" if own_draw_gaps else ("global_fallback" if draw_gaps else "none")

    l1_by_gap = {}
    for seed, last_hit in seed_last_hit.items():
        gap = next_draw_id - last_hit
        if gap <= 0:
            continue
        l1_by_gap.setdefault(gap, []).append((seed, last_hit))
    if not l1_by_gap:
        return None

    if avg_draw_gap is not None:
        chosen_gap = min(l1_by_gap.keys(), key=lambda g: (abs(g - avg_draw_gap), g))
    else:
        chosen_gap = min(l1_by_gap.keys())
    candidates = l1_by_gap[chosen_gap]

    # --- BUOC 2: chon SEED trong nhom (khoang cach giua cac gia tri seed) ---
    own_seed_values = get_seed_values_from_l2_file(l2_file)
    seed_values = own_seed_values if own_seed_values else all_seed_values_global(l2_dir)
    seed_gap_source = "own" if own_seed_values else ("global_fallback" if seed_values else "none")
    seed_gaps = [b - a for a, b in zip(seed_values, seed_values[1:]) if b > a]
    avg_seed_gap = (sum(seed_gaps) / len(seed_gaps)) if seed_gaps else None

    if seed_values:
        def sort_key(item):
            seed, _ = item
            dist = nearest_distance(seed, seed_values)
            if avg_seed_gap is not None and dist is not None:
                return (abs(dist - avg_seed_gap), seed)
            return (dist if dist is not None else 0, seed)
        candidates_sorted = sorted(candidates, key=sort_key)
    else:
        candidates_sorted = sorted(candidates, key=lambda item: item[0])

    seed, last_hit = candidates_sorted[0]
    numbers, special = predict_ticket(seed, next_draw_id, rank_to_mask)

    return {
        "seed_start": seed_start,
        "seed": seed,
        "numbers": numbers,
        "special": special,
        "file": l1_dir,
        "total_seeds_in_model": len(seed_last_hit),
        "last_hit_draw_id": last_hit,
        "gap_since_hit": chosen_gap,
        "avg_draw_gap": (round(avg_draw_gap, 2) if avg_draw_gap is not None else None),
        "draw_gap_source": draw_gap_source,
        "n_candidates_same_gap": len(candidates),
        "avg_seed_gap": (round(avg_seed_gap, 2) if avg_seed_gap is not None else None),
        "seed_gap_source": seed_gap_source,
    }


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_dirs = [s.strip() for s in os.environ.get("L1_DIRS", "l1-1,l1-2").split(",") if s.strip()]
    l2_dir = os.environ.get("L2_DIR", "l2_merged")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)
    next_draw_id = get_next_draw_id(csv_path)

    predictions = []
    for l1_dir in l1_dirs:
        info = predict_for_model(l1_dir, l2_dir, next_draw_id, rank_to_mask)
        if info is not None:
            predictions.append(info)
        else:
            print(f"[gap] Model {l1_dir}: khong co seed nao trong L1, bo qua.")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - CHIEN LUOC GAP (khoang cach).\n")
        f.write("Buoc 1: chon KY theo khoang cach GIUA CAC KY TRUNG (so voi trung binh\n")
        f.write("cua model). Buoc 2: trong ky do, chon SEED theo khoang cach GIUA CAC\n")
        f.write("GIA TRI SEED da thang hang (so voi trung binh) - khong con buoc nao\n")
        f.write("chon ngau nhien. Cong thuc hash giong TicketFormula.dart/scan_v2.cpp.\n\n")

        for info in predictions:
            nums_str = "-".join(f"{n:02d}" for n in info["numbers"])
            f.write(f"--- Model (L1: {info['file']}, seed_start={info['seed_start']}) ---\n")
            f.write(f"  so seed con trong L1: {info['total_seeds_in_model']}\n")
            f.write(f"  avg_draw_gap (nguon: {info['draw_gap_source']}): {info['avg_draw_gap']}\n")
            f.write(f"  ky duoc chon: cach {info['gap_since_hit']} ky "
                    f"({info['n_candidates_same_gap']} seed cung nhom gap nay)\n")
            f.write(f"  avg_seed_gap (nguon: {info['seed_gap_source']}): {info['avg_seed_gap']}\n")
            f.write(f"  seed duoc chon: {info['seed']} "
                    f"(lan xuat hien gan nhat: ky {info['last_hit_draw_id']:05d})\n")
            f.write(f"  DU DOAN ky {next_draw_id:05d}: {nums_str} + DAC BIET {info['special']}\n\n")

        if not predictions:
            f.write("(Khong co model nao co seed, khong co du doan.)\n")

    hpath = save_prediction_history(history_dir, next_draw_id, STRATEGY, predictions)
    print(f"[gap] Da ghi {len(predictions)} du doan vao {out_path}")
    print(f"[gap] Da luu lich su du doan ({STRATEGY}) vao {hpath}")
    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_MODELS={len(predictions)}")


if __name__ == "__main__":
    main()
