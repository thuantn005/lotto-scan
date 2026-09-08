#!/usr/bin/env python3
"""
check_prediction_result.py - Khi 1 ky MOI duoc xac nhan, doc lai TAT CA
cac file lich su du doan da luu TU TRUOC cho ky do
(predict/history/{draw_id}_{strategy}.txt - moi chien luoc 1 file rieng,
xem lotto_common.py) va so khop voi ket qua THAT.

CAI THIEN so voi ban truoc:
1. Truoc day CHI doi chieu duoc chien luoc "base" (predict_next_draw.py)
   vi day la chien luoc DUY NHAT ghi lich su - 3 chien luoc con lai (ml/
   ai/ai2) khong bao gio duoc kiem chung. Gio TU DONG doi chieu MOI chien
   luoc dang co file lich su cho ky nay (khong hard-code danh sach, dung
   lotto_common.known_strategies() de tu phat hien).
2. Truoc day chi cham DUNG/SAI tuyet doi (trung ca 5 so + dac biet - xac
   suat ~1/324632 moi ve, co the cho HANG NAM van chua co 1 lan). Gio
   THEM cham diem trung TUNG PHAN (0-5 so + co/khong trung dac biet,
   xem lotto_common.score_ticket) va TICH LUY vao
   predict/strategy_stats.json - cho phep so sanh 4 chien luoc CO Y NGHIA
   THONG KE chi sau vai chuc ky, thay vi phai cho trung tuyet doi.
3. So sanh voi MOC NGAU NHIEN (EXPECTED_RANDOM_MATCHES ~ 0.714 so/ve) de
   biet chien luoc nao (neu co) dang lam TOT HON boc so hoan toan ngau
   nhien - hay chi dang dao dong quanh muc ngau nhien (binh thuong, vi
   xo so la ngau nhien that su).

Model nao doan DUNG TUYET DOI (trung ca 5 so chinh + so dac biet) van
duoc luu vao thu muc j1_535/ nhu truoc (khong doi hanh vi nay).

Neu ky nay KHONG co file lich su nao (chua tung du doan cho ky nay) thi
bo qua, khong bao loi.

ENV:
    CSV_PATH      - file CSV cac ky quay (mac dinh data/all.csv)
    DRAW_ID       - ky can doi chieu (bat buoc, vi du "00867")
    HISTORY_DIR   - thu muc luu lich su du doan (mac dinh predict/history)
    OUT_DIR       - thu muc luu ket qua doan DUNG tuyet doi (mac dinh j1_535)
    STATS_PATH    - file JSON thong ke tich luy theo chien luoc
                    (mac dinh predict/strategy_stats.json)
    KEEP_LAST_N_HISTORY_DRAWS - so ky GAN NHAT giu lai file lich su tho
                    trong predict/history/, cac ky cu hon se bi XOA sau
                    khi da cong don vao strategy_stats.json (mac dinh 60,
                    ~1 thang o lich 2 ky/ngay). Dat -1 de tat (giu mai
                    mai nhu truoc). Chan predict/history phinh to vo han
                    khi so chien luoc (base/ml/ai/ai2/ai3/...) tang dan.
"""

import json
import os
from pathlib import Path

from lotto_common import (
    get_actual_result,
    load_prediction_history,
    known_strategies,
    prune_old_history,
    score_ticket,
    EXPECTED_RANDOM_MATCHES,
    EXPECTED_RANDOM_SPECIAL_HIT_RATE,
)


