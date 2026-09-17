#!/usr/bin/env python3
"""
predict_next_draw_app.py - Du doan ky KE TIEP: MOI MODEL (moi file trong
l1_merged/) tu sinh ra du doan RIENG cua model do. Seed du doan LUON LUON
lay TU L1 (pool seed dang quet cua model do) - l2_merged CHI dung LAM MAU
THONG KE (khong bao gio lay seed truc tiep tu l2_merged de du doan).

CO CHE (chon THEO 2 BUOC, lay KY (draw_id) LAM DON VI - khong gop seed
cua nhieu ky lai voi nhau, vi neu gop theo bucket rong (vd 20 ky) thi 1
ky tinh co co qua nhieu seed se lan at ca vung, sai lech het y nghia "ky
nao dang den han"):
  1. TINH MAT DO (lam muot) tu l2_merged CUA CHINH model do: voi moi seed
     da thang hang (>=2 lan trung J1), tinh khoang cach (so ky) GIUA 2
     LAN TRUNG LIEN TIEP. Voi TUNG ky cu the ma L1 co seed roi vao, uoc
     luong TRONG SO = so khoang cach L2 nam trong cua so [ky -
     APP_GAP_SMOOTH_WINDOW/2, ky + APP_GAP_SMOOTH_WINDOW/2] (lam muot vi
     mau L2 thua - dem dung 1 diem se qua nhieu 0). Lam muot CHI de uoc
     luong trong so cho TUNG KY RIENG LE, KHONG gop seed cua nhieu ky lai.
     Model nao CHUA co du lieu L2 rieng (qua moi) thi DU PHONG dung mat do
     GOP TOAN CUC (tu TAT CA model) thay the tam thoi.
  2. CHON 1 KY CU THE (khong phai 1 bucket/khoang) theo trong so mat do do
     (random.choices) - moi ky la 1 don vi ung cu rieng biet, hoan toan
     KHONG bi anh huong boi so seed cua ky do nhieu hay it.
  3. Trong ky da chon, CHON NGAU NHIEN DEU 1 seed trong so cac seed L1
     thuoc DUNG ky do (co the vai chuc den vai nghin seed, tuy mat do
     pool - nhung day la buoc RIENG, tach biet voi buoc chon ky o tren).
  4. Model khong co ky nao co trong so mat do L2 (hiem) -> DU PHONG cuoi
     cung: random deu tren TOAN BO pool L1 cua model do.
  5. Voi seed da chon, ap dung DUNG cong thuc predict_ticket(seed,
     next_draw_id) (TicketFormula.generate ben Dart / scan_v2.cpp): rank
     = mix64(seed*M1 + draw_id*M2) mod C(35,5) -> unrank thanh 5 so
     chinh; special = mix64(rank_mixed) mod 12 + 1.

QUAN TRONG: day van CHI la 1 gia thuyet thong ke tren du lieu qua khu
(hien tuong "seed lap lai theo chu ky" quan sat tu l2_merged) ap dung
chong len L1 - KHONG co bao dam gi ve tuong lai vi RNG thuc su khong the
du doan duoc. backtest_predictions.py van la thuoc do khach quan duy
nhat de biet chien luoc nay co thuc su hon random hay khong.

-> So ve sinh ra = so file model L1 co seed (moi model dung 1 ve rieng).

ENV:
    CSV_PATH               - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB                - pattern glob file L1 (mac dinh l1_merged/merged_seed*.json)
    L2_DIR                 - thu muc chua file L2, CHI dung tinh histogram (mac dinh l2_merged)
    OUT_PATH               - file .txt ket qua (mac dinh predict/next_draw_predict_app.txt)
    HISTORY_DIR            - thu muc luu lich su du doan (mac dinh predict/history)
    APP_GAP_SMOOTH_WINDOW  - do rong cua so lam muot mat do, tinh bang so ky (mac dinh 20)
    APP_MANUAL_OVERRIDE_JSON - GHI DE THU CONG, TUYET DOI, RIENG TUNG MODEL
        (de trong = tat ca model dung histogram tu dong). Dang JSON:
        {"<seed_start cua model>": {"min": X, "max": Y, "target": Z}, ...}
        Model nao co seed_start xuat hien trong JSON nay se BO QUA
        histogram, chi xet cac seed L1 co "so ky da trui qua" nam trong
        [min, max], chon seed GAN target NHAT (dat min=max=target de bat
        buoc TUYET DOI dung 1 so ky duy nhat). Model nao KHONG co trong
        JSON van tu dong theo histogram L2 nhu binh thuong. Vi du chi
        ghi de rieng 2 model, con lai tu dong:
        {"682305800400": {"min": 267, "max": 267, "target": 267},
         "900477750639": {"min": 100, "max": 200, "target": 150}}
"""

