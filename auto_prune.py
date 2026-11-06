#!/usr/bin/env python3
"""Lap ke hoach loai ve + tia cap cu.
  python3 auto_prune.py GAME THU_MUC_GZ NEXT_DRAW TARGET [MAX_LIST]
GAME = lotto535 | mega. Doc cac first2_*.txt.gz (hoac first2_mega_*.txt.gz) trong THU_MUC_GZ.
1) Tinh so ve con lai cho ky NEXT_DRAW khi dung TAT CA cac cap.
2) Neu con lai > TARGET -> need_more=true (workflow quet them cap).
3) Neu da <= TARGET -> chon tap cap NHO NHAT (tham lam lazy) du de con lai <= TARGET; cac cap con lai vao drop.
Ghi plan.json, va ve_con_lai_<game>_<ky>.txt (neu so ve <= MAX_LIST)."""
import sys, glob, os, re, json, heapq
import numpy as np, pandas as pd
from math import comb
game, d, nxt, target = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
maxl = int(sys.argv[5]) if len(sys.argv) > 5 else 300000
LOTTO = game == 'lotto535'
MOD = 324632 if LOTTO else 8145060
C = MOD * 12 if LOTTO else MOD
pat = 'first2_*_*.txt.gz' if LOTTO else 'first2_mega_*_*.txt.gz'
M1 = np.uint64(0x9E3779B97F4A7C15); M2 = 0xD1B54A32D192ED03
M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
add = np.uint64((nxt * M2) & ((1 << 64) - 1))
def mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def keys(s):
    with np.errstate(over='ignore'):
        mx = mix(s * M1 + add); r = (mx % np.uint64(MOD)).astype(np.int64)
        if LOTTO: r = r * 12 + (mix(mx) % np.uint64(12)).astype(np.int64)
    return np.unique(r).astype(np.int32)
files = sorted(glob.glob(os.path.join(d, pat)))
name = lambda f: re.search(r'first2_(?:mega_)?(\d+_\d+)', f).group(1)
K = {}
for f in files:
    s = pd.read_csv(f, sep=' ', header=None, usecols=[0], dtype={0: np.uint64}, engine='c')[0].to_numpy()
    K[name(f)] = keys(s)
allc = np.zeros(C, bool)
for k in K.values(): allc[k] = True
rem_all = int(C - allc.sum())
plan = dict(game=game, next_draw=nxt, target=target, pairs=len(K), remaining_all=rem_all, need_more=rem_all > target)
covered = np.zeros(C, bool); keep = []; rem = C
if not plan['need_more']:
    heap = [(-len(k), n) for n, k in K.items()]; heapq.heapify(heap)
    while heap and rem > target:
        _, n = heapq.heappop(heap); k = K[n]; g = int(np.count_nonzero(~covered[k]))
        if heap and g < -heap[0][0]: heapq.heappush(heap, (-g, n)); continue   # gain cu, tinh lai (lazy)
        covered[k] = True; keep.append(n); rem = int(C - covered.sum())
    plan.update(keep=sorted(keep), drop=sorted(set(K) - set(keep)), remaining_keep=rem)
else:
    plan.update(keep=sorted(K), drop=[], remaining_keep=rem_all)
json.dump(plan, open('plan.json', 'w'), indent=1)
print({k: (v if not isinstance(v, list) else len(v)) for k, v in plan.items()})
final = covered if not plan['need_more'] else allc
left = np.nonzero(~final)[0]
if len(left) <= maxl:
    out = f've_con_lai_{game}_{nxt}.txt'
    if LOTTO:
        from lotto_common import build_binom, build_rank_to_mask
        lut = build_rank_to_mask(build_binom())
        with open(out, 'w') as o:
            for k in left:
                r, sp = divmod(int(k), 12); m = lut[r]
                o.write(' '.join(f'{i+1:02d}' for i in range(35) if m >> i & 1) + f' | DB {sp+1:02d}\n')
    else:
        T = [np.array([comb(i, j) if i >= j else 0 for i in range(46)], dtype=np.int64) for j in range(7)]
        r = left.astype(np.int64); cols = []
        for j in range(6, 0, -1):
            x = np.searchsorted(T[j], r, side='right') - 1; cols.append(x + 1); r = r - T[j][x]
        A = np.sort(np.stack(cols, 1), axis=1)
        with open(out, 'w') as o:
            for row in A: o.write('-'.join(f'{v:02d}' for v in row) + '\n')
    print('da ghi', out, len(left))