def load_stats(stats_path):
    p = Path(stats_path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def empty_strategy_stats():
    return {
        "checked_draws": 0,       # so KY da doi chieu (co the >1 model/ky)
        "tickets_checked": 0,     # so VE (model) da doi chieu (>= checked_draws)
        "matches_hist": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "special_hits": 0,
        "j1_hits": 0,
        "sum_matches": 0,
    }


def update_strategy_stats(stats, strategy, entries_scored):
    s = stats.setdefault(strategy, empty_strategy_stats())
    s["checked_draws"] += 1
    for sc in entries_scored:
        s["tickets_checked"] += 1
        s["matches_hist"][str(sc["matches"])] += 1
        s["sum_matches"] += sc["matches"]
        if sc["special_hit"]:
            s["special_hits"] += 1
        if sc["is_j1"]:
            s["j1_hits"] += 1


def print_stats_summary(stats):
    print("\n=== THONG KE TICH LUY THEO CHIEN LUOC (so voi moc ngau nhien) ===")
    print(f"Moc ngau nhien tham chieu: trung binh {EXPECTED_RANDOM_MATCHES:.3f} so/5 "
          f"so chinh, ty le trung dac biet {EXPECTED_RANDOM_SPECIAL_HIT_RATE:.3f}")
    for strategy, s in sorted(stats.items()):
        n = s["tickets_checked"]
        if n == 0:
            continue
        avg = s["sum_matches"] / n
        sp_rate = s["special_hits"] / n
        print(f"  [{strategy}] {n} ve da doi chieu (qua {s['checked_draws']} ky) - "
              f"trung binh {avg:.3f} so/ve (moc ngau nhien {EXPECTED_RANDOM_MATCHES:.3f}), "
              f"ty le trung dac biet {sp_rate:.3f} (moc {EXPECTED_RANDOM_SPECIAL_HIT_RATE:.3f}), "
              f"J1 tuyet doi: {s['j1_hits']}")


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    draw_id_str = os.environ.get("DRAW_ID", "")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    out_dir = os.environ.get("OUT_DIR", "j1_535")
    stats_path = os.environ.get("STATS_PATH", "predict/strategy_stats.json")
    keep_last_n = int(os.environ.get("KEEP_LAST_N_HISTORY_DRAWS", "60"))

    if not draw_id_str:
        print("Thieu DRAW_ID, bo qua.")
        print("MATCHED_COUNT=0")
        return

    draw_id = int(draw_id_str)
    strategies = known_strategies(history_dir, draw_id)
    if not strategies:
        print(f"Khong co lich su du doan nao cho ky {draw_id_str} trong {history_dir}, bo qua.")
        print("MATCHED_COUNT=0")
        return

    actual = get_actual_result(csv_path, draw_id_str)
    if actual is None:
        print(f"Khong tim thay ket qua thuc te cho ky {draw_id_str} trong {csv_path}, bo qua.")
        print("MATCHED_COUNT=0")
        return

    actual_numbers, actual_special, draw_date = actual
    print(f"Ky {draw_id_str} ({draw_date}): thuc te = "
          f"{sorted(actual_numbers)} + DB {actual_special}")
    print(f"Chien luoc co lich su cho ky nay: {strategies}")

    stats = load_stats(stats_path)
    all_matched = []  # (strategy, entry) - dung DUNG TUYET DOI, cho j1_535/

    for strategy in strategies:
        entries, hpath = load_prediction_history(history_dir, draw_id, strategy)
        if not entries:
            continue
        scored = []
        for e in entries:
            sc = score_ticket(e["numbers"], e["special"], actual_numbers, actual_special)
            scored.append(sc)
            status = "DUNG J1" if sc["is_j1"] else f"{sc['matches']}/5 so" + (" + DB" if sc["special_hit"] else "")
            print(f"  [{strategy}] seed={e['seed']} (model seed_start={e['seed_start']}) -> "
                  f"{sorted(e['numbers'])} + DB {e['special']} -> {status}")
            if sc["is_j1"]:
                all_matched.append((strategy, e))
        update_strategy_stats(stats, strategy, scored)

    os.makedirs(os.path.dirname(stats_path) or ".", exist_ok=True)
    Path(stats_path).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print_stats_summary(stats)

    # Ky nay da duoc cong don vao strategy_stats.json o tren - tu day
    # tro di du lieu tho tung ky (predict/history/) khong con can giu
    # mai, chi giu 1 cua so gan day de debug. Xoa cac ky qua cu de
    # predict/history khong phinh to vo han khi so chien luoc tang dan.
    removed = prune_old_history(history_dir, draw_id, keep_last_n)
    if removed:
        print(f"Da xoa {removed} file lich su cu (qua {keep_last_n} ky gan nhat) trong {history_dir}")

    if all_matched:
        os.makedirs(out_dir, exist_ok=True)
        out_path = Path(out_dir) / f"{draw_id_str}.txt"
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"KY {draw_id_str} ({draw_date}) - DU DOAN DUNG (trung J1)\n")
            f.write(f"Ket qua thuc te: {sorted(actual_numbers)} + DAC BIET {actual_special}\n\n")
            for strategy, e in all_matched:
                f.write(f"chien luoc: {strategy}\n")
                f.write(f"seed: {e['seed']}\n")
                f.write(f"model seed_start: {e['seed_start']}\n")
                f.write(f"nguon file L1: {e['source_file']}\n\n")
        print(f"Da luu {len(all_matched)} du doan DUNG vao {out_path}")

        # File JSON gon nhe di kem, dung de dinh kem vao tin nhan FCM (xem
        # send_fcm_push.py --event-type j1_prediction_hit --event-json ...)
        json_path = Path(out_dir) / f"{draw_id_str}.json"
        json_path.write_text(
            json.dumps({
                "draw_id": draw_id_str,
                "draw_date": draw_date,
                "numbers": sorted(actual_numbers),
                "special": actual_special,
                "matched_models": [
                    {"strategy": strategy, "seed": e["seed"], "seed_start": e["seed_start"]}
                    for strategy, e in all_matched
                ],
            }, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    else:
        print("Khong co model nao doan dung tuyet doi ky nay (xem thong ke trung tung phan o tren).")

    print(f"MATCHED_COUNT={len(all_matched)}")


if __name__ == "__main__":
    main()
