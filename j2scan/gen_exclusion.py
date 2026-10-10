#!/usr/bin/env python3
"""Sinh danh sach VE LOAI (5 so chinh) cho mot ky tu cac seed J2 da quet.
Dung:  python3 j2scan/gen_exclusion.py --draw 934 [--remaining con_lai_934.txt] [--out loai_ve_934.txt]
Doc:   j2scan/out/j2_b*.txt (moi dong: "seed so_ky")
Ve cua seed tai ky D: mix64(seed*M1 + D*M2) % 324632 -> unrank colex -> 5 so (giong scan_j2.cpp / lotto_common.py)."""
import argparse, glob, math
M1, M2 = 0x9E3779B97F4A7C15, 0xD1B54A32D192ED03
M3, M4 = 0xBF58476D1CE4E5B9, 0x94D049BB133111EB
MASK = (1 << 64) - 1
C = 324632
def mix64(x):
    x ^= x >> 30; x = (x * M3) & MASK; x ^= x >> 27; x = (x * M4) & MASK; x ^= x >> 31; return x
def unrank(r):
    nums = []
    for k in range(5, 0, -1):
        x = k - 1
        while math.comb(x + 1, k) <= r: x += 1
        nums.append(x + 1); r -= math.comb(x, k)
    return tuple(sorted(nums))
ap = argparse.ArgumentParser()
ap.add_argument("--draw", type=int, required=True, help="ID ky can loai ve (vd 934)")
ap.add_argument("--glob", default="j2scan/out/j2_b*.txt")
ap.add_argument("--out", default=None)
ap.add_argument("--remaining", default=None, help="ghi cac to hop CON LAI (chua bi loai) ra file nay")
a = ap.parse_args()
seeds = set()
for f in glob.glob(a.glob):
    if "missing" in f: continue
    for l in open(f):
        p = l.split()
        if p: seeds.add(int(p[0]))
ranks = {mix64((s * M1 + a.draw * M2) & MASK) % C for s in seeds}
pct = len(ranks) / C * 100
print(f"{len(seeds)} seed -> {len(ranks)} ve loai khac nhau ({pct:.3f}% trong {C} to hop), con lai {C - len(ranks)}")
out = a.out or f"loai_ve_{a.draw}.txt"
open(out, "w").write("".join(" ".join(f"{n:02d}" for n in unrank(r)) + "\n" for r in sorted(ranks)))
print("ghi", out)
if a.remaining:
    ex = ranks
    open(a.remaining, "w").write("".join(" ".join(f"{n:02d}" for n in unrank(r)) + "\n" for r in range(C) if r not in ex))
    print("ghi", a.remaining)
