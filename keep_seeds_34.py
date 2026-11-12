#!/usr/bin/env python3
"""GIU LAI TAT CA SEED hit >= 3 ky (hit 3, 4, ...) cua Lotto, vinh vien, de dung LOAI VE.
Cap gz co the bi xoa khi truot cua so, nhung seed hit >= 3 ky thi luu o seed_state/keep34_lotto535.txt (seed \\t cac ky hit).
Nguon: (1) moi file inverse/first2_*.txt.gz: dong co cot so-hit >= 3; (2) seed_state/hits_lotto535.tsv: seed da du doan dung them ky sau d2.
Chay nhieu lan an toan: gop (hop cac ky hit), khong mat seed da luu.
  python3 keep_seeds_34.py THU_MUC_GZ"""
import os, sys, glob, re
import numpy as np, pandas as pd
gzdir = sys.argv[1] if len(sys.argv) > 1 else 'inverse'
OUT = 'seed_state/keep34_lotto535.txt'; os.makedirs('seed_state', exist_ok=True)
keep = {}
if os.path.exists(OUT):
    for l in open(OUT):
        a = l.rstrip('\n').split('\t')
        if len(a) == 2 and a[0].isdigit(): keep[int(a[0])] = {int(x) for x in a[1].split(',') if x.strip().isdigit()}
n0 = len(keep)
for f in glob.glob(os.path.join(gzdir, 'first2_*_*.txt.gz')):
    d = pd.read_csv(f, sep=' ', header=None, usecols=[0, 1, 2], dtype={0: np.uint64, 1: np.int32, 2: str}, engine='c')
    h = d[d[1] >= 3]
    for sd, ks in zip(h[0].to_numpy(), h[2].to_numpy()):
        keep.setdefault(int(sd), set()).update(int(x) for x in str(ks).split(',') if x.strip().isdigit())
hf = 'seed_state/hits_lotto535.tsv'
if os.path.exists(hf):
    for l in open(hf):
        a = l.rstrip('\n').split('\t')
        if len(a) == 3 and a[2].strip():
            d1d2 = [int(x) for x in a[1].split('_') if x.isdigit() and int(x) > 0]
            keep.setdefault(int(a[0]), set()).update(d1d2 + [int(x) for x in a[2].split(',') if x.strip().isdigit()])
with open(OUT, 'w') as o:
    for sd in sorted(keep): o.write(f"{sd}\t{','.join(map(str, sorted(keep[sd])))}\n")
print(f'keep34: {len(keep):,} seed hit >= 3 ky (them moi {len(keep) - n0:,}) -> {OUT}')
