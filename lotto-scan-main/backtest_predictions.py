#!/usr/bin/env python3
"""
backtest_predictions.py - Backtest WALK-FORWARD (khong nhin truoc tuong
lai) cho chien luoc chon seed theo "so lan tung trung" (giong het
predict_next_draw.py), chay tren TOAN BO lich su da co san trong tung
file l1_merged/merged_seed*.json - thay vi phai cho tung ngay 1 mau du
lieu that (nhu check_prediction_result.py), backtest nay dung lai LICH
SU DA QUET SAN de tao ra HANG TRAM diem du lieu ngay lap tuc.

QUAN TRONG - tranh "nhin truoc tuong lai" (lookahead bias): voi MOI ky
draw_id trong 1 model, seed duoc chon CHI dua tren so lan tung trung cua
seed do o CAC KY TRUOC draw_id nay (khong bao gom chinh ky dang du doan).
Neu khong lam vay, ket qua se bi thoi phong gia tao (vi "weight" cua 1
seed von di bao gom ca viec no co trung ky dang xet hay khong).

Vi seed_start/seed_count cua tung model la CO DINH va KHONG lien quan gi
den ket qua thuc te, day la 1 cach kiem tra RAT NGHIEM NGAT xem "chon
seed theo so lan tung trung" co thuc su hon xac suat ngau nhien hay
khong - hay chi la nhieu (dac biet voi model 682305800400: ~400 seed
tinh co trung MOI ky trong so 1.56 ty seed, dung bang ky vong ngau nhien
1.56e9 / 3,895,584 co the ~ 400.2 - xem docstring lotto_common.py).

Ghi bao cao ra predict/backtest_report.txt (doc duoc) va
predict/backtest_stats.json (may doc duoc).

ENV:
    CSV_PATH   - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB    - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_REPORT - file .txt bao cao (mac dinh predict/backtest_report.txt)
    OUT_STATS  - file .json thong ke (mac dinh predict/backtest_stats.json)
"""

import glob
import json
import os
from pathlib import Path

from lotto_common import (
    build_binom,
    build_rank_to_mask,
    predict_ticket,
    load_all_actual_results,
    score_ticket,
    EXPECTED_RANDOM_MATCHES,
    EXPECTED_RANDOM_SPECIAL_HIT_RATE,
)


def empty_agg():
    return {
        "draws_evaluated": 0,
        "matches_hist": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "special_hits": 0,
        "j1_hits": 0,
        "sum_matches": 0,
    }


def add_score(agg, sc):
    agg["draws_evaluated"] += 1
    agg["matches_hist"][str(sc["matches"])] += 1
    agg["sum_matches"] += sc["matches"]
    if sc["special_hit"]:
        agg["special_hits"] += 1
    if sc["is_j1"]:
        agg["j1_hits"] += 1


def backtest_one_model(fp, actual_results, rank_to_mask):
    try:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Bo qua {fp}: {e}")
        return None

    draws = sorted(data.get("draws", []), key=lambda d: d.get("draw_id", 0))
    agg = empty_agg()
    per_draw = []
    seed_weight = {}  # CHI cap nhat SAU KHI da du doan xong ky hien tai

    for d in draws:
        draw_id = d.get("draw_id")
        seeds_this_draw = d.get("seeds", [])

        # --- Du doan cho draw_id nay, CHI dung weight tich luy TU CAC KY
        # TRUOC (khong bao gom seeds_this_draw) ---
        if seed_weight:
            best_seed = min(seed_weight.keys(), key=lambda s: (-seed_weight[s], s))
            actual = actual_results.get(draw_id)
            if actual is not None:
                actual_numbers, actual_special, _ = actual
                pred_numbers, pred_special = predict_ticket(best_seed, draw_id, rank_to_mask)
                sc = score_ticket(pred_numbers, pred_special, actual_numbers, actual_special)
                add_score(agg, sc)
                per_draw.append({"draw_id": draw_id, "seed": best_seed, **sc})

        # --- CHI SAU KHI da du doan xong, moi "hoc" them tu ky nay cho
        # cac ky SAU (dung thu tu nay moi la walk-forward that su) ---
        for s in seeds_this_draw:
            seed_weight[s] = seed_weight.get(s, 0) + 1

    return {
        "file": fp,
        "seed_start": data.get("seed_start"),
        "seed_end": data.get("seed_end"),
        "total_draws_in_file": len(draws),
        "agg": agg,
        "per_draw": per_draw,
    }


