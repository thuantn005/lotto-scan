#!/usr/bin/env python3
"""
find_consensus_tickets.py - Voi 1 KY MUC TIEU (vi du 900, co the la ky
tuong lai CHUA quay), quet CAC seed dau vao (L1 va/hoac L2), ap CUNG 1
cong thuc du doan predict_ticket(seed, ky_muc_tieu, rank_to_mask) cho
tung seed, roi GOM NHOM cac seed KHAC NHAU cho ra CUNG 1 ket qua du doan
(dung 5 so + dung so dac biet).

Y TUONG: 1 seed rieng le du "manh" van chi la 1 "y kien". Nhung neu N
seed HOAN TOAN KHAC NHAU (khac gia tri seed, tung trung THAT o cac ky
KHAC NHAU trong qua khu - tuc doc lap ve mat du lieu) ma lai cung cho ra
DUNG 1 ve cho ky muc tieu, day la tin hieu "dong thuan" - tuong tu
nhieu chuyen gia doc lap cung dua ra 1 du doan.

2 NGUON DU LIEU (co the dung 1 hoac ca 2 cung luc):
  - L1 (L1_GLOB, vi du l1_merged/merged_seed*.json): seed CHI moi trung
    THAT 1 LAN (chua du nguong de "thang hang" len L2). Pool RAT LON
    (co the hang chuc TRIEU ban ghi/model), moi seed gan voi DUNG 1 ky
    da tung trung.
  - L2 (L2_GLOB, vi du l2_merged/promoted_seed*.json): seed da tung
    trung THAT >= 2 lan (da "thang hang"). Pool nho hon nhieu nhung moi
    seed da duoc kiem chung 2 lan doc lap.

CANH BAO THONG KE QUAN TRONG (voi pool L1, RAT LON):
  Voi hang chuc trieu seed dau vao nhung chi ~3.9 trieu to hop ve co
  the (C(35,5) x 12), theo "nghich ly ngay sinh nhat" thi TRUNG BINH
  MOI to hop ve deu se co VAI seed "trung ngau nhien" chi vi so luong
  dau vao qua lon - HOAN TOAN khong can co quy luat that nao. Vi vay
  MIN_SEEDS phai dat CAO HON HAN muc trung binh ky vong (script tu tinh
  va in ra bang phan phoi Poisson) thi 1 nhom moi thuc su dang chu y ve
  mat thong ke - chu KHONG phai bat ky nhom >=2 seed nao cung co y
  nghia (khac voi khi dung L2, pool nho, >=2 seed da la hiem).

ENV:
    TARGET_DRAW_ID  - ky muc tieu can du doan (BAT BUOC, vi du "900")
    L1_GLOB         - duong dan (co wildcard *) toi (cac) file
                      l1_merged/merged_seed*.json. De trong ("") de
                      KHONG dung L1.
    L2_GLOB         - duong dan (co wildcard *) toi (cac) file
                      l2_merged/promoted_seed*.json. De trong ("") de
                      KHONG dung L2. (Neu ca L1_GLOB va L2_GLOB deu
                      trong, mac dinh dung L2_GLOB="l2_merged/promoted_seed*.json"
                      de tuong thich nguoc.)
    TOP_N           - so nhom ve dong thuan cao nhat can in ra (mac
                      dinh 20)
    MIN_SEEDS       - chi hien nhom co tu bay nhieu seed DOC LAP tro
                      len (mac dinh 2 khi chi dung L2; NEN DAT CAO HON
                      NHIEU - vi du 10-20+ - khi dung L1, xem bang
                      Poisson script tu in ra de chon so hop ly)
    OUT_PATH        - file text ghi lai ket qua day du (mac dinh
                      predict/consensus_tickets_{ky}.txt)
"""

import glob
import json
import math
import os
from collections import defaultdict
from pathlib import Path

from lotto_common import build_binom, build_rank_to_mask, mix64, M1, M2, MASK64, C, score_ticket


