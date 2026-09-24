#!/usr/bin/env python3
"""
lotto_common.py - Thu vien DUNG CHUNG cho cac script du doan ky ke tiep
(predict_next_draw.py, predict_next_draw_app.py). Truoc day moi script tu
copy-paste y het cung 1 bo ham (build_binom/build_rank_to_mask/mix64/
predict_ticket/get_next_draw_id) - gop lai day de sua 1 cho la ap dung
cho tat ca, tranh lech thuat toan giua cac phien ban theo thoi gian.

(2026-09: da bo chien luoc "ml" (predict_next_draw_ml.py/ml_scoring.py)
khoi pipeline - xem README_THAY_DOI.txt. known_strategies() ben duoi tu
dong glob theo file lich su hien co nen khong can sua gi them o day.)

(2026-09: da bo LUON chien luoc "ai"/"ai2" (Gemini/Groq) - predict_next_
draw_ai.py, predict_next_draw_ai2.py, predict_next_draw_ai3.py (chua bao
gio duoc gan vao workflow) DA XOA, kem 2 ham chi phuc vu rieng chung
(collect_ai_candidates_per_model()/build_ai_prompt()) cung DA XOA khoi
file nay vi khong con noi nao goi. Pipeline predict gio CHI con 2 chien
luoc: "base" (predict_next_draw.py) va "app" (predict_next_draw_app.py,
mo phong co che sinh so cua app Flutter) - khong con phu thuoc API key
ngoai (GEMINI_API_KEY/GROQ_API_KEY) nao nua. Xem README_THAY_DOI.txt.)

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

import bisect
import csv
import glob
import json
import os
import math
import random
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
# Lich su du doan theo tung CHIEN LUOC (base/ai/ai2/app) - moi chien luoc
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
            line = (
                f"{info.get('seed_start')}|{info.get('seed')}|"
                f"{nums_str}|{info['special']}|{info.get('file', '')}"
            )
            # TUY CHON (chi chien luoc "consensus" ghi): 2 truong them o cuoi
            #   level      = so seed DOC LAP thuc te cung sinh ra ve nay (muc dong thuan)
            #   seeds_detail = list (seed, [ky_trung,...]) - moi seed dong thuan + cac ky no tung trung
            # File cu (5 truong) van doc duoc binh thuong.
            if info.get("level") is not None:
                detail = ";".join(
                    f"{s}@{'+'.join(str(k) for k in kys)}"
                    for s, kys in (info.get("seeds_detail") or [])
                )
                line += f"|{info['level']}|{detail}"
            f.write(line + "\n")
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
        if len(parts) not in (5, 7):  # 5 = dinh dang cu; 7 = them level + seeds_detail (consensus)
            continue
        seed_start, seed, nums_str, special, src_file = parts[:5]
        entry = {
            "seed_start": seed_start,
            "seed": seed,
            "numbers": frozenset(int(x) for x in nums_str.split(",")),
            "special": int(special),
            "source_file": src_file,
        }
        if len(parts) == 7:
            try:
                entry["level"] = int(parts[5])
            except ValueError:
                entry["level"] = None
            seeds = []
            for item in parts[6].split(";"):
                if not item:
                    continue
                sd, _, kys = item.partition("@")
                seeds.append({"seed": sd, "draws": [k for k in kys.split("+") if k]})
            entry["seeds"] = seeds
        entries.append(entry)
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


def prune_old_history(history_dir, current_draw_id, keep_last_n):
    """Xoa cac file predict/history/{draw_id}_{strategy}.txt cua nhung ky
    DA CU (draw_id <= current_draw_id - keep_last_n). Goi ham nay SAU KHI
    check_prediction_result.py da doi chieu + cong don ket qua ky
    current_draw_id vao predict/strategy_stats.json - tu luc do du lieu
    tho tung ky khong con can giu mai (da nam trong so tich luy), chi giu
    lai 1 cua so gan day de tien debug/doi chieu thu cong. Cang nhieu
    chien luoc (base/ml/ai/ai2/ai3/...) thi so file/ky cang nhieu, nen
    can chan de predict/history khong phinh to vo han theo thoi gian.

    Tra ve so file da xoa.
    """
    d = Path(history_dir)
    if not d.exists() or keep_last_n < 0:
        return 0
    cutoff = current_draw_id - keep_last_n
    if cutoff < 0:
        return 0
    removed = 0
    for p in d.glob("*_*.txt"):
        m = re.match(r"^(\d+)_", p.name)
        if not m:
            continue
        file_draw_id = int(m.group(1))
        if file_draw_id <= cutoff:
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
    return removed


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


# ---------------------------------------------------------------------
# Khoi phuc lai cho predict_next_draw_ai.py / ai2.py / ai3.py (goi Gemini/
# Groq/OpenRouter) - 2 ham nay TRUOC DAY bi xoa (xem docstring dau file)
# vi 3 chien luoc AI chua bao gio duoc gan vao workflow, nhung ban than
# file *_ai*.py van con nguyen va van import 2 ham nay, nen phai co lai
# thi 3 script do moi chay duoc.
# ---------------------------------------------------------------------

def get_gaps_from_l2_file(l2_path):
    """Doc 1 file l2_merged, tra ve list SO NGUYEN cac khoang cach (so ky)
    GIUA 2 LAN TRUNG LIEN TIEP cua tung seed da thang hang trong file do.
    Tra ve [] neu file khong ton tai/rong/loi. (Chuyen tu
    predict_next_draw_app.py vao day de collect_density_candidates_per_model
    dung chung duoc.)"""
    l2_path = Path(l2_path)
    if not l2_path.exists():
        return []
    try:
        data = json.loads(l2_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Bo qua {l2_path}: {e}")
        return []

    gaps = []
    for p in data.get("promoted", []):
        hits = sorted(h["draw_id"] for h in (p.get("hits") or []))
        for a, b in zip(hits, hits[1:]):
            if b > a:
                gaps.append(b - a)
    return gaps


def get_gaps_from_l2_dir(l2_dir):
    """Gop gap tu MOI file l2_merged/*.json lai - dung lam mau du phong
    (mat do TOAN CUC) cho model nao chua co/chua du L2 rieng."""
    gaps = []
    for fp in sorted(glob.glob(os.path.join(str(l2_dir), "promoted_seed*.json"))):
        gaps.extend(get_gaps_from_l2_file(fp))
    return gaps


def collect_avggap_candidates_per_model(fp, next_draw_id, rank_to_mask,
                                         l2_dir, global_gaps, top_k):
    """THAY THE cho collect_density_candidates_per_model() (histogram mat
    do lam muot theo cua so) bang 1 co che DON GIAN HON: tinh 1 con so
    KHOANG CACH TRUNG BINH (mean) tu TOAN BO cac gap (so ky giua 2 lan
    trung lien tiep) da tung xay ra trong L2 - uu tien L2 RIENG cua model
    (l2_dir/promoted_seed{seed_start}.json), model nao chua co thi dung
    global_gaps (gop tu toan bo l2_dir) lam du phong.

    Voi tung seed con dang cho trong L1, tinh gap = kỳ_sap_toi -
    kỳ_trung_gan_nhat, roi xep hang cac gap KHAC NHAU theo do LECH TUYET
    DOI so voi trung binh (|gap - avg_gap| CANG NHO cang uu tien) - tuc
    uu tien seed nao "dang o dung do tuoi trung binh" ma cac seed manh
    cua model nay thuong hay trung, thay vi ca 1 histogram day du.

    Tra ve top_k UNG VIEN (moi ung vien 1 gap khac nhau, gan trung binh
    nhat truoc) de AI chon giua chung + giai thich. Neu model KHONG co
    du lieu gap nao (ca rieng lan gop toan cuc deu rong - model qua moi,
    chua co seed nao thang hang trong toan he thong), xep hang du phong
    theo gap NHO NHAT (thay vi bo qua het model) va avg_gap_l2 tra ve
    None de biet la khong co co so thong ke that su.

    Tra ve None neu file L1 rong/loi hoac khong co gap > 0 nao."""
    try:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Bo qua {fp}: {e}")
        return None

    seed_last_hit = {}
    for d in data.get("draws", []):
        did = d.get("draw_id")
        for s in d.get("seeds") or []:
            prev = seed_last_hit.get(s)
            if prev is None or did > prev:
                seed_last_hit[s] = did
    if not seed_last_hit:
        return None

    seed_start = data.get("seed_start")
    model_gaps = get_gaps_from_l2_file(Path(l2_dir) / f"promoted_seed{seed_start}.json") if l2_dir else []
    l2_gaps = model_gaps if model_gaps else (global_gaps or [])
    l2_gap_source = "own" if model_gaps else ("global_fallback" if global_gaps else "none")
    avg_gap = (sum(l2_gaps) / len(l2_gaps)) if l2_gaps else None

    l1_by_gap = {}
    for seed, last_hit in seed_last_hit.items():
        gap = next_draw_id - last_hit
        if gap <= 0:
            continue
        l1_by_gap.setdefault(gap, []).append((seed, last_hit))
    if not l1_by_gap:
        return None

    if avg_gap is not None:
        # Gan trung binh nhat truoc; hoa thi gap nho hon xep truoc (on dinh).
        distinct_gaps = sorted(l1_by_gap.keys(), key=lambda g: (abs(g - avg_gap), g))
    else:
        # Khong co du lieu gap nao lam co so - du phong: gap nho nhat truoc.
        distinct_gaps = sorted(l1_by_gap.keys())
    top_gaps = distinct_gaps[:top_k]

    rng = random.Random(f"{next_draw_id}:{seed_start}:avg")
    candidates = []
    for g in top_gaps:
        seed, last_hit = rng.choice(l1_by_gap[g])
        numbers, special = predict_ticket(seed, next_draw_id, rank_to_mask)
        candidates.append({
            "seed": seed,
            "gap_since_hit": g,
            "diff_to_avg": (round(abs(g - avg_gap), 1) if avg_gap is not None else None),
            "last_hit_draw": last_hit,
            "n_seed_cung_gap": len(l1_by_gap[g]),
            "numbers": numbers,
            "special": special,
        })

    return {
        "file": str(fp),
        "seed_start": seed_start,
        "total_draws_in_model": data.get("total_draws"),
        "total_seeds_in_model": len(seed_last_hit),
        "candidates": candidates,
        "avg_gap_l2": (round(avg_gap, 1) if avg_gap is not None else None),
        "n_gap_samples": len(l2_gaps),
        "l2_gap_source": l2_gap_source,
    }


def build_ai_prompt(next_draw_id, recent_draws, models):
    """Dung ket qua cua collect_avggap_candidates_per_model() (1 phan
    tu/model) de dung 1 prompt van ban, yeu cau AI tra ve JSON
    {"picks": [{"model_index", "seed", "reasoning"}, ...]}, moi model
    DUNG 1 pick, seed PHAI nam trong danh sach ung vien cua chinh model
    do (khong duoc bia seed moi). Cung tuong thich nguoc voi candidate
    kieu density/weight-tho (khong co key diff_to_avg) neu sau nay can
    dung lai."""
    lines = [
        "Ban dang tham gia 1 bai tap THONG KE/NGHIEN CUU ve du lieu xo so "
        "da cong bo cong khai - day la du lieu NGAU NHIEN THAT SU, khong "
        "co cach nao du doan chinh xac, KHONG phai loi khuyen tai chinh "
        "hay danh bac.",
        f"Ky ke tiep can du doan: {next_draw_id:05d} (5 so tu 01-35 + 1 so dac biet tu 01-12).",
        "",
        f"Ket qua {len(recent_draws)} ky GAN NHAT (cu truoc -> moi sau):",
    ]
    for draw_id, numbers, special in recent_draws:
        nums_str = "-".join(f"{n:02d}" for n in numbers)
        lines.append(f"  Ky {draw_id:05d}: {nums_str} + DB {special:02d}")

    lines += [
        "",
        f"Co {len(models)} 'model' doc lap (danh so tu 0), moi model la 1 tap "
        "seed rieng sinh boi cong thuc hash mix64 co dinh, da duoc quet doi "
        "chieu voi lich su that. Voi moi model, tinh 1 con so KHOANG CACH "
        "TRUNG BINH (avg_gap) = trung binh cong cua tat ca cac khoang cach "
        "(so ky) giua 2 lan trung lien tiep ma cac seed DA TUNG thang hang "
        "cua CHINH model do tung co (uu tien du lieu rieng cua model, du "
        "phong bang du lieu gop toan cuc neu model chua co du lieu rieng). "
        "Voi tung seed con dang cho trong pool, tinh gap = so ky da troi "
        "qua ke tu lan trung gan nhat. Danh sach ung vien duoi day da sap "
        "theo do LECH TUYET DOI so voi avg_gap TANG DAN (gap cang GAN trung "
        "binh lich su cang xep truoc) - day la 1 gia thuyet thong ke thuan "
        "tuy ('seed dang o dung do tuoi hay trung nhat'), KHONG phai quy "
        "luat vat ly:",
        "",
    ]
    for i, m in enumerate(models):
        avg_txt = (f"avg_gap L2 = {m['avg_gap_l2']} ky (tu {m.get('n_gap_samples', '?')} mau, "
                   f"nguon: {m.get('l2_gap_source', '?')})") if m.get("avg_gap_l2") is not None \
            else "CHUA co du lieu L2 nao de tinh avg_gap (model con qua moi) - xep theo gap nho nhat"
        lines.append(
            f"--- Model {i} (seed_start={m['seed_start']}, "
            f"{m['total_seeds_in_model']} seed con lai trong pool, {avg_txt}) ---"
        )
        for c in m["candidates"]:
            nums_str = "-".join(f"{n:02d}" for n in c["numbers"])
            if "diff_to_avg" in c:
                diff_txt = f"lech {c['diff_to_avg']} ky so voi trung binh" if c["diff_to_avg"] is not None else "khong co avg de so sanh"
                lines.append(
                    f"  seed={c['seed']} | cach ky gan nhat {c['gap_since_hit']} ky | {diff_txt} "
                    f"({c.get('n_seed_cung_gap', '?')} seed khac cung dung khoang cach nay) | "
                    f"neu chon, du doan ky {next_draw_id:05d} = {nums_str} + DB {c['special']:02d}"
                )
            elif "gap_since_hit" in c:
                lines.append(
                    f"  seed={c['seed']} | cach ky gan nhat {c['gap_since_hit']} ky | "
                    f"trong so mat do L2 tai khoang cach nay: {c.get('weight', '?')} "
                    f"({c.get('n_seed_cung_gap', '?')} seed khac cung dung khoang cach nay) | "
                    f"neu chon, du doan ky {next_draw_id:05d} = {nums_str} + DB {c['special']:02d}"
                )
            else:
                lines.append(
                    f"  seed={c['seed']} | weight={c.get('weight', '?')} | "
                    f"lan trung gan nhat: ky {c['last_hit_draw']:05d} | "
                    f"neu chon, du doan ky {next_draw_id:05d} = {nums_str} + DB {c['special']:02d}"
                )
        lines.append("")

    lines += [
        "YEU CAU: voi MOI model o tren, chon DUNG 1 seed trong danh sach ung "
        "vien CUA CHINH model do (KHONG duoc bia seed khac, khong duoc bo "
        "qua model nao) ma ban thay 'hop ly nhat' dua tren do lech so voi "
        "avg_gap, va bat ky quy luat nao ban quan sat duoc tu lich su gan "
        "day (chi mang tinh tham khao thong ke, khong co co so khoa hoc de "
        "du doan chinh xac 1 RNG that).",
        "CHI tra loi DUNG 1 JSON object, KHONG markdown, KHONG chu thich gi "
        "them ngoai JSON, dung dinh dang:",
        '{"picks": [{"model_index": 0, "seed": 123456, "reasoning": "..."}, ...]}',
        "reasoning viet ngan gon (1-2 cau), bang tieng Viet.",
    ]
    return "\n".join(lines)


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


