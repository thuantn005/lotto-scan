#!/usr/bin/env python3
"""
predict_next_draw_random.py - Du doan ky KE TIEP bang cach BOC NGAU NHIEN
THAT SU (khong dua vao seed/L1/lich su gi ca) - day la chien luoc DOI
CHUNG (control group) cho toan bo du an: neu cac chien luoc dua vao seed
(base/ml/ai/ai2/ai3) khong thang duoc chien luoc nay 1 cach co y nghia
thong ke qua nhieu ky, chung khong hon gi ngau nhien thuan tuy.

KHONG dung L1/L2, KHONG dung CSV lich su (tru de xac dinh next_draw_id),
KHONG goi API AI nao - chi random.SystemRandom() (nguon ngau nhien he
dieu hanh, khong seed co dinh, khong the doan truoc/tai lap).

Ghi ra file RIENG: predict/next_draw_predict_random.txt. Chien luoc nay
duoc danh dau la "random" trong lich su du doan
(predict/history/{draw_id}_random.txt), doc lap voi base/ml/ai/ai2/ai3.

ENV:
    CSV_PATH     - file CSV cac ky quay, chi de lay next_draw_id (mac dinh data/all.csv)
    OUT_PATH     - file .txt ket qua rieng (mac dinh predict/next_draw_predict_random.txt)
    HISTORY_DIR  - thu muc luu lich su du doan (mac dinh predict/history)
    NUM_PICKS    - so ve ngau nhien sinh ra cho ky nay (mac dinh 15, cung
                   so luong voi CANDIDATES_PER_MODEL cua cac chien luoc khac
                   de so sanh cong bang)
"""

import os
import random

from lotto_common import (
    get_next_draw_id,
    save_prediction_history,
)

STRATEGY = "random"


def random_ticket(rng: random.Random):
    """1 ve boc ngau nhien THAT SU: 5 so chinh phan biet tu 1-35 + 1 so
    dac biet tu 1-12, KHONG lien quan gi den seed/cong thuc sinh ve cua
    cac chien luoc khac."""
    numbers = sorted(rng.sample(range(1, 36), 5))
    special = rng.randint(1, 12)
    return numbers, special


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_random.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    num_picks = int(os.environ.get("NUM_PICKS", "15"))

    next_draw_id = get_next_draw_id(csv_path)
    print(f"[Random] Ky ke tiep can du doan: {next_draw_id:05d}")

    # random.SystemRandom() lay entropy tu he dieu hanh (os.urandom),
    # KHONG seed co dinh - moi lan chay ra ket qua khac nhau, khong the
    # tai lap/du doan truoc, dung 100% voi tinh chat "doi chung ngau
    # nhien" cua chien luoc nay.
    rng = random.SystemRandom()

    predictions = []
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN RANDOM (doi chung ngau nhien,\n"
                f"doc lap hoan toan voi cac chien luoc dua vao seed: base/ml/ai/ai2/ai3)\n")
        f.write("Luu y: day la BOC SO NGAU NHIEN THAT SU (random.SystemRandom), KHONG\n"
                "dua vao seed/L1/lich su gi ca - dung de LAM MOC SO SANH thong ke, so\n"
                "xem cac chien luoc kia co thuc su hon ngau nhien hay khong.\n\n")

        for i in range(num_picks):
            numbers, special = random_ticket(rng)
            nums_str = "-".join(f"{n:02d}" for n in numbers)
            f.write(f"  ve #{i + 1}: {nums_str} + DAC BIET {special}\n")
            predictions.append({
                "seed_start": "random",
                "seed": i,
                "numbers": numbers,
                "special": special,
                "file": "random",
            })

    hpath = save_prediction_history(history_dir, next_draw_id, STRATEGY, predictions)

    print(f"[Random] Da ghi {num_picks} ve ngau nhien vao {out_path}")
    print(f"[Random] Da luu lich su du doan ({STRATEGY}) vao {hpath}")
    print(f"NEXT_DRAW_ID={next_draw_id}")


if __name__ == "__main__":
    main()
