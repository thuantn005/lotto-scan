#!/usr/bin/env python3
"""Sinh ve cho 1 ky Max 3D Pro tu cac seed da quet, dem do phu / ve con lai trong 1.000.000 to hop.
Dung: python3 m3dscan/gen_exclusion_m3d.py --draw 756 [--remaining con_lai_756.txt] [--out ve_756.txt]
Doc m3dscan/out/m3d_b*.txt (moi dong "seed so_ky"). Ve = mix64(seed*M1 + draw*M2) % 10^6 -> "aaa bbb"."""
import argparse, glob
M1, M2 = 0x9E3779B97F4A7C15, 0xD1B54A32D192ED03
M3, M4 = 0xBF58476D1CE4E5B9, 0x94D049BB133111EB
MASK = (1 << 64) - 1; C = 10**6
def mix64(x):
    x ^= x >> 30; x = (x * M3) & MASK; x ^= x >> 27; x = (x * M4) & MASK; x ^= x >> 31; return x
ap = argparse.ArgumentParser(); ap.add_argument("--draw", type=int, required=True)
ap.add_argument("--glob", default="m3dscan/out/m3d_b*.txt"); ap.add_argument("--out", default=None); ap.add_argument("--remaining", default=None)
a = ap.parse_args(); seeds = set()
for f in glob.glob(a.glob):
    if "missing" in f: continue
    for l in open(f):
        p = l.split()
        if p: seeds.add(int(p[0]))
ranks = {mix64((s * M1 + a.draw * M2) & MASK) % C for s in seeds}
print(f"{len(seeds)} seed -> {len(ranks)} ve khac nhau ({len(ranks)/C*100:.3f}% trong {C:,} to hop), con lai {C-len(ranks):,}")
out = a.out or f"ve_{a.draw}.txt"
open(out, "w").write("".join(f"{r//1000:03d} {r%1000:03d}\n" for r in sorted(ranks))); print("ghi", out)
if a.remaining: open(a.remaining, "w").write("".join(f"{r//1000:03d} {r%1000:03d}\n" for r in range(C) if r not in ranks))