def format_agg_line(label, agg):
    n = agg["draws_evaluated"]
    if n == 0:
        return f"  {label}: khong co ky nao du dieu kien backtest (chua tich luy duoc seed nao truoc do)."
    avg = agg["sum_matches"] / n
    sp_rate = agg["special_hits"] / n
    hist = ", ".join(f"{k}so:{v}" for k, v in sorted(agg["matches_hist"].items()))
    return (f"  {label}: {n} ky da backtest - trung binh {avg:.3f} so/ve "
            f"(moc ngau nhien {EXPECTED_RANDOM_MATCHES:.3f}), ty le trung dac biet "
            f"{sp_rate:.3f} (moc {EXPECTED_RANDOM_SPECIAL_HIT_RATE:.3f}), J1: {agg['j1_hits']} | "
            f"phan bo so trung: {hist}")


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    out_report = os.environ.get("OUT_REPORT", "predict/backtest_report.txt")
    out_stats = os.environ.get("OUT_STATS", "predict/backtest_stats.json")

    actual_results = load_all_actual_results(csv_path)
    print(f"Da doc {len(actual_results)} ky thuc te tu {csv_path}")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    files = sorted(glob.glob(l1_glob))
    print(f"So file model L1 tim thay: {len(files)}")

    per_model_results = []
    overall = empty_agg()

    for fp in files:
        res = backtest_one_model(fp, actual_results, rank_to_mask)
        if res is None:
            continue
        per_model_results.append(res)
        for row in res["per_draw"]:
            sc = {"matches": row["matches"], "special_hit": row["special_hit"], "is_j1": row["is_j1"]}
            add_score(overall, sc)

    os.makedirs(os.path.dirname(out_report) or ".", exist_ok=True)
    lines = []
    lines.append("BACKTEST WALK-FORWARD - chien luoc 'base' (chon seed theo so lan tung trung)")
    lines.append("Du doan cho ky N CHI dung thong tin cac ky < N (khong nhin truoc), nen day la")
    lines.append("phep thu NGHIEM NGAT xem chien luoc nay co that su hon ngau nhien khong.\n")

    for res in per_model_results:
        lines.append(f"--- Model: {res['file']} (seed_start={res['seed_start']}, "
                     f"{res['total_draws_in_file']} ky co san trong file) ---")
        lines.append(format_agg_line("Ket qua backtest", res["agg"]))
        lines.append("")

    lines.append("=== TONG HOP TAT CA MODEL ===")
    lines.append(format_agg_line("TOAN BO", overall))

    report_text = "\n".join(lines)
    Path(out_report).write_text(report_text, encoding="utf-8")
    print("\n" + report_text)

    stats_out = {
        "per_model": [
            {
                "file": r["file"],
                "seed_start": r["seed_start"],
                "seed_end": r["seed_end"],
                "total_draws_in_file": r["total_draws_in_file"],
                "agg": r["agg"],
            }
            for r in per_model_results
        ],
        "overall": overall,
        "expected_random_matches": EXPECTED_RANDOM_MATCHES,
        "expected_random_special_hit_rate": EXPECTED_RANDOM_SPECIAL_HIT_RATE,
    }
    Path(out_stats).write_text(json.dumps(stats_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDa ghi bao cao vao {out_report} va {out_stats}")


if __name__ == "__main__":
    main()
