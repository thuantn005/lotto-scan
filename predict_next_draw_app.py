#!/usr/bin/env python3
"""
predict_next_draw_app.py - Du doan ky KE TIEP theo DUNG co che sinh so cua
app Flutter "San Chia Giai 535" (man hinh RandomPickScreen + GithubSeedSource
+ TicketFormula trong gplxvn) - PORT sang Python de tu dong hoa tren GitHub
Actions, thay vi phai mo app bam tay moi ky.

CO CHE (giu dung 100% logic cua app, xem github_seed_source.dart):
  1. Gop seed tu TOAN BO file l1_merged/merged_seed*.json (cung nguon du
     lieu app dang doc, chi khac la app tro toi 1 file con o day co nhieu
     model/file song song nen gop chung lai theo TUNG KY).
  2. CHI GIU seed cua cac ky nam trong "cua so uu tien": cach ky can du
     doan (next_draw_id) TOI THIEU APP_GAP_DRAWS ky (mac dinh 200), va
     cua so rong APP_WINDOW_DRAWS ky (mac dinh 500) tinh tu moc do lui ve
     qua khu. Vi du next_draw_id=800, gap=200, window=500:
       windowEnd   = 800 - 200 = 600
       windowStart = max(1, 600 - 500 + 1) = 101
     -> chi dung seed cua ky nam trong [101, 600].
  3. Neu cua so do rong (chua du 500 ky lich su tinh tu moc "cach 200
     ky") -> fallback dung TOAN BO ky <= windowEnd; neu van rong (ky hien
     tai qua som, < gap_draws) -> fallback dung TOAN BO seed dang co -
     giong dung 3 nhanh fallback trong _windowFilter() ben Dart.
  4. CHON NGAU NHIEN (khong uu tien seed nao - dung random.SystemRandom,
     tuong duong Random.secure() ben Dart) N seed KHONG TRUNG tu pool do.
  5. Voi moi seed, ap dung DUNG cong thuc predict_ticket(seed, next_draw_id)
     (chinh la TicketFormula.generate ben Dart / scan_v2.cpp): rank =
     mix64(seed*M1 + draw_id*M2) mod C(35,5) -> unrank thanh 5 so chinh;
     special = mix64(rank_mixed) mod 12 + 1.

Day CHI la mo phong LAI CHINH XAC co che cua app tren GitHub Actions de
theo doi/doi chieu tu dong - KHONG mang y nghia du doan tot hon random.
backtest_predictions_v2.py da xac nhan khong chien luoc nao (base/ml/ai/
ai2/ai3/seed/app) hon duoc random mot cach co y nghia thong ke.

ENV:
    CSV_PATH         - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB          - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_PATH         - file .txt ket qua (mac dinh predict/next_draw_predict_app.txt)
    HISTORY_DIR      - thu muc luu lich su du doan (mac dinh predict/history)
    APP_GAP_DRAWS    - so ky toi thieu phai cach ky dang sinh so (mac dinh 200)
    APP_WINDOW_DRAWS - be rong cua so uu tien tinh tu moc gap (mac dinh 500)
    APP_LINE_COUNT   - so ve sinh ra moi ky (mac dinh 5, giong max cua slider "So ve" trong app)
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

# Nguon ngau nhien CHI dung de CHON seed trong pool - giong Random.secure()
# ben Dart: moi seed trong pool co xac suat duoc chon BANG NHAU, khong uu
# tien seed nao (khac voi predict_next_draw_seed.py la chon theo weight).
_rng = random.SystemRandom()


def load_seed_pool_by_draw(l1_glob):
    """Doc TOAN BO file L1, tra ve dict {draw_id: set(seeds)} - gop tat ca
    model lai theo TUNG KY. App (GithubSeedSource) doc 1 file JSON duy
    nhat co cau truc {"draws": [{"draw_id":.., "seeds":[..]}, ...]} - o
    day repo co NHIEU file L1 (nhieu model quet song song) nen gop chung
    lai truoc khi loc theo cua so, cho ra 1 pool tuong duong."""
    by_draw = {}
    for fp in sorted(glob.glob(l1_glob)):
        try:
            data = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Bo qua {fp}: {e}")
            continue
        for d in data.get("draws", []):
            did = d.get("draw_id")
            seeds = d.get("seeds")
            if did is None or not seeds:
                continue
            by_draw.setdefault(did, set()).update(seeds)
    return by_draw


def window_filter(by_draw, next_draw_id, gap_draws, window_draws):
    """PORT NGUYEN VAN logic _windowFilter() cua GithubSeedSource.dart -
    tra ve (list seed cua pool, (windowStart, windowEnd, che_do))."""
    window_end = next_draw_id - gap_draws
    window_start = max(1, window_end - window_draws + 1)

    in_window = set()
    for did, seeds in by_draw.items():
        if window_start <= did <= window_end:
            in_window.update(seeds)
    if in_window:
        return sorted(in_window), (window_start, window_end, "window")

    # Chua du lich su tinh tu moc "cach gap_draws ky" - dung tam moi ky
    # <= windowEnd, giong nhanh fallback dau tien ben Dart.
    if window_end >= 1:
        fallback = set()
        for did, seeds in by_draw.items():
            if did <= window_end:
                fallback.update(seeds)
        if fallback:
            return sorted(fallback), (window_start, window_end, "fallback_all_before_gap")

    # Van rong (ky hien tai < gap_draws, hau nhu khong xay ra thuc te) -
    # dung tam TOAN BO seed dang co.
    everything = set()
    for seeds in by_draw.values():
        everything.update(seeds)
    return sorted(everything), (window_start, window_end, "fallback_everything")


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_app.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    gap_draws = int(os.environ.get("APP_GAP_DRAWS", "200"))
    window_draws = int(os.environ.get("APP_WINDOW_DRAWS", "500"))
    line_count = int(os.environ.get("APP_LINE_COUNT", "5"))

    next_draw_id = get_next_draw_id(csv_path)
    print(f"[App] Ky ke tiep can du doan: {next_draw_id:05d}")

    by_draw = load_seed_pool_by_draw(l1_glob)
    print(f"[App] So ky co seed trong L1: {len(by_draw)}")

    pool, (w_start, w_end, mode) = window_filter(by_draw, next_draw_id, gap_draws, window_draws)
    print(f"[App] Cua so uu tien: ky [{w_start:05d}, {w_end:05d}] - che do: {mode} - pool: {len(pool)} seed")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    tickets = []
    if pool:
        n = min(line_count, len(pool))
        picked_seeds = _rng.sample(pool, n)
        for seed in picked_seeds:
            numbers, special = predict_ticket(seed, next_draw_id, rank_to_mask)
            tickets.append({"seed": seed, "numbers": numbers, "special": special})

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN APP (mo phong DUNG co che\n")
        f.write("sinh so cua app Flutter 'San Chia Giai 535' - tab Sinh So Tu Seed):\n")
        f.write(f"chon ngau nhien seed trong cua so uu tien [ky {w_start:05d}, ky {w_end:05d}]\n")
        f.write(f"(cach {gap_draws} ky, rong {window_draws} ky), roi ap dung cong thuc hash\n")
        f.write("giong TicketFormula.dart / scan_v2.cpp (khong AI/ML, khong uu tien seed).\n")
        f.write(f"Che do pool: {mode} | Tong so seed trong pool: {len(pool)}\n\n")

        if not tickets:
            f.write("(Pool seed rong, khong co du doan.)\n")

        for i, t in enumerate(tickets, start=1):
            nums_str = "-".join(f"{n:02d}" for n in t["numbers"])
            f.write(f"Ve {i}: {nums_str} + DAC BIET {t['special']:02d} (seed {t['seed']})\n")

    hist_predictions = [
        {
            "seed_start": w_start,
            "seed": t["seed"],
            "numbers": t["numbers"],
            "special": t["special"],
            "file": mode,
        }
        for t in tickets
    ]
    hpath = save_prediction_history(history_dir, next_draw_id, STRATEGY, hist_predictions)

    print(f"[App] Da ghi {len(tickets)} ve vao {out_path}")
    print(f"[App] Da luu lich su du doan ({STRATEGY}) vao {hpath}")
    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_TICKETS={len(tickets)}")


if __name__ == "__main__":
    main()
