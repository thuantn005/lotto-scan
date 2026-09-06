#!/usr/bin/env python3
"""
predict_next_draw_ml.py - Du doan ky KE TIEP bang ML, DOC LAP HOAN TOAN
voi predict_next_draw.py (khong sua, khong goi, khong dung chung file
ket qua). Van doc seed tu L1 (l1_merged/*.json) nhu predict_next_draw.py,
nhung tieu chi CHON seed trong tung model khac han:

    predict_next_draw.py (goc)  -> chon seed theo SO LAN TUNG TRUNG cao nhat
    predict_next_draw_ml.py (nay) -> chon seed co VE (5 so + dac biet) cho
        ky ke tiep dat TONG DIEM ML (Logistic Regression tan suat lich su,
        xem ml_scoring.py) CAO NHAT trong so cac seed dang co trong L1 cua
        model do.

KHONG dung L2 lam input. Ghi ra file RIENG: predict/next_draw_predict_ml.txt

ENV:
    CSV_PATH   - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB    - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_PATH   - file .txt ket qua rieng cua ML (mac dinh predict/next_draw_predict_ml.txt)
    ML_SCORES_PATH - file diem so ML da tinh san boi ml_scoring.py
                     (mac dinh predict/ml_scores.json; neu chua co se TU
                     goi ml_scoring.train_number_scores/train_special_scores)
"""

import glob
import json
import os
from pathlib import Path

import ml_scoring

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
        next(f, None)
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


def load_or_train_ml_scores(csv_path, ml_scores_path):
    p = Path(ml_scores_path)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data["number_scores"], data["special_scores"]
        except Exception as e:
            print(f"Khong doc duoc {ml_scores_path} ({e}), se tu train lai.")

    draws = ml_scoring.load_draws(csv_path)
    number_scores = ml_scoring.train_number_scores(draws)
    special_scores = ml_scoring.train_special_scores(draws)
    return {str(k): v for k, v in number_scores.items()}, {str(k): v for k, v in special_scores.items()}


def pick_best_seed_by_ml(fp, next_draw_id, rank_to_mask, number_scores, special_scores):
    try:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Bo qua {fp}: {e}")
        return None

    seeds = set()
    for d in data.get("draws", []):
        for s in d.get("seeds", []):
            seeds.add(s)
    if not seeds:
        return None

    best_seed, best_score, best_ticket = None, None, None
    for s in seeds:
        numbers, special = predict_ticket(s, next_draw_id, rank_to_mask)
        score = sum(number_scores.get(str(n), 0.5) for n in numbers) + special_scores.get(str(special), 0.5)
        if best_score is None or score > best_score or (score == best_score and s < best_seed):
            best_seed, best_score, best_ticket = s, score, (numbers, special)

    return {
        "seed": best_seed,
        "ml_score": best_score,
        "numbers": best_ticket[0],
        "special": best_ticket[1],
        "seed_start": data.get("seed_start"),
        "total_seeds_in_model": len(seeds),
        "file": fp,
    }


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_ml.txt")
    ml_scores_path = os.environ.get("ML_SCORES_PATH", "predict/ml_scores.json")

    next_draw_id = get_next_draw_id(csv_path)
    files = sorted(glob.glob(l1_glob))
    print(f"[ML] Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"[ML] So file model L1 tim thay: {len(files)}")

    number_scores, special_scores = load_or_train_ml_scores(csv_path, ml_scores_path)

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    predictions = []
    for fp in files:
        info = pick_best_seed_by_ml(fp, next_draw_id, rank_to_mask, number_scores, special_scores)
        if info:
            predictions.append(info)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN ML (doc lap voi predict_next_draw.py)\n")
        f.write("Tieu chi chon seed: trong tat ca seed dang co trong L1 cua tung model,\n")
        f.write("chon seed co ve (5 so + dac biet) dat TONG DIEM ML (Logistic Regression\n")
        f.write("tan suat lich su) CAO NHAT.\n\n")
        for info in predictions:
            nums_str = "-".join(f"{n:02d}" for n in info["numbers"])
            f.write(f"--- Model (l1_merged file: {info['file']}) ---\n")
            f.write(f"  seed_start cua model: {info['seed_start']}\n")
            f.write(f"  so seed trong L1 cua model nay: {info['total_seeds_in_model']}\n")
            f.write(f"  seed duoc chon (diem ML cao nhat): {info['seed']} (diem={info['ml_score']:.4f})\n")
            f.write(f"  DU DOAN ky {next_draw_id:05d}: {nums_str} + DAC BIET {info['special']}\n\n")

    print(f"[ML] Da ghi {len(predictions)} du doan vao {out_path}")
    print(f"NEXT_DRAW_ID={next_draw_id}")


if __name__ == "__main__":
    main()
