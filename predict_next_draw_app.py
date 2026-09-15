#!/usr/bin/env python3
"""
predict_next_draw_app.py - Du doan ky KE TIEP: giong het "base"
(predict_next_draw.py) o cho MOI MODEL (moi file trong l1_merged/) tu
sinh ra du doan RIENG cua model do (khong gop het seed cua moi file lai
thanh 1 pool chung nua) - CHI khac o CACH CHON seed trong tung file:

  - base (predict_next_draw.py): chon seed MANH NHAT (so lan tung trung
    cao nhat) trong file do.
  - app (file nay): chon NGAU NHIEN DEU 1 seed trong file do (dung
    random.SystemRandom, tuong duong Random.secure() ben Dart cua app
    Flutter "San Chia Giai 535" - tab "Sinh So Tu Seed") - KHONG uu tien
    seed nao, dung tinh than "random pick" cua app.

CO CHE:
  1. Voi TUNG file trong l1_merged/merged_seed*.json (moi file = 1
     "model"/1 dai seed rieng), gop TOAN BO seed cua rieng file do (khong
     phan biet seed thuoc ky nao trong file) thanh 1 pool CUA RIENG MODEL
     do.
  2. Voi moi model, CHON NGAU NHIEN 1 seed tu pool cua model do.
  3. Ap dung DUNG cong thuc predict_ticket(seed, next_draw_id) (chinh la
     TicketFormula.generate ben Dart / scan_v2.cpp): rank =
     mix64(seed*M1 + draw_id*M2) mod C(35,5) -> unrank thanh 5 so chinh;
     special = mix64(rank_mixed) mod 12 + 1.

-> So ve sinh ra = so file model L1 co seed (KHONG con co dinh
APP_LINE_COUNT nhu truoc - moi model dung 1 ve rieng, giong het cach base
lam viec, chi khac cach chon seed trong tung model).

Day CHI la mo phong lai co che RANDOM PICK cua app tren GitHub Actions de
theo doi/doi chieu tu dong - KHONG mang y nghia du doan tot hon random.
backtest_predictions.py da xac nhan khong chien luoc nao (base/app) hon
duoc random mot cach co y nghia thong ke.

ENV:
    CSV_PATH    - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB     - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_PATH    - file .txt ket qua (mac dinh predict/next_draw_predict_app.txt)
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

STRATEGY = "app"

# Nguon ngau nhien CHI dung de CHON seed trong tung model - giong
# Random.secure() ben Dart: moi seed trong pool cua model co xac suat
# duoc chon BANG NHAU, khong uu tien seed nao (khac voi base la chon
# theo weight).
_rng = random.SystemRandom()


def load_seed_pool_of_file(fp):
    """Doc 1 file L1, tra ve (set TOAN BO seed cua RIENG file nay - gop
    tat ca cac ky trong file lai, seed_start cua model) hoac None neu
    file rong/loi."""
    try:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Bo qua {fp}: {e}")
        return None

    pool = set()
    for d in data.get("draws", []):
        seeds = d.get("seeds")
        if seeds:
            pool.update(seeds)

    if not pool:
        return None
    return pool, data.get("seed_start"), data.get("total_draws")


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_app.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")

    next_draw_id = get_next_draw_id(csv_path)
    files = sorted(glob.glob(l1_glob))
    print(f"[App] Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"[App] So file model L1 tim thay: {len(files)}")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    predictions = []
    for fp in files:
        info = load_seed_pool_of_file(fp)
        if info is None:
            continue
        pool, seed_start, total_draws = info

        seed = _rng.choice(sorted(pool))
        numbers, special = predict_ticket(seed, next_draw_id, rank_to_mask)
        predictions.append({
            "file": fp,
            "seed_start": seed_start,
            "total_seeds_in_model": len(pool),
            "total_draws_in_model": total_draws,
            "seed": seed,
            "numbers": numbers,
            "special": special,
        })

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN APP (moi model 1 ve, chon\n")
        f.write("NGAU NHIEN DEU 1 seed trong pool cua RIENG model do - mo phong co che\n")
        f.write("random pick cua app Flutter 'San Chia Giai 535', khac 'base' o cho\n")
        f.write("khong uu tien seed manh nhat) roi ap dung cong thuc hash giong\n")
        f.write("TicketFormula.dart / scan_v2.cpp (khong AI/ML).\n\n")

        for info in predictions:
            nums_str = "-".join(f"{n:02d}" for n in info["numbers"])
            f.write(f"--- Model (l1_merged file: {info['file']}) ---\n")
            f.write(f"  seed_start cua model: {info['seed_start']}\n")
            f.write(f"  so seed trong L1 cua model nay: {info['total_seeds_in_model']}\n")
            f.write(f"  seed duoc chon (ngau nhien deu): {info['seed']}\n")
            f.write(f"  DU DOAN ky {next_draw_id:05d}: {nums_str} + DAC BIET {info['special']}\n\n")

        if not predictions:
            f.write("(Khong co model nao co seed, khong co du doan.)\n")

    hpath = save_prediction_history(history_dir, next_draw_id, STRATEGY, predictions)

    print(f"[App] Da ghi {len(predictions)} du doan (1 model = 1 ve) vao {out_path}")
    print(f"[App] Da luu lich su du doan ({STRATEGY}) vao {hpath}")
    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_MODELS={len(predictions)}")


if __name__ == "__main__":
    main()
