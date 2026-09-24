#!/usr/bin/env python3
"""
explain_consensus_ticket.py - KIEM CHUNG / GIAI THICH ve dong thuan (xem HUONG_DAN_VE_DONG_THUAN.txt).

Voi 1 model (seed_start) va 1 ky (draw_id), doc l1_merged/merged_seed{model}.json,
gom TAT CA seed da trung o cac ky KHAC ky nay (pool), cho moi seed sinh ve cho
ky nay bang lotto_common.predict_ticket-cong thuc, roi dem so seed DOC LAP cung ra 1 ve
= MUC DONG THUAN cua ve do. In ra cac ve co muc nam trong --levels kem danh sach seed.

Cach dung:
    python3 explain_consensus_ticket.py 682305800400 905 --levels 3,4
    python3 explain_consensus_ticket.py 682305800400 283 --levels 2 --limit 5 --show-actual

--show-actual: neu ky da co ket qua trong data/all.csv, in them ve TRUNG THAT va muc dong thuan cua no.
Chi doc du lieu, khong ghi file.
"""
import argparse, csv, json, sys
from pathlib import Path
import numpy as np
from lotto_common import build_binom, build_rank_to_mask, M1, M2, M3, M4, MASK64, C


def mix64_vec(x):
    x = x ^ (x >> np.uint64(30)); x = x * np.uint64(M3)
    x = x ^ (x >> np.uint64(27)); x = x * np.uint64(M4)
    return x ^ (x >> np.uint64(31))


def keys_for(seeds, draw_id):
    """key = rank*12 + (special-1); giong predict_ticket()."""
    with np.errstate(over="ignore"):
        comb = (seeds * np.uint64(M1) + np.uint64(draw_id) * np.uint64(M2)) & np.uint64(MASK64)
        mixed = mix64_vec(comb) & np.uint64(MASK64)
        rank = (mixed % np.uint64(C)).astype(np.int64)
        sp = (mix64_vec(mixed) % np.uint64(12)).astype(np.int64)
    return rank * 12 + sp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("draw_id", type=int)
    ap.add_argument("--levels", default="3,4"); ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--show-actual", action="store_true")
    a = ap.parse_args()
    levels = {int(x) for x in a.levels.split(",")}
    fp = Path(f"l1_merged/merged_seed{a.model}.json")
    data = json.loads(fp.read_text(encoding="utf-8"))
    seeds, src = [], []
    for d in data["draws"]:
        if d["draw_id"] == a.draw_id:      # pool = seed cua cac ky KHAC ky dang xet
            continue
        for s in d["seeds"]:
            seeds.append(s); src.append(d["draw_id"])
    seeds = np.array(seeds, dtype=np.uint64); src = np.array(src)
    uniq, idx = np.unique(seeds, return_index=True)   # khu trung seed (1 seed = 1 phieu)
    key = keys_for(uniq, a.draw_id)
    cnt = np.bincount(key, minlength=C * 12)
    rtm = build_rank_to_mask(build_binom())

    def fmt(k):
        r, sp = divmod(int(k), 12)
        return "-".join(f"{i+1:02d}" for i in range(35) if int(rtm[r]) >> i & 1) + f" + DB {sp+1:02d}"

    print(f"Model {a.model} | ky {a.draw_id} | pool {uniq.size:,} seed doc lap tu {len(set(src.tolist()))} ky khac")
    for lv in sorted(levels):
        ks = np.where(cnt == lv)[0]
        print(f"\nMuc {lv}: {ks.size:,} ve")
        for k in ks[: a.limit]:
            print(f"  {fmt(k)}")
            for s in uniq[key == k]:
                kys = sorted(set(src[seeds == s].tolist()))
                print(f"      seed {int(s)} - da trung o ky {', '.join(map(str, kys))}")
    if a.show_actual:
        for r in csv.DictReader(open("data/all.csv", encoding="utf-8")):
            if int(r["draw_id"]) == a.draw_id:
                j = json.loads(r["result_json"])
                m = sum(1 << (n - 1) for n in j["numbers"])
                rank = {int(v): i for i, v in enumerate(rtm)}[m]
                k = rank * 12 + (j["special_numbers"][0] - 1)
                print(f"\nVe TRUNG THAT ky {a.draw_id}: {fmt(k)} -> muc dong thuan = {int(cnt[k])}")
                break
        else:
            print(f"\n(ky {a.draw_id} chua co trong data/all.csv)")


if __name__ == "__main__":
    sys.exit(main())
