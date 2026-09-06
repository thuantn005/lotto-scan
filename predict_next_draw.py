#!/usr/bin/env python3
"""
predict_next_draw.py - Du doan ky KE TIEP: MOI MODEL (moi file trong
l1_merged/) chon ra DUNG 1 SEED lam du doan rieng cua model do - KHONG
gop phieu bau tat ca seed lai thanh 1 bo so chung.

Seed duoc chon trong tung model = seed dang co trong L1 cua model do voi
so lan tung trung (weight) CAO NHAT (seed "manh" nhat, gan voi nguong
thang hang L2 nhat). Neu seed nay du doan dung cho ky ke tiep, no se
THANG HANG (thanh L2) ngay khi ky moi duoc xac nhan.

KHONG dung L2 (l2_merged/) lam input - L2 chi la KET QUA thang hang.

Thuat toan giu NGUYEN 100% cong thuc trong scan_per_draw.cpp:
    combined = seed*M1 + draw_id*M2   (mod 2^64)
    mixed    = mix64(combined)
    rank     = mixed mod C(35,5)
    mask     = unrank_colex(rank)      -> 5 so chinh
    mixed2   = mix64(mixed)
    special  = mixed2 mod 12 + 1

ENV:
    CSV_PATH   - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB    - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_PATH   - file .txt ket qua (mac dinh predict/next_draw_predict.txt)
"""

import glob
import json
import os
from pathlib import Path

M1 = 0x9E3779B97F4A7C15
M2 = 0xD1B54A32D192ED03
M3 = 0xBF58476D1CE4E5B9
M4 = 0x94D049BB133111EB
MASK64 = 0xFFFFFFFFFFFFFFFF
C = 324632  # C(35,5)


def build_binom():
    binom = [[0] * 6 for _ in range(36)]
    for n in range(36):
        for k in range(6):
            if k == 0:
                binom[n][k] = 1
            elif k > n:
                binom[n][k] = 0
            else:
                num, den = 1, 1
                for i in range(k):
                    num *= (n - i)
                    den *= (i + 1)
                binom[n][k] = num // den
    return binom


def build_rank_to_mask(binom):
    lut = [0] * C
    for r in range(C):
        mask, rem = 0, r
        for k in range(5, 0, -1):
            x = k - 1
            while binom[x + 1][k] <= rem:
                x += 1
            mask |= (1 << x)
            rem -= binom[x][k]
        lut[r] = mask
    return lut


def mix64(x):
    x &= MASK64
    x ^= (x >> 30)
    x = (x * M3) & MASK64
    x ^= (x >> 27)
    x = (x * M4) & MASK64
    x ^= (x >> 31)
    return x


def predict_ticket(seed, draw_id, rank_to_mask):
    combined = (seed * M1 + draw_id * M2) & MASK64
    mixed = mix64(combined)
    rank = mixed % C
    mask = rank_to_mask[rank]
    mixed2 = mix64(mixed)
    special = (mixed2 % 12) + 1
    numbers = [i + 1 for i in range(35) if mask & (1 << i)]
    return numbers, special


def get_next_draw_id(csv_path):
    max_id = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        next(f, None)  # header
        for line in f:
            parts = line.split(",", 2)
            if len(parts) < 2:
                continue
            try:
                did = int(parts[1])
            except ValueError:
                continue
            if did > max_id:
                max_id = did
    return max_id + 1


def pick_strongest_seed_per_model(fp):
    """Doc 1 file L1, tra ve (seed manh nhat, weight, so ky da trung, seed_start)
    hoac None neu file rong. 'Manh nhat' = so lan tung trung (weight) CAO
    NHAT trong model nay; hoa thi chon seed nho nhat de on dinh ket qua."""
    try:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Bo qua {fp}: {e}")
        return None

    seed_weight = {}
    seed_last_draw = {}
    for d in data.get("draws", []):
        did = d.get("draw_id")
        for s in d.get("seeds", []):
            seed_weight[s] = seed_weight.get(s, 0) + 1
            seed_last_draw[s] = max(seed_last_draw.get(s, 0), did or 0)

    if not seed_weight:
        return None

    best_seed = min(seed_weight.keys(), key=lambda s: (-seed_weight[s], s))
    return {
        "seed": best_seed,
        "weight": seed_weight[best_seed],
        "last_hit_draw": seed_last_draw[best_seed],
        "seed_start": data.get("seed_start"),
        "total_draws_in_model": data.get("total_draws"),
        "total_seeds_in_model": len(seed_weight),
    }


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict.txt")

    next_draw_id = get_next_draw_id(csv_path)
    files = sorted(glob.glob(l1_glob))
    print(f"Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"So file model L1 tim thay: {len(files)}")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    predictions = []
    for fp in files:
        info = pick_strongest_seed_per_model(fp)
        if info is None:
            continue
        numbers, special = predict_ticket(info["seed"], next_draw_id, rank_to_mask)
        info["file"] = fp
        info["numbers"] = numbers
        info["special"] = special
        predictions.append(info)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - MOI MODEL 1 SEED (khong gop phieu bau, khong dung L2)\n")
        f.write(f"Seed manh nhat cua tung model = seed co so lan trung (trong L1 cua model do) cao nhat.\n")
        f.write(f"Neu seed nay du doan dung ky {next_draw_id:05d}, no se THANG HANG (thanh L2) ngay ky nay.\n\n")

        for info in predictions:
            nums_str = "-".join(f"{n:02d}" for n in info["numbers"])
            f.write(f"--- Model (l1_merged file: {info['file']}) ---\n")
            f.write(f"  seed_start cua model: {info['seed_start']}\n")
            f.write(f"  so seed con lai trong L1 cua model nay: {info['total_seeds_in_model']}\n")
            f.write(f"  seed duoc chon (manh nhat): {info['seed']}\n")
            f.write(f"  seed nay da tung trung: {info['weight']} lan (lan gan nhat: ky {info['last_hit_draw']:05d})\n")
            f.write(f"  DU DOAN ky {next_draw_id:05d}: {nums_str} + DAC BIET {info['special']}\n\n")

    print(f"Da ghi {len(predictions)} du doan (1 model = 1 seed) vao {out_path}")
    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_MODELS={len(predictions)}")


if __name__ == "__main__":
    main()
