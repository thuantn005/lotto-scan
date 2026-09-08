#!/usr/bin/env python3
"""
lotto_common.py - Thu vien DUNG CHUNG cho ca 4 script du doan ky ke tiep
(predict_next_draw.py, predict_next_draw_ml.py, predict_next_draw_ai.py,
predict_next_draw_ai2.py). Truoc day moi script tu copy-paste y het cung
1 bo ham (build_binom/build_rank_to_mask/mix64/predict_ticket/
get_next_draw_id) - gop lai day de sua 1 cho la ap dung cho ca 4, tranh
lech thuat toan giua cac phien ban theo thoi gian.

Cong thuc sinh ve (giu NGUYEN 100% tu scan_per_draw.cpp):
    combined = seed*M1 + draw_id*M2   (mod 2^64)
    mixed    = mix64(combined)
    rank     = mixed mod C(35,5)
    mask     = unrank_colex(rank)      -> 5 so chinh
    mixed2   = mix64(mixed)
    special  = mixed2 mod 12 + 1

Ngoai ra file nay con them 2 phan MOI (cai thien chuc nang du doan):

1. save_prediction_history() / load_prediction_history() - truoc day CHI
   predict_next_draw.py (chien luoc "weight") ghi lich su vao
   predict/history/{draw_id}.txt, nen check_prediction_result.py CHI kiem
   chung duoc 1/4 chien luoc - 3 ban con lai (ML, AI/Gemini, AI2/Groq)
   khong bao gio duoc doi chieu voi ket qua that. Gio moi chien luoc ghi
   RIENG 1 file predict/history/{draw_id}_{strategy}.txt (strategy la
   "base"/"ml"/"ai"/"ai2"), khong con doi nhau.

2. score_ticket() - so trung TUNG PHAN (0-5 so chinh + co/khong trung dac
   biet) thay vi chi nhi phan DUNG/SAI (tron ca 5 so + dac biet la qua
   hiem, phai cho hang nam moi co du du lieu so sanh). Diem trung tung
   phan cho phep tich luy thong ke co y nghia sau vai chuc ky, thay vi
   phai cho 1 lan trung tuyet doi ca 5+1 (xac suat ~1/324632 moi ve).
"""

import csv
import json
import os
import math
import re
from pathlib import Path

M1 = 0x9E3779B97F4A7C15
M2 = 0xD1B54A32D192ED03
M3 = 0xBF58476D1CE4E5B9
M4 = 0x94D049BB133111EB
MASK64 = 0xFFFFFFFFFFFFFFFF
C = 324632  # C(35,5)
SPECIAL_COUNT = 12
COMBOS_TOTAL = C * SPECIAL_COUNT  # 3,895,584 - tong so ve co the (5 so + dac biet)
MATCH_PROB = 1 / COMBOS_TOTAL  # xac suat 1 seed BAT KY trung DUNG 1 ky CU THE, thuan tuy ngau nhien

# Ky vong so trung TRUNG BINH cua 1 ve 5-so-chon-tu-35 BOC NGAU NHIEN (khong
# lien quan gi den seed) so voi ket qua that: E[matches] = 5 * 5/35.
# Dung lam MOC SO SANH ("neu chien luoc nay khong hon duoc con so nay 1
# cach co y nghia thong ke, no khong hon xac suat ngau nhien").
EXPECTED_RANDOM_MATCHES = 5 * (5 / 35)  # = 5/7 ~= 0.7143
EXPECTED_RANDOM_SPECIAL_HIT_RATE = 1 / 12  # ~= 0.0833


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
        next(f, None)  # header
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


def load_recent_draws_summary(csv_path, last_k=15):
    """Tra ve list [(draw_id, [5 so], dac biet)] cua last_k ky GAN NHAT,
    dung lam ngu canh cho AI (khong dung de tinh toan chinh xac gi)."""
    rows = []
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
            numbers = sorted(int(x) for x in nums_match.group(1).split(",") if x.strip() != "")
            specials = [int(x) for x in sp_match.group(1).split(",") if x.strip() != ""]
            if len(numbers) != 5 or not specials:
                continue
            rows.append((draw_id, numbers, specials[0]))
    rows.sort(key=lambda r: r[0])
    return rows[-last_k:]


def get_actual_result(csv_path, draw_id_str):
    """Tra ve (frozenset 5 so chinh, so dac biet, ngay quay) cua draw_id,
    hoac None neu chua co / khong parse duoc."""
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 5 or row[1] != draw_id_str:
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


def load_all_actual_results(csv_path):
    """Doc TOAN BO CSV 1 LAN, tra ve dict {draw_id:int -> (frozenset so
    chinh, dac biet, ngay)}. Dung cho backtest (quet hang tram ky) thay vi
    goi get_actual_result() (quet lai tu dau file) cho tung ky rieng le -
    nhanh hon rat nhieu khi can tra cuu nhieu ky."""
    out = {}
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
            out[draw_id] = (numbers, specials[0], draw_date)
    return out


# ---------------------------------------------------------------------
# Lich su du doan theo tung CHIEN LUOC (base/ml/ai/ai2) - moi chien luoc
# 1 file rieng, KHONG con doi ghi len nhau nhu truoc.
# ---------------------------------------------------------------------

def history_path(history_dir, draw_id, strategy):
    return Path(history_dir) / f"{draw_id:05d}_{strategy}.txt"


