#!/usr/bin/env python3
"""
predict_next_draw_seed.py - Du doan ky KE TIEP: MOI MODEL (moi file trong
l1_merged/) chon ra DUNG 1 SEED lam du doan rieng cua model do - KHONG
gop phieu bau tat ca seed lai thanh 1 bo so chung.

Seed duoc chon trong tung model = seed dang co trong L1 cua model do voi
so lan tung trung (weight) CAO NHAT (seed "manh" nhat, gan voi nguong
thang hang L2 nhat). Neu seed nay du doan dung cho ky ke tiep, no se
THANG HANG (thanh L2) ngay khi ky moi duoc xac nhan.

KHONG dung L2 (l2_merged/) lam input - L2 chi la KET QUA thang hang.
KHONG dung AI/ML gi ca - chi la 1 quy tac co dinh (chon weight cao nhat).

Doi chung voi predict_next_draw_random.py (boc so ngau nhien thuan tuy,
khong lien quan seed) - so sanh 2 chien luoc nay theo thoi gian se cho
biet co "tin hieu" gi trong du lieu seed hay khong.

Thuat toan sinh ve + cac ham dung chung nam trong lotto_common.py.

Chien luoc nay duoc danh dau la "seed" trong lich su du doan
(predict/history/{draw_id}_seed.txt).

ENV:
    CSV_PATH    - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB     - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_PATH    - file .txt ket qua (mac dinh predict/next_draw_predict_seed.txt)
    HISTORY_DIR - thu muc luu lich su du doan (mac dinh predict/history)
"""

import glob
import json
import os
import random
from pathlib import Path

from lotto_common import (
    build_binom,
    build_rank_to_mask,
    predict_ticket,
    get_next_draw_id,
    save_prediction_history,
)

STRATEGY = "seed"

# Nguon ngau nhien CHI dung de PHA HOA giua cac seed cung dat weight cao
# nhat trong 1 model (xem pick_strongest_seed_per_model) - KHONG dung de
# chon seed nhu predict_next_draw_random.py (o day van uu tien weight
# cao nhat truoc, chi random khi thuc su hoa).
_rng = random.SystemRandom()


def pick_strongest_seed_per_model(fp):
    """Doc 1 file L1, tra ve (seed manh nhat, weight, so ky da trung, seed_start)
    hoac None neu file rong. 'Manh nhat' = so lan tung trung (weight) CAO
    NHAT trong model nay; neu co NHIEU seed cung dat weight cao nhat do,
    CHON NGAU NHIEN 1 trong so do (thay vi luon lay seed nho nhat - cach
    cu KHONG mang y nghia thong ke gi, chi de ket qua on dinh)."""
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

    max_weight = max(seed_weight.values())
    top_seeds = [s for s, w in seed_weight.items() if w == max_weight]
    best_seed = _rng.choice(top_seeds)
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
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_seed.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")

    next_draw_id = get_next_draw_id(csv_path)
    files = sorted(glob.glob(l1_glob))
    print(f"[Seed] Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"[Seed] So file model L1 tim thay: {len(files)}")

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
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN SEED (moi model 1 seed manh nhat,\n"
                f"khong gop phieu bau, khong dung L2, khong AI/ML)\n")
        f.write("Seed manh nhat cua tung model = seed co so lan trung (trong L1 cua model do) cao nhat.\n")
        f.write(f"Neu seed nay du doan dung ky {next_draw_id:05d}, no se THANG HANG (thanh L2) ngay ky nay.\n\n")

        if not predictions:
            f.write("(Khong tim thay model L1 nao co seed, khong co du doan.)\n")

        for info in predictions:
            nums_str = "-".join(f"{n:02d}" for n in info["numbers"])
            f.write(f"--- Model (l1_merged file: {info['file']}) ---\n")
            f.write(f"  seed_start cua model: {info['seed_start']}\n")
            f.write(f"  so seed con lai trong L1 cua model nay: {info['total_seeds_in_model']}\n")
            f.write(f"  seed duoc chon (manh nhat): {info['seed']}\n")
            f.write(f"  seed nay da tung trung: {info['weight']} lan (lan gan nhat: ky {info['last_hit_draw']:05d})\n")
            f.write(f"  DU DOAN ky {next_draw_id:05d}: {nums_str} + DAC BIET {info['special']}\n\n")

    hpath = save_prediction_history(history_dir, next_draw_id, STRATEGY, predictions)

    print(f"[Seed] Da ghi {len(predictions)} du doan (1 model = 1 seed) vao {out_path}")
    print(f"[Seed] Da luu lich su du doan ({STRATEGY}) vao {hpath}")
    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_MODELS={len(predictions)}")


if __name__ == "__main__":
    main()
