#!/usr/bin/env python3
"""
check_prediction_result.py - Khi 1 ky MOI duoc xac nhan, doc lai file du
doan da luu TU TRUOC (predict/history/{draw_id}.txt - duoc ghi boi
predict_next_draw.py o LAN CHAY TRUOC, luc do ky nay chua co ket qua) va
so khop voi ket qua THAT cua ky do. Model nao doan DUNG (trung ca 5 so
chinh + so dac biet) thi luu vao thu muc j1_535/.

Neu ky nay KHONG co file lich su tuong ung (vi du lan dau chay, chua tung
du doan cho ky nay) thi bo qua, khong bao loi.

ENV:
    CSV_PATH    - file CSV cac ky quay (mac dinh data/all.csv)
    DRAW_ID     - ky can doi chieu (bat buoc, vi du "00867")
    HISTORY_DIR - thu muc luu lich su du doan (mac dinh predict/history)
    OUT_DIR     - thu muc luu ket qua doan DUNG (mac dinh j1_535)
"""

import csv
import json
import os
import re
from pathlib import Path


def get_actual_result(csv_path, draw_id_str):
    """Tra ve (set 5 so chinh, so dac biet, ngay quay) cua draw_id, hoac None."""
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 5:
                continue
            if row[1] != draw_id_str:
                continue
            draw_date = row[2] if len(row) > 2 else ""
            result_json = row[4]
            nums_match = re.search(r'"numbers"\s*:\s*\[([^\]]*)\]', result_json)
            sp_match = re.search(r'"special_numbers"\s*:\s*\[([^\]]*)\]', result_json)
            if not nums_match or not sp_match:
                continue
            numbers = frozenset(int(x) for x in nums_match.group(1).split(",") if x.strip() != "")
            specials = [int(x) for x in sp_match.group(1).split(",") if x.strip() != ""]
            if len(numbers) != 5 or not specials:
                continue
            return numbers, specials[0], draw_date
    return None


def load_history(history_dir, draw_id_str):
    """Doc file predict/history/{draw_id}.txt (dinh dang ghi boi
    predict_next_draw.py): seed_start|seed|weight|n1,n2,n3,n4,n5|special|file"""
    path = Path(history_dir) / f"{draw_id_str}.txt"
    if not path.exists():
        return None, path
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != 6:
            continue
        seed_start, seed, weight, nums_str, special, src_file = parts
        numbers = frozenset(int(x) for x in nums_str.split(","))
        entries.append({
            "seed_start": seed_start,
            "seed": seed,
            "weight": weight,
            "numbers": numbers,
            "special": int(special),
            "source_file": src_file,
        })
    return entries, path


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    draw_id_str = os.environ.get("DRAW_ID", "")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    out_dir = os.environ.get("OUT_DIR", "j1_535")

    if not draw_id_str:
        print("Thieu DRAW_ID, bo qua.")
        print("MATCHED_COUNT=0")
        return

    entries, history_path = load_history(history_dir, draw_id_str)
    if entries is None:
        print(f"Khong co lich su du doan cho ky {draw_id_str} ({history_path}), bo qua.")
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

    matched = []
    for e in entries:
        is_match = (e["numbers"] == actual_numbers) and (e["special"] == actual_special)
        status = "DUNG" if is_match else "sai"
        print(f"  seed={e['seed']} (model seed_start={e['seed_start']}) -> "
              f"{sorted(e['numbers'])} + DB {e['special']} -> {status}")
        if is_match:
            matched.append(e)

    if matched:
        os.makedirs(out_dir, exist_ok=True)
        out_path = Path(out_dir) / f"{draw_id_str}.txt"
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"KY {draw_id_str} ({draw_date}) - DU DOAN DUNG (trung J1)\n")
            f.write(f"Ket qua thuc te: {sorted(actual_numbers)} + DAC BIET {actual_special}\n\n")
            for e in matched:
                f.write(f"seed: {e['seed']}\n")
                f.write(f"model seed_start: {e['seed_start']}\n")
                f.write(f"so lan tung trung truoc do (trong L1): {e['weight']}\n")
                f.write(f"nguon file L1: {e['source_file']}\n\n")
        print(f"Da luu {len(matched)} du doan DUNG vao {out_path}")

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
                    {"seed": e["seed"], "seed_start": e["seed_start"], "weight": e["weight"]}
                    for e in matched
                ],
            }, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    else:
        print("Khong co model nao doan dung ky nay.")

    print(f"MATCHED_COUNT={len(matched)}")


if __name__ == "__main__":
    main()
