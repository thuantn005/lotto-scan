#!/usr/bin/env python3
"""Gop inverse/ket_qua_*.txt, kiem tra lai seed bang hash tren data/all.csv, loc seed >= N ky va chuoi lien tiep.
Dung: python3 filter_inverse.py --min 4 --out inverse/tong_hop_inverse.txt"""
import argparse, glob, os, re
from lotto_common import build_binom, load_all_actual_results

M = (1 << 64) - 1
M1, M2, M3, M4 = 0x9E3779B97F4A7C15, 0xD1B54A32D192ED03, 0xBF58476D1CE4E5B9, 0x94D049BB133111EB
def mix(x):
    x ^= x >> 30; x = (x * M3) & M; x ^= x >> 27; x = (x * M4) & M; x ^= x >> 31; return x

ap = argparse.ArgumentParser(); ap.add_argument("--min", type=int, default=4)
ap.add_argument("--out", default="inverse/tong_hop_inverse.txt"); ap.add_argument("--dir", default="inverse")
a = ap.parse_args()
b = build_binom(); D = []
for d, (n, sp, _) in sorted(load_all_actual_results("data/all.csv").items()):
    p = sorted(x - 1 for x in n); D.append((d, sum(b[p[k - 1]][k] for k in range(1, 6)), sp))
def hits(seed):
    h = []
    for d, r, sp in D:
        mx = mix((seed * M1 + d * M2) & M)
        if mx % 324632 == r and mix(mx) % 12 == sp - 1: h.append(d)
    return h
def streak(ks):
    best = cur = 1 if ks else 0
    for x, y in zip(ks, ks[1:]):
        cur = cur + 1 if y == x + 1 else 1; best = max(best, cur)
    return best

seeds = {}; pairs = []
for f in sorted(glob.glob(os.path.join(a.dir, "ket_qua_*.txt"))):
    pairs.append(os.path.basename(f)[8:-4]); on = False
    for l in open(f):
        if l.startswith("--- seed"): on = True; continue
        if on and re.match(r"^\d+ \d+ ", l): seeds[int(l.split()[0])] = 1
rows = []
for s in seeds:
    h = hits(s)  # kiem tra lai tren toan bo ky hien co
    if len(h) >= a.min: rows.append((len(h), streak(h), s, h))
rows.sort(reverse=True)
with open(a.out, "w") as f:
    f.write(f"Da quet {len(pairs)} cap: {', '.join(pairs)}\n")
    f.write(f"{len(seeds)} seed trong file, {len(rows)} seed co >= {a.min} ky (da kiem tra lai bang hash, {len(D)} ky)\n")
    f.write("so_hit chuoi_lien_tiep seed cac_ky\n")
    for n, st, s, h in rows: f.write(f"{n} {st} {s} {','.join(map(str, h))}\n")
print(open(a.out).read())