import bisect
import glob
import json
import os
import random
from collections import defaultdict
from pathlib import Path

from lotto_common import (
    build_binom,
    build_rank_to_mask,
    predict_ticket,
    get_next_draw_id,
    save_prediction_history,
)

STRATEGY = "app"

# Nguon ngau nhien dung cho MOI buoc "chon ngau nhien" trong file nay:
# chon bucket co trong so, chon seed trong bucket, va du phong toan phan.
# Giong Random.secure() ben Dart - dung tinh than "random pick" cua app.
_rng = random.SystemRandom()


def get_gaps_from_l2_file(l2_path):
    """Doc 1 file l2_merged, tra ve list SO NGUYEN cac khoang cach (so ky)
    GIUA 2 LAN TRUNG LIEN TIEP cua tung seed da thang hang trong file do.
    Tra ve [] neu file khong ton tai/rong/loi."""
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
    """Gop gap tu MOI file l2_merged/*.json lai - CHI dung lam du phong
    cho model nao chua co (hoac chua du) du lieu L2 rieng cua no."""
    gaps = []
    for fp in sorted(glob.glob(os.path.join(l2_dir, "promoted_seed*.json"))):
        gaps.extend(get_gaps_from_l2_file(Path(fp)))
    return gaps


def pick_seed_by_l2_density(seed_last_hit, next_draw_id, l2_gaps, window_width):
    """Chon THEO 2 BUOC, lay KY (draw_id) lam don vi ca 2 buoc - "khoang
    cach" o day LUON LA SO KY giua 2 lan trung (khong phai khoang cach
    gia tri so cua seed):
      1. Voi TUNG KY CU THE ma L1 co seed roi vao (tuc "so ky da trui
         qua" = 1 gia tri nguyen cu the), tinh TRONG SO = MAT DO L2 lam
         muot quanh ky do (dem so khoang cach - giua 2 lan trung cua cac
         seed da thang hang - roi vao cua so [ky - window_width/2, ky +
         window_width/2]; lam muot vi mau L2 thua, dem dung 1 diem se qua
         nhieu 0).
      2. CHON 1 KY CU THE theo trong so do (random.choices) - moi ky la 1
         don vi ung cu, KHONG ke seed cua ky do nhieu hay it.
      3. Trong DUNG ky da chon, CHON NGAU NHIEN DEU 1 seed trong so cac
         seed L1 thuoc ky do (vd 8000 seed) - vi CA 8000 seed nay deu
         "giong het nhau" ve mat du lieu (deu chi trung dung 1 lan, dung
         vao ky nay), KHONG co thong tin nao khac de phan biet chung, nen
         xac suat deu nhau la lua chon dung.

    Tra ve ((seed, last_hit, gap), n_seed_trong_ky_do, meta) hoac
    (None, 0, {}) neu khong the chon."""
    if not l2_gaps:
        return None, 0, {}

    l1_by_gap = defaultdict(list)
    for seed, last_hit in seed_last_hit.items():
        gap = next_draw_id - last_hit
        if gap <= 0:
            continue
        l1_by_gap[gap].append((seed, last_hit, gap))

    if not l1_by_gap:
        return None, 0, {}

    sorted_l2 = sorted(l2_gaps)
    half_lo = window_width // 2
    half_hi = window_width - half_lo - 1

    def density_weight(g):
        lo = bisect.bisect_left(sorted_l2, g - half_lo)
        hi = bisect.bisect_right(sorted_l2, g + half_hi)
        return hi - lo

    distinct_gaps = sorted(l1_by_gap.keys())
    weights = [density_weight(g) for g in distinct_gaps]

    if sum(weights) == 0:
        return None, 0, {}

    chosen_gap = _rng.choices(distinct_gaps, weights=weights, k=1)[0]
    candidates = l1_by_gap[chosen_gap]
    chosen = _rng.choice(candidates)
    meta = {
        "chosen_ky_gap": chosen_gap,
        "l2_density_weight": density_weight(chosen_gap),
        "n_distinct_ky_available": len(distinct_gaps),
    }
    return chosen, len(candidates), meta


