#!/usr/bin/env python3
"""
predict_l1_3_gap.py - MODEL DU DOAN DUY NHAT, CHI cho l1-3/ (seed_start 309440000001,
dai 309.440.000.001 -> 309.540.000.000), theo KHOANG CACH CUA SEED TRUNG J1 2 LAN.

"Seed trung J1 2 lan" = seed trong l2_merged/promoted_seed309440000001.json
(do check_l1_per_draw.py ghi tu l1-3/). Chi dung L2 CUA CHINH l1-3, KHONG fallback
sang l1-1/l1-2.

  BUOC 1 - chon KY: avg_draw_gap = trung binh khoang cach (so ky) giua 2 lan trung
    cua moi seed trung 2 lan. Voi moi seed trong L1 (l1-3/): gap = ky_ke_tiep -
    lan_trung_gan_nhat. Chon nhom gap GAN avg_draw_gap nhat (hoa: gap nho hon).
  BUOC 2 - chon SEED: avg_seed_gap = trung binh khoang cach giua 2 gia tri seed
    lien tiep (sap tang) cua cac seed trung 2 lan. Voi moi seed trong nhom, tinh
    khoang cach toi seed trung-2-lan GAN NHAT; chon seed co |khoang cach - avg_seed_gap|
    nho nhat (hoa: seed nho hon). Khong co random.

Ngoai vé chon, ghi them TOP_N (mac dinh 10) ung vien xep theo cung quy tac.
CANH BAO: day chi la quy tac co dinh tren du lieu qua khu; RNG khong du doan duoc.

LOAI VE TRUNG results/: ve cua cac seed trong results/final_j1_2plus_*.json (seed trung J1 >= 2 lan,
quet backtest mu) tinh cho ky ke tiep; ung vien nao TRUNG 1 trong cac ve do thi BI LOAI, lay ung vien
tiep theo theo cung quy tac. Ung vien trung ve nhau (2 seed cung ra 1 ve) chi giu 1.

ENV: RESULTS_GLOB (results/final_j1_2plus_*.json; dat rong de tat), CSV_PATH (data/all.csv), L1_DIR (l1-3), L2_FILE (l2_merged/promoted_seed309440000001.json),
     OUT_PATH (predict/next_draw_predict_l1_3.txt), HISTORY_DIR (predict/history), TOP_N (10)
"""
import bisect, glob, json, os
from pathlib import Path
from lotto_common import (build_binom, build_rank_to_mask, predict_ticket, get_next_draw_id,
    get_gaps_from_l2_file, get_seed_values_from_l2_file, load_l1_dir, save_prediction_history)

STRATEGY = "gap_l1_3"

def nearest_distance(seed, vals):
    i = bisect.bisect_left(vals, seed); c = []
    if i < len(vals): c.append(abs(vals[i] - seed))
    if i > 0: c.append(abs(seed - vals[i - 1]))
    return min(c) if c else None

def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_dir = os.environ.get("L1_DIR", "l1-3")
    l2_file = Path(os.environ.get("L2_FILE", "l2_merged/promoted_seed309440000001.json"))
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_l1_3.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    top_n = int(os.environ.get("TOP_N", "10"))
    next_id = get_next_draw_id(csv_path)
    seed_start, seed_end, draws = load_l1_dir(l1_dir)
    last = {}
    for d in draws:
        for s in d.get("seeds", []):
            if s not in last or d["draw_id"] > last[s]: last[s] = d["draw_id"]
    gaps = get_gaps_from_l2_file(l2_file); vals = sorted(get_seed_values_from_l2_file(l2_file))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if not last or not gaps or len(vals) < 2:
        open(out_path, "w", encoding="utf-8").write(
            f"DU DOAN KY {next_id:05d} - MODEL l1-3: chua du du lieu (L1={len(last)} seed, "
            f"L2={len(vals)} seed trung 2 lan). Khong du doan.\n")
        print("[l1-3] chua du du lieu"); return
    avg_dg = sum(gaps) / len(gaps)
    sg = [b - a for a, b in zip(vals, vals[1:]) if b > a]; avg_sg = sum(sg) / len(sg)
    rows = []
    for s, h in last.items():
        g = next_id - h
        if g <= 0: continue
        dist = nearest_distance(s, vals)
        rows.append((abs(g - avg_dg), g, abs(dist - avg_sg), s, h))
    rows.sort()   # gap gan avg nhat -> (hoa gap nho) -> seed distance gan avg -> seed nho
    rank_to_mask = build_rank_to_mask(build_binom())
    # --- LOAI VE TRUNG ve sinh ra tu seed results/final_j1_2plus (J1 >= 2 lan) ---
    banned = set()
    rg = os.environ.get("RESULTS_GLOB", "results/final_j1_2plus_*.json")
    n_res = 0
    for fp in (sorted(glob.glob(rg)) if rg else []):
        for r in json.load(open(fp, encoding="utf-8")).get("results", []):
            n_res += 1
            nums_r, sp_r = predict_ticket(r["seed"], next_id, rank_to_mask)
            banned.add((tuple(nums_r), sp_r))
    top = []; seen = set(); n_excl = 0
    for row in rows:
        nums_c, sp_c = predict_ticket(row[3], next_id, rank_to_mask)
        key = (tuple(nums_c), sp_c)
        if key in banned: n_excl += 1; continue
        if key in seen: continue
        seen.add(key); top.append(row)
        if len(top) >= top_n: break
    preds = []
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_id:05d} - MODEL l1-3 (seed {seed_start}-{seed_end}), khoang cach seed trung J1 2 lan\n")
        f.write(f"L1: {len(last)} seed | L2 (trung 2 lan): {len(vals)} seed | avg_draw_gap={avg_dg:.2f} | avg_seed_gap={avg_sg:,.0f}\n")
        f.write(f"Loai ve trung results/j1_2plus: {len(banned)} ve ({n_res} seed) | ung vien bi loai: {n_excl}\n\n")
        for i, (_, g, _, s, h) in enumerate(top, 1):
            nums, sp = predict_ticket(s, next_id, rank_to_mask)
            f.write(f"#{i}{' (CHINH)' if i == 1 else ''}: {'-'.join(f'{n:02d}' for n in nums)} + DB {sp} | seed {s} | trung gan nhat ky {h:05d} (gap {g})\n")
            if i == 1:
                preds.append({"seed_start": seed_start, "seed": s, "numbers": nums, "special": sp, "file": l1_dir,
                    "total_seeds_in_model": len(last), "last_hit_draw_id": h, "gap_since_hit": g,
                    "avg_draw_gap": round(avg_dg, 2), "draw_gap_source": "own",
                    "n_candidates_same_gap": sum(1 for r in rows if r[1] == g),
                    "avg_seed_gap": round(avg_sg, 2), "seed_gap_source": "own"})
    save_prediction_history(history_dir, next_id, STRATEGY, preds)
    print(f"[l1-3] da ghi {out_path}"); print(f"NEXT_DRAW_ID={next_id}")

if __name__ == "__main__":
    main()
