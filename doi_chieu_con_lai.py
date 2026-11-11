#!/usr/bin/env python3
"""Doi chieu VE CON LAI voi ket qua that (Lotto 5/35). Moi ky 1 lan.
Voi moi ky D da co ket qua: lay USE_PAIRS cap MOI NHAT co d2 < D (cap biet truoc khi ky D quay), tinh tap ve bi loai (seed cua cac cap sinh ra ve cho ky D),
roi xem VE TRUNG THAT (5 so + DB) cua ky D la CON LAI hay BI LOAI. Ngau nhien: ve that con lai voi xac suat ~ exp(-so_seed/tong_ve).
  python3 doi_chieu_con_lai.py THU_MUC_GZ      env: USE_PAIRS (4), SAVE_LAST (5), CSV (data/all.csv)
Ghi ve_trung/doi_chieu_con_lai.jsonl (log) va ve_trung/doi_chieu_con_lai.txt (de doc + tong ket)."""
import os, re, sys, csv, json, glob
from math import comb, exp
import numpy as np, pandas as pd
gzdir = sys.argv[1] if len(sys.argv) > 1 else 'inverse'
USE = int(os.environ.get('USE_PAIRS') or 4); LAST = int(os.environ.get('SAVE_LAST') or 5); CSV = os.environ.get('CSV') or 'data/all.csv'
MOD = 324632; CT = MOD * 12
M1 = np.uint64(0x9E3779B97F4A7C15); M2 = 0xD1B54A32D192ED03; M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
def mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def tid(s, d):
    with np.errstate(over='ignore'):
        m = mix(s * M1 + np.uint64((d * M2) & ((1 << 64) - 1))); return (m % np.uint64(MOD)).astype(np.int64) * 12 + (mix(m) % np.uint64(12)).astype(np.int64)
def rank(nums): return sum(comb(n - 1, i + 1) for i, n in enumerate(sorted(nums)))
RES = {}; DATE = {}
for r in csv.DictReader(open(CSV, encoding='utf-8', newline='')):
    if (r.get('draw_id') or '').isdigit() and r.get('product') == 'lotto535':
        try: j = json.loads(r['result_json']); RES[int(r['draw_id'])] = rank(j['numbers']) * 12 + int(j['special_numbers'][0]) - 1; DATE[int(r['draw_id'])] = r.get('draw_date', '')
        except Exception: pass
pat = re.compile(r'first2_(\d+)_(\d+)\.txt\.gz$'); files = []
for f in glob.glob(os.path.join(gzdir, 'first2_*.txt.gz')):
    m = pat.search(f)
    if m: files.append((int(m.group(1)), int(m.group(2)), f))
os.makedirs('ve_trung', exist_ok=True); lf = 've_trung/doi_chieu_con_lai.jsonl'
log = [json.loads(l) for l in open(lf)] if os.path.exists(lf) else []; done = {r['ky'] for r in log}
cache = {}
def seeds(f):
    if f not in cache: cache[f] = pd.read_csv(f, sep=' ', header=None, usecols=[0], dtype={0: np.uint64}, engine='c')[0].to_numpy()
    return cache[f]
for D in sorted(RES)[-LAST:]:
    if D in done: continue
    fs = sorted([x for x in files if x[1] < D], key=lambda x: -x[0])[:USE]
    if not fs: continue
    ns = 0; bi_loai = False; cnt = 0
    for a, b, f in fs:
        s = seeds(f); ns += len(s); h = int((tid(s, D) == RES[D]).sum()); cnt += h; bi_loai |= h > 0
    rec = {'ky': D, 'ngay': DATE.get(D, ''), 'so_cap': len(fs), 'cap': [f'{a}_{b}' for a, b, _ in fs], 'so_seed': ns, 've_that_con_lai': not bi_loai,
           'so_seed_sinh_ve_that': cnt, 'xs_con_lai_ngau_nhien': round(exp(-ns / CT), 4)}
    log.append(rec)
log.sort(key=lambda r: r['ky'])
with open(lf, 'w') as o:
    for r in log: o.write(json.dumps(r, ensure_ascii=False) + '\n')
with open('ve_trung/doi_chieu_con_lai.txt', 'w') as o:
    o.write('# ky | ngay | so cap | so seed | ve trung that: CON LAI hay BI LOAI | so seed sinh ra ve that | xs con lai ngau nhien\n')
    for r in log: o.write(f"{r['ky']} | {r['ngay']} | {r['so_cap']} | {r['so_seed']:,} | {'CON LAI' if r['ve_that_con_lai'] else 'BI LOAI'} | {r['so_seed_sinh_ve_that']} | {r['xs_con_lai_ngau_nhien']:.1%}\n")
    if log:
        k = sum(r['ve_that_con_lai'] for r in log); e = sum(r['xs_con_lai_ngau_nhien'] for r in log)
        o.write(f'# TONG KET: {len(log)} ky | ve that nam trong danh sach CON LAI: {k} ky ({k / len(log):.1%}) | ky vong ngau nhien: {e:.2f} ky ({e / len(log):.1%})\n')
print(open('ve_trung/doi_chieu_con_lai.txt').read().splitlines()[-1])