def save_prediction_history(history_dir, draw_id, strategy, predictions):
    """predictions: list cac dict co it nhat cac key
    seed_start, seed, numbers (list int), special (int), file (ten file L1
    nguon). Ghi 1 dong/model, dinh dang:
        seed_start|seed|n1,n2,n3,n4,n5|special|file
    """
    os.makedirs(history_dir, exist_ok=True)
    path = history_path(history_dir, draw_id, strategy)
    with path.open("w", encoding="utf-8") as f:
        for info in predictions:
            nums_str = ",".join(str(n) for n in info["numbers"])
            f.write(
                f"{info.get('seed_start')}|{info.get('seed')}|"
                f"{nums_str}|{info['special']}|{info.get('file', '')}\n"
            )
    return path


def load_prediction_history(history_dir, draw_id, strategy):
    path = history_path(history_dir, draw_id, strategy)
    if not path.exists():
        return None, path
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            continue
        seed_start, seed, nums_str, special, src_file = parts
        entries.append({
            "seed_start": seed_start,
            "seed": seed,
            "numbers": frozenset(int(x) for x in nums_str.split(",")),
            "special": int(special),
            "source_file": src_file,
        })
    return entries, path


def known_strategies(history_dir, draw_id):
    """Liet ke cac chien luoc DA CO file lich su cho ky nay (glob theo
    ten file thay vi hard-code danh sach, de sau nay them chien luoc moi
    khong can sua check_prediction_result.py)."""
    prefix = f"{draw_id:05d}_"
    d = Path(history_dir)
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob(f"{prefix}*.txt")):
        out.append(p.stem[len(prefix):])
    return out


# ---------------------------------------------------------------------
# Cham diem trung TUNG PHAN - xem docstring dau file.
# ---------------------------------------------------------------------

def score_ticket(predicted_numbers, predicted_special, actual_numbers, actual_special):
    """Tra ve dict {matches: 0..5, special_hit: bool, is_j1: bool}."""
    matches = len(set(predicted_numbers) & set(actual_numbers))
    special_hit = (predicted_special == actual_special)
    return {
        "matches": matches,
        "special_hit": special_hit,
        "is_j1": (matches == 5 and special_hit),
    }


# ---------------------------------------------------------------------
# Nguong thang hang L1 -> L2 theo THONG KE (thay cho nguong co dinh
# "weight >= 2" ap dung cho MOI model nhu truoc).
#
# VAN DE cua nguong co dinh: xac suat 1 seed BAT KY trung DUNG 1 ky cu the
# la p = 1/COMBOS_TOTAL, GIONG NHAU cho moi model (khong phu thuoc
# seed_count). Nhung SO LUONG seed duoc thu (seed_count) va SO KY duoc
# kiem tra (num_draws) khac nhau RAT NHIEU giua cac model:
#   - Model chinh (682305800400): ~1.56 ty seed x 872 ky
#   - Cac model phu (ONCE/ONCE2/ONCE3): ~31.15 ty seed x 10-20 ky
# => Ky vong so luong seed TINH CO dat duoc weight>=2 THUAN TUY NGAU NHIEN
# (khong co gia tri gi) la RAT KHAC NHAU giua cac model (xem
# expected_false_positive_count). Voi model chinh (nhieu ky), nguong
# weight>=2 hau nhu chac chan co hang chuc seed "thang hang" chi vi trung
# hop ngau nhien (birthday paradox), trong khi voi model phu (it ky) thi
# weight>=2 lai la 1 su kien hiem, co y nghia hon nhieu - CUNG 1 nguong
# nhung do "hiem" hoan toan khac nhau => khong nen dung 1 con so co dinh
# cho tat ca.
#
# Giai phap: voi MOI model, tinh nguong weight NHO NHAT sao cho SO LUONG
# seed du kien dat duoc nguong do THUAN TUY NGAU NHIEN (khong lien quan
# gi den ket qua that) nam DUOI 1 "ngan sach sai so" (budget) cho truoc -
# vi du budget=0.05 nghia la ky vong <1/20 kha nang co BAT KY seed nao
# trong toan bo dai dat nguong do chi vi trung hop ngau nhien.
# ---------------------------------------------------------------------

def expected_false_positive_count(seed_count, num_draws, weight, p=MATCH_PROB):
    """So luong seed KY VONG (tren toan bo seed_count seed) dat duoc DUNG
    'weight' lan trung (trong so num_draws ky) THUAN TUY NGAU NHIEN -
    xap xi Poisson/nhi thuc: seed_count * C(num_draws, weight) * p^weight
    (bo qua thua so (1-p)^(num_draws-weight) vi p cuc nho, sai so khong
    dang ke). Cang lon nghia la nguong do CANG DE bi trung ngau nhien
    (cang KHONG dang tin cay)."""
    if weight > num_draws:
        return 0.0
    return seed_count * math.comb(num_draws, weight) * (p ** weight)


def choose_promotion_threshold(seed_count, num_draws, budget=0.05, min_weight=2, max_weight=10):
    """Tra ve (threshold, expected_at_threshold): weight NHO NHAT (>=
    min_weight) sao cho expected_false_positive_count(...) <= budget. Neu
    khong tim duoc trong [min_weight, max_weight] (model qua nho/qua it
    ky de dat do tin cay mong muon), tra ve max_weight (an toan nhat co
    the, van co the > budget - caller nen kiem tra lai gia tri tra ve)."""
    for w in range(min_weight, max_weight + 1):
        exp = expected_false_positive_count(seed_count, num_draws, w)
        if exp <= budget:
            return w, exp
    return max_weight, expected_false_positive_count(seed_count, num_draws, max_weight)