def get_actual_result(csv_path, draw_id):
    """Tra ve (numbers, special) THAT cua 1 ky tu data/all.csv, hoac None
    neu ky do chua co ket qua (con la ky tuong lai) hoac khong tim thay."""
    import csv as csv_module
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv_module.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 5:
                    continue
                try:
                    did = int(row[1])
                except ValueError:
                    continue
                if did == draw_id and row[3] == "confirmed":
                    result = json.loads(row[4])
                    return sorted(result["numbers"]), result["special_numbers"][0]
    except FileNotFoundError:
        pass
    return None


def iter_l1_seeds(l1_glob):
    """Sinh lan luot (seed, seed_start_model, hit_draw_id) tu cac file
    L1 khop l1_glob - KHONG giu toan bo trong bo nho cung luc (dung
    generator) vi L1 co the co hang chuc trieu ban ghi."""
    files = sorted(glob.glob(l1_glob)) if l1_glob else []
    for fp in files:
        try:
            data = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Bo qua {fp}: {e}")
            continue
        seed_start = data.get("seed_start")
        for d in data.get("draws", []):
            did = d.get("draw_id")
            for s in d.get("seeds") or []:
                yield s, seed_start, did


def iter_l2_seeds(l2_glob):
    """Sinh lan luot (seed, seed_start_model, hit_draw_id) tu cac file
    L2 khop l2_glob - 1 seed L2 co the co NHIEU hit_draw_id (>=2), sinh
    1 dong rieng cho MOI hit de dong nhat dinh dang voi L1."""
    files = sorted(glob.glob(l2_glob)) if l2_glob else []
    for fp in files:
        try:
            data = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Bo qua {fp}: {e}")
            continue
        seed_start = data.get("seed_start")
        for p in data.get("promoted", []):
            seed = p["seed"]
            for h in (p.get("hits") or []):
                yield seed, seed_start, h["draw_id"]


def poisson_pmf(k, mu):
    return math.exp(-mu) * (mu ** k) / math.factorial(k)


def poisson_tail_ge(k, mu, max_k=200):
    """P(X >= k) cho phan phoi Poisson(mu), tinh bang 1 - P(X < k)."""
    p_lt = sum(poisson_pmf(i, mu) for i in range(0, min(k, max_k)))
    return max(0.0, 1.0 - p_lt)