def load_seed_hits_of_file(fp):
    """Doc 1 file L1, tra ve (dict seed -> lan xuat hien GAN NHAT (draw_id
    lon nhat) cua rieng file nay, seed_start cua model, total_draws) hoac
    None neu file rong/loi. Moi seed con trong L1 (chua thang hang len
    l2_merged) thuong chi xuat hien dung 1 lan; neu vi ly do nao do xuat
    hien nhieu hon thi lay lan GAN NHAT (draw_id lon nhat) lam moc."""
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
    return seed_last_hit, data.get("seed_start"), data.get("total_draws")


def pick_due_seed_manual(seed_last_hit, next_draw_id, gap_min, gap_max, target):
    """Che do GHI DE THU CONG TUYET DOI (bo qua histogram): loc seed co
    gap trong [gap_min, gap_max], tim khoang cach GAN target nhat, CHON
    NGAU NHIEN 1 seed trong nhom dong hang o muc gan nhat do. Dat
    gap_min=gap_max=target de bat buoc TUYET DOI dung 1 so ky duy nhat
    (khong con vung "gan dung")."""
    best_diff = None
    tied = []
    for seed, last_hit in seed_last_hit.items():
        gap = next_draw_id - last_hit
        if gap <= 0 or gap < gap_min or gap > gap_max:
            continue
        diff = abs(gap - target)
        if best_diff is None or diff < best_diff:
            best_diff, tied = diff, [(seed, last_hit, gap)]
        elif diff == best_diff:
            tied.append((seed, last_hit, gap))
    if not tied:
        return None, 0
    return _rng.choice(tied), len(tied)


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    l2_dir = os.environ.get("L2_DIR", "l2_merged")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_app.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    window_width = int(os.environ.get("APP_GAP_SMOOTH_WINDOW", "20"))

    raw_overrides = os.environ.get("APP_MANUAL_OVERRIDE_JSON", "").strip()
    try:
        manual_overrides = {str(k): v for k, v in json.loads(raw_overrides).items()} if raw_overrides else {}
    except Exception as e:
        print(f"[App] APP_MANUAL_OVERRIDE_JSON loi cu phap ({e}), bo qua, dung tu dong cho tat ca model")
        manual_overrides = {}

    next_draw_id = get_next_draw_id(csv_path)
    files = sorted(glob.glob(l1_glob))
    print(f"[App] Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"[App] So file model L1 tim thay: {len(files)}")
    print(f"[App] Che do tu dong: chon TUNG KY (cua so lam muot {window_width} ky), "
          f"trong so lay tu mat do L2 CUA TUNG MODEL; ghi de thu cong TUYET DOI cho {len(manual_overrides)} model")

    # Mau gop toan cuc - CHI dung du phong cho model KHONG duoc ghi de thu
    # cong VA chua co L2 rieng.
    global_gaps = get_gaps_from_l2_dir(l2_dir)

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    predictions = []
    for fp in files:
        info = load_seed_hits_of_file(fp)
        if info is None:
            continue
        seed_last_hit, seed_start, total_draws = info

        chosen, n_tied, meta, reason = None, 0, {}, None
        override = manual_overrides.get(str(seed_start))

        if override is not None:
            gmin, gmax, target = int(override["min"]), int(override["max"]), int(override["target"])
            chosen, n_tied = pick_due_seed_manual(seed_last_hit, next_draw_id, gmin, gmax, target)
            if chosen is not None:
                reason = "manual_override"
        else:
            model_gaps = get_gaps_from_l2_file(Path(l2_dir) / f"promoted_seed{seed_start}.json")
            if model_gaps:
                chosen, n_tied, meta = pick_seed_by_l2_density(
                    seed_last_hit, next_draw_id, model_gaps, window_width)
                if chosen is not None:
                    reason = "l2_density_own"
            if chosen is None and global_gaps:
                chosen, n_tied, meta = pick_seed_by_l2_density(
                    seed_last_hit, next_draw_id, global_gaps, window_width)
                if chosen is not None:
                    reason = "l2_density_global_fallback"

        if chosen is not None:
            seed, last_hit_draw_id, gap_since_hit = chosen
        else:
            seed = _rng.choice(sorted(seed_last_hit.keys()))
            last_hit_draw_id = seed_last_hit[seed]
            gap_since_hit = next_draw_id - last_hit_draw_id
            reason = "l1_random_fallback"

        numbers, special = predict_ticket(seed, next_draw_id, rank_to_mask)
        predictions.append({
            "file": fp,
            "seed_start": seed_start,
            "total_seeds_in_model": len(seed_last_hit),
            "seed": seed,
            "reason": reason,
            "last_hit_draw_id": last_hit_draw_id,
            "gap_since_hit": gap_since_hit,
            "n_tied_candidates": n_tied,
            "meta": meta,
            "numbers": numbers,
            "special": special,
        })

    REASON_LABEL = {
        "l2_density_own": "UU TIEN - mat do L2 rieng cua model",
        "l2_density_global_fallback": "UU TIEN - mat do L2 gop toan cuc (model chua co L2 rieng)",
        "manual_override": "UU TIEN - ghi de thu cong",
        "l1_random_fallback": "DU PHONG - random deu tren L1",
    }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN APP (moi model 1 ve).\n")
        f.write("Seed LUON lay tu L1; l2_merged CHI dung tinh MAT DO (lam muot) khoang\n")
        f.write("cach RIENG cho TUNG MODEL. Chon THEO 2 BUOC, lay KY (draw_id) lam don\n")
        f.write("vi (khong gop seed cua nhieu ky lai voi nhau, tranh 1 ky co qua nhieu\n")
        f.write("seed lan at ca vung): (1) chon 1 KY CU THE theo trong so mat do L2, (2)\n")
        f.write("trong ky do, chon ngau nhien deu 1 seed. Khong co du lieu phu hop thi\n")
        f.write("roi ve random deu tren toan bo pool L1 cua model do. Cong thuc hash\n")
        f.write("giong TicketFormula.dart / scan_v2.cpp (khong AI/ML).\n\n")

        for info in predictions:
            nums_str = "-".join(f"{n:02d}" for n in info["numbers"])
            f.write(f"--- Model (l1_merged file: {info['file']}) ---\n")
            f.write(f"  seed_start cua model: {info['seed_start']}\n")
            f.write(f"  so seed con trong L1 cua model nay: {info['total_seeds_in_model']}\n")
            f.write(f"  ({REASON_LABEL.get(info['reason'], info['reason'])})\n")
            if info["meta"]:
                f.write(f"    ky duoc chon: cach {info['meta']['chosen_ky_gap']} ky "
                        f"(trong so mat do L2 tai ky nay: {info['meta']['l2_density_weight']}, "
                        f"trong so {info['meta']['n_distinct_ky_available']} ky co seed L1)\n")
            if info["n_tied_candidates"]:
                f.write(f"    chon ngau nhien trong {info['n_tied_candidates']} seed cung dung ky nay\n")
            f.write(f"  seed duoc chon: {info['seed']}\n")
            f.write(f"    lan xuat hien gan nhat trong L1: ky {info['last_hit_draw_id']:05d}, "
                    f"cach ky sap toi {info['gap_since_hit']} ky\n")
            f.write(f"  DU DOAN ky {next_draw_id:05d}: {nums_str} + DAC BIET {info['special']}\n\n")

        if not predictions:
            f.write("(Khong co model nao co seed, khong co du doan.)\n")

    hpath = save_prediction_history(history_dir, next_draw_id, STRATEGY, predictions)

    n_priority = sum(1 for p in predictions if p["reason"] != "l1_random_fallback")
    print(f"[App] Da ghi {len(predictions)} du doan vao {out_path} "
          f"({n_priority} theo trong so l2_merged, {len(predictions) - n_priority} du phong random)")
    print(f"[App] Da luu lich su du doan ({STRATEGY}) vao {hpath}")
    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_MODELS={len(predictions)}")


if __name__ == "__main__":
    main()
