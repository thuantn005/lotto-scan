#!/usr/bin/env python3
"""
predict_l1_3_gap.py - DU DOAN 1 VE, chon TRUC TIEP tu VE CON LAI trong l0/.

Moi lan chay:
  1. l200: doi chieu ve trung cua ky vua quay voi l0/ cua ky do (doc du doan cu truoc khi xoa).
  2. Xoa MOI du doan hien co (predict/) va l0/ cu.
  3. l0/: to hop J1 (324,632 x 12 = 3,895,584 ve) loai ve do seed trong results/ (J1 2 lan, 3 lan, >=4 lan)
     sinh ra cho ky ke tiep -> ghi l0/kyNNNNN_ve_con_lai.txt.gz.
  4. Du doan 1 ve = 1 dong NGAU NHIEN trong file ve con lai (khong co quy tac chon).
CANH BAO: loai ve khong doi xac suat 1 ve (~1/3.9 trieu); RNG khong du doan duoc.

ENV: CSV_PATH (data/all.csv), OUT_PATH (predict/next_draw_predict_l1_3.txt), HISTORY_DIR (predict/history),
     L0_DIR (l0), L200_DIR (l200), RESULTS_GLOB (results/final_j1_*plus*.json*)
"""
import gzip, os, random
from l0_l200 import load_result_seeds, build_excluded, write_l0, clear_dir, read_old_prediction, record_l200, fmt
from lotto_common import (build_binom, build_rank_to_mask, predict_ticket, get_next_draw_id,
    get_actual_result, save_prediction_history)

STRATEGY = "l0_random"


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_l1_3.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    l0_dir = os.environ.get("L0_DIR", "l0"); l200_dir = os.environ.get("L200_DIR", "l200")
    next_id = get_next_draw_id(csv_path); prev_id = next_id - 1
    rank_to_mask = build_rank_to_mask(build_binom())
    seeds = load_result_seeds(os.environ.get("RESULTS_GLOB", "results/final_j1_*plus*.json*"))

    # 1) l200: ghi VE TRUNG cua ky vua quay (doc du doan cu + l0 cu TRUOC khi xoa)
    actual = get_actual_result(csv_path, f"{prev_id:05d}")
    if actual:
        record_l200(l200_dir, prev_id, actual, build_excluded(prev_id, seeds, predict_ticket, rank_to_mask),
                    read_old_prediction(history_dir, prev_id), l0_dir)

    # 2) xoa moi du doan hien co + l0 cu
    clear_dir(os.path.dirname(out_path) or "predict"); clear_dir(l0_dir)

    # 3) l0: ve con lai cua ky ke tiep
    excluded = build_excluded(next_id, seeds, predict_ticket, rank_to_mask)
    remain = write_l0(l0_dir, next_id, seeds, excluded)

    # 4) du doan 1 ve: dong IDX (tinh tu 1) trong file ve con lai
    idx = random.SystemRandom().randrange(remain)   # ngau nhien that, khong quy tac
    with gzip.open(os.path.join(l0_dir, f"ky{next_id:05d}_ve_con_lai.txt.gz"), "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == idx: ticket = line.strip(); break
    nums_s, sp_s = ticket.split(" + ")
    nums = [int(x) for x in nums_s.split("-")]; sp = int(sp_s)
    assert (tuple(nums), sp) not in excluded

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_id:05d} - chon truc tiep tu VE CON LAI trong l0\n")
        f.write(f"l0: tong {324632 * 12:,} ve | bi loai {len(excluded):,} (tu {len(seeds):,} seed results J1>=2) | CON LAI {remain:,}\n")
        f.write(f"Chon ngau nhien, khong quy tac: dong {idx + 1:,}/{remain:,} trong l0/ky{next_id:05d}_ve_con_lai.txt.gz\n\n")
        f.write(f"DU DOAN: {ticket}\n")
    save_prediction_history(history_dir, next_id, STRATEGY,
        [{"seed_start": "", "seed": f"l0#{idx + 1}", "numbers": nums, "special": sp, "file": f"l0/ky{next_id:05d}_ve_con_lai.txt.gz"}])
    print(f"[l0] da ghi {out_path}: {ticket} (dong {idx + 1:,}/{remain:,})"); print(f"NEXT_DRAW_ID={next_id}")


if __name__ == "__main__":
    main()