def main():
    target_draw_id = os.environ.get("TARGET_DRAW_ID")
    if not target_draw_id:
        raise SystemExit("Can bien moi truong TARGET_DRAW_ID (vi du: TARGET_DRAW_ID=900)")
    target_draw_id = int(target_draw_id)

    l1_glob = os.environ.get("L1_GLOB", "")
    l2_glob = os.environ.get("L2_GLOB", "")
    if not l1_glob and not l2_glob:
        l2_glob = "l2_merged/promoted_seed*.json"  # tuong thich nguoc voi ban truoc

    top_n = int(os.environ.get("TOP_N", "20"))
    min_seeds = int(os.environ.get("MIN_SEEDS", "2"))
    out_path = os.environ.get("OUT_PATH", f"predict/consensus_tickets_{target_draw_id:05d}.txt")
    exclude_hits_at_target = os.environ.get("EXCLUDE_HITS_AT_TARGET", "1") != "0"
    known_up_to_raw = os.environ.get("KNOWN_UP_TO_DRAW_ID", "")
    known_up_to = int(known_up_to_raw) if known_up_to_raw else None

    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    actual = get_actual_result(csv_path, target_draw_id)
    if actual:
        actual_numbers, actual_special = actual
        print(f"*** Ky {target_draw_id:05d} DA CO KET QUA THAT: {'-'.join(f'{n:02d}' for n in actual_numbers)} + DB {actual_special:02d} ***")
        print("*** (se tu danh dau nhom nao TRUNG voi ket qua that o duoi) ***\n")
    else:
        actual_numbers, actual_special = None, None

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    m1, m2, mask64 = M1, M2, MASK64  # local binding cho vong lap nhanh hon

    def fast_key(seed):
        """Nhu predict_ticket() nhung CHUA giai ma 35 so - chi tra ve
        (rank, special), du de lam KHOA gom nhom (2 seed cho CUNG
        (rank, special) chac chan cho ra CUNG 5 so + dac biet, vi rank
        <-> mask la anh xa 1-1 qua rank_to_mask). Nhanh hon nhieu khi
        phai chay hang chuc trieu lan."""
        combined = (seed * m1 + target_draw_id * m2) & mask64
        mixed = mix64(combined)
        rank = mixed % C
        mixed2 = mix64(mixed)
        special = (mixed2 % 12) + 1
        return (rank, special)

    groups = defaultdict(list)  # (rank, special) -> [(seed, seed_start, hit_draw_id), ...]
    n_total = 0

    sources = []
    if l1_glob:
        sources.append(("L1", iter_l1_seeds(l1_glob)))
    if l2_glob:
        sources.append(("L2", iter_l2_seeds(l2_glob)))

    for src_name, gen in sources:
        n_src = 0
        n_excluded = 0
        n_excluded_future = 0
        for seed, seed_start, hit_draw_id in gen:
            if exclude_hits_at_target and hit_draw_id == target_draw_id:
                # Seed nay von DA duoc gan nhan "tung trung THAT tai chinh
                # ky muc tieu" - dua no vao gom nhom se VONG TRON LOGIC
                # (chac chan "trung" vi do CHINH LA dinh nghia cua no),
                # KHONG phai tin hieu dong thuan that. Bo qua.
                n_excluded += 1
                continue
            if known_up_to is not None and hit_draw_id > known_up_to:
                # BACKTEST DUNG CACH: gia lap dung luc dang dung o ky
                # known_up_to (vi du 847) va CHUA biet ket qua cac ky SAU
                # do (848, 849, ...) - loai bo moi seed ma "bang chung
                # trung" cua no chi co duoc TU TUONG LAI so voi thoi diem
                # gia dinh dang du doan. Neu khong loc cai nay, ket qua se
                # bi "look-ahead bias" (dung thong tin ma luc do chua the
                # co that).
                n_excluded_future += 1
                continue
            key = fast_key(seed)
            groups[key].append((seed, seed_start, hit_draw_id))
            n_src += 1
            n_total += 1
            if n_src % 2_000_000 == 0:
                print(f"  ... da xu ly {n_src:,} ban ghi tu nguon {src_name}")
        notes = []
        if n_excluded:
            notes.append(f"da loai tru {n_excluded:,} ban ghi trung dung ky muc tieu")
        if n_excluded_future:
            notes.append(f"da loai tru {n_excluded_future:,} ban ghi 'tu tuong lai' (hit_draw_id > {known_up_to}, xem KNOWN_UP_TO_DRAW_ID)")
        excl_note = " (" + "; ".join(notes) + ")" if notes else ""
        print(f"Nguon {src_name}: {n_src:,} ban ghi (seed x lan trung).{excl_note}")

    if n_total == 0:
        print("Khong doc duoc seed nao (kiem tra lai L1_GLOB/L2_GLOB), dung.")
        return

    # QUAN TRONG: mu phai tinh theo so SEED DOC LAP, KHONG phai tong so
    # ban ghi - vi 1 seed L2 co the co 2+ hit_draw_id (2+ ban ghi) nhung
    # van CHI rot vao DUNG 1 to hop ve cho ky muc tieu (fast_key chi phu
    # thuoc vao seed + target_draw_id, khong phu thuoc hit_draw_id). Neu
    # dung n_total (dem ca ban ghi trung lap) se lam mu bi thoi phong sai
    # (vi du seed L2 co trung binh 2 hit/seed se lam mu cao gap ~2 lan
    # thuc te).
    n_distinct_seeds_total = len({m[0] for members in groups.values() for m in members})

    total_tickets_possible = C * 12
    mu = n_distinct_seeds_total / total_tickets_possible

    print(f"\nTONG so ban ghi (seed x lan trung) dau vao: {n_total:,}")
    print(f"Trong do so SEED DOC LAP (dung de tinh mu): {n_distinct_seeds_total:,}")
    print(f"Tong so to hop ve co the (C(35,5) x 12 dac biet): {total_tickets_possible:,}")
    print(f"=> Trung binh ky vong moi to hop ve: mu = {mu:.4f} ban ghi/to hop (phan phoi Poisson)")
    print("Bang tham khao: so nhom UOC TINH co >= k seed CHI DO NGAU NHIEN (birthday paradox), voi mu tren:")
    for k in [2, 3, 5, 8, 10, 15, 20, 30, 50]:
        p_tail = poisson_tail_ge(k, mu)
        expected_groups = total_tickets_possible * p_tail
        if expected_groups < 0.0001 and k > 5:
            print(f"   k>={k:<3d}: uoc tinh ~{expected_groups:.2e} nhom do ngau nhien (RAT hiem - neu tim thay 1 nhom that, dang chu y)")
        else:
            print(f"   k>={k:<3d}: uoc tinh ~{expected_groups:.2f} nhom do ngau nhien")
    print("(Chon MIN_SEEDS o muc ma so nhom uoc tinh o tren << 1 de dam bao nhom tim duoc KHONG PHAI ngau nhien thuan tuy)\n")

    # Chi giu (va sap xep) nhung nhom co so seed DOC LAP >= min_seeds.
    ranked = []
    for key, members in groups.items():
        distinct_seeds = {m[0] for m in members}
        if len(distinct_seeds) >= min_seeds:
            ranked.append((key, members, len(distinct_seeds)))
    ranked.sort(key=lambda x: (-x[2], x[0]))

    print(f"Ky muc tieu: {target_draw_id:05d} | So nhom dong thuan (>= {min_seeds} seed doc lap): {len(ranked)}")
    print(f"Top {min(top_n, len(ranked))} nhom dong thuan cao nhat:\n")

    lines_out = [
        f"KY MUC TIEU: {target_draw_id:05d}",
        f"Nguon du lieu: " + ", ".join(f"{s}={g}" for s, g in [("L1", l1_glob), ("L2", l2_glob)] if g),
        f"Tong so ban ghi dau vao: {n_total:,} (so seed doc lap: {n_distinct_seeds_total:,})",
        f"Tong so to hop ve co the: {total_tickets_possible:,}",
        f"mu (trung binh ky vong/to hop, Poisson): {mu:.4f}",
        f"So nhom dong thuan tim duoc (>= {min_seeds} seed doc lap): {len(ranked)}",
        "",
    ]

    for rank_i, (key, members, n_distinct) in enumerate(ranked[:top_n], start=1):
        rank_val, special = key
        mask = rank_to_mask[rank_val]
        numbers = [i + 1 for i in range(35) if mask & (1 << i)]
        nums_str = "-".join(f"{x:02d}" for x in numbers)
        header = f"#{rank_i}: {nums_str} + DB {special:02d}  <-  {n_distinct} seed DOC LAP cung dong y"
        if actual_numbers is not None:
            score = score_ticket(numbers, special, actual_numbers, actual_special)
            if score["is_j1"]:
                header += "  >>> TRUNG TUYET DOI CA 5 SO + DAC BIET VOI KET QUA THAT!!! <<<"
            elif score["matches"] >= 3:
                header += f"  >>> Trung {score['matches']}/5 so voi ket qua that{' + dac biet' if score['special_hit'] else ''} <<<"
        print(header)
        lines_out.append(header)
        # Gop cac hit-draw-id theo tung seed (1 seed co the xuat hien
        # nhieu lan neu no tung trung o nhieu ky khac nhau).
        by_seed = defaultdict(lambda: {"seed_start": None, "hits": []})
        for seed, seed_start, hit_draw_id in members:
            by_seed[seed]["seed_start"] = seed_start
            by_seed[seed]["hits"].append(hit_draw_id)
        for seed, info in sorted(by_seed.items()):
            hits_str = ", ".join(f"ky {h:05d}" for h in sorted(info["hits"]))
            detail = f"    seed={seed} (model seed_start={info['seed_start']}) - tung trung THAT o: {hits_str}"
            print(detail)
            lines_out.append(detail)
        print()
        lines_out.append("")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    Path(out_path).write_text("\n".join(lines_out), encoding="utf-8")
    print(f"Da ghi ket qua day du vao {out_path}")


if __name__ == "__main__":
    main()
