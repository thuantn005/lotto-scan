#!/usr/bin/env python3
"""
ml_scoring.py - Train 1 model Logistic Regression NHO (thong ke tan suat co
trong so thoi gian) tren LICH SU KET QUA THAT (data/all.csv, KHONG lien
quan gi den seed), de cham diem xac suat tung so (1-35) va so dac biet
(1-12) se xuat hien o ky KE TIEP.

Diem so nay dung de predict_next_draw.py CHON trong so cac seed dang co
trong L1 cua tung model, seed nao co ve du doan (5 so + dac biet) tong
diem ML CAO NHAT - thay vi chi chon theo "so lan tung trung" nhu truoc.

Luu y: day la mo hinh thong ke DON GIAN cho muc dich nghien cuu/thu
nghiem - xo so la ngau nhien that su nen KHONG co gia tri du doan chinh
xac, chi la 1 lop uu tien bo sung khi co nhieu seed L1 ngang nhau.

Dac trung (feature) cho MOI so (dung chung cho ca 35 so chinh va 12 so
dac biet, huan luyen 2 model rieng):
    - freq_all: tan suat xuat hien tinh tren toan bo lich su
    - freq_last20 / freq_last50: tan suat trong 20 / 50 ky gan nhat
    - gap: so ky da qua ke tu lan xuat hien gan nhat (cang lau cang "dang
      cho" theo logic thong ke tan suat co dien)

ENV:
    CSV_PATH  - file CSV cac ky quay (mac dinh data/all.csv)
    OUT_PATH  - file JSON diem so (mac dinh predict/ml_scores.json)
"""

import csv
import json
import os
import re
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression


def load_draws(csv_path):
    """Tra ve list [(draw_id:int, numbers:set[int], special:int)], sap xep tang dan."""
    draws = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 5:
                continue
            try:
                draw_id = int(row[1])
            except ValueError:
                continue
            result_json = row[4]
            nums_match = re.search(r'"numbers"\s*:\s*\[([^\]]*)\]', result_json)
            sp_match = re.search(r'"special_numbers"\s*:\s*\[([^\]]*)\]', result_json)
            if not nums_match or not sp_match:
                continue
            numbers = frozenset(int(x) for x in nums_match.group(1).split(",") if x.strip() != "")
            specials = [int(x) for x in sp_match.group(1).split(",") if x.strip() != ""]
            if len(numbers) != 5 or not specials:
                continue
            draws.append((draw_id, numbers, specials[0]))
    draws.sort(key=lambda d: d[0])
    return draws


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    out_path = os.environ.get("OUT_PATH", "predict/ml_scores.json")

    draws = load_draws(csv_path)
    print(f"Da doc {len(draws)} ky tu {csv_path}")

    # Train rieng 2 model: 1 cho 35 so chinh, 1 cho 12 so dac biet.
    number_scores = train_number_scores(draws)
    special_scores = train_special_scores(draws)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "number_scores": {str(k): v for k, v in number_scores.items()},
            "special_scores": {str(k): v for k, v in special_scores.items()},
            "total_draws_used": len(draws),
        }, f, ensure_ascii=False, indent=2)

    print(f"Da ghi diem so ML vao {out_path}")
    top5 = sorted(number_scores.items(), key=lambda kv: -kv[1])[:5]
    print(f"Top 5 so (theo diem ML): {top5}")
    top_sp = sorted(special_scores.items(), key=lambda kv: -kv[1])[:1]
    print(f"So dac biet cao diem nhat: {top_sp}")


def _build(draws, value_range, present_fn):
    n = len(draws)
    warmup = min(50, n // 3) if n > 10 else 0
    count_all = {v: 0 for v in value_range}
    last_seen_idx = {v: -1 for v in value_range}
    window20, window50 = [], []
    X, y = [], []

    for i, draw in enumerate(draws):
        present = present_fn(draw)
        if i >= warmup:
            for v in value_range:
                freq_all = count_all[v] / i if i > 0 else 0.0
                f20 = sum(1 for (_, p) in window20 if v in p) / len(window20) if window20 else 0.0
                f50 = sum(1 for (_, p) in window50 if v in p) / len(window50) if window50 else 0.0
                gap = (i - last_seen_idx[v]) if last_seen_idx[v] >= 0 else i
                X.append([freq_all, f20, f50, gap])
                y.append(1 if v in present else 0)
        for v in present:
            count_all[v] += 1
            last_seen_idx[v] = i
        window20.append((i, present))
        window50.append((i, present))
        if len(window20) > 20:
            window20.pop(0)
        if len(window50) > 50:
            window50.pop(0)

    current_features = {}
    n_total = len(draws)
    for v in value_range:
        freq_all = count_all[v] / n_total if n_total > 0 else 0.0
        f20 = sum(1 for (_, p) in window20 if v in p) / len(window20) if window20 else 0.0
        f50 = sum(1 for (_, p) in window50 if v in p) / len(window50) if window50 else 0.0
        gap = (n_total - last_seen_idx[v]) if last_seen_idx[v] >= 0 else n_total
        current_features[v] = [freq_all, f20, f50, gap]

    return np.array(X, dtype=float), np.array(y, dtype=int), current_features


def _train(X, y, value_range, current_features):
    if len(X) < 20 or len(set(y.tolist())) < 2:
        return {v: 1.0 for v in value_range}
    model = LogisticRegression(max_iter=500, class_weight="balanced")
    model.fit(X, y)
    scores = {}
    for v in value_range:
        feat = np.array(current_features[v], dtype=float).reshape(1, -1)
        scores[v] = float(model.predict_proba(feat)[0][1])
    return scores


def train_number_scores(draws):
    value_range = list(range(1, 36))
    X, y, cur = _build(draws, value_range, lambda d: d[1])  # d = (draw_id, numbers, special)
    return _train(X, y, value_range, cur)


def train_special_scores(draws):
    value_range = list(range(1, 13))
    X, y, cur = _build(draws, value_range, lambda d: {d[2]})
    return _train(X, y, value_range, cur)


if __name__ == "__main__":
    main()
