#!/usr/bin/env python3
"""BACKTEST chien luoc chon 10 ve tren TOAN BO lich su Lotto 5/35 (data/all.csv) -> bao_cao/backtest_chien_luoc_lotto535.txt.
Voi MOI ky that trong lich su, mo phong REPS bo 10 ve theo tung chien luoc roi tinh tien thuong theo gia tri co ban (10.000d/ve):
  A ngau nhien | B phu deu (7 ve khong chung so + 3 ve, DB khac nhau) | C chum (10 ve chung 3 so)
So voi ky vong ly thuyet chinh xac. Kiem tra them lich su co deu khong (chi binh phuong). Khong dung seed => khong the backtest 've con lai' o day;
loc ve con lai doc lap voi ket qua nen khong doi ky vong (backtest theo cap seed that nam trong doi_chieu_con_lai.py).
  python3 backtest_chien_luoc.py      env: REPS (2000), SEED (1)"""
import os, csv, json
from math import comb
import numpy as np
REPS = int(os.environ.get('REPS') or 2000); rng = np.random.default_rng(int(os.environ.get('SEED') or 1))
CT = comb(35, 5) * 12; COST = 10000
D = []
for r in csv.DictReader(open(os.environ.get('CSV') or 'data/all.csv', encoding='utf-8', newline='')):
    if r.get('product') == 'lotto535':
        try: j = json.loads(r['result_json']); D.append((int(r['draw_id']), sorted(j['numbers']), int(j['special_numbers'][0])))
        except Exception: pass
D.sort(); nd = len(D)
# bang giai co ban: (so chinh, trung DB) -> tien. Doc dac (5+DB) dem rieng. KK: 2 so+DB hoac 1 so+DB (gia dinh)
PRIZE = {(5, 0): 10_000_000, (4, 1): 5_000_000, (4, 0): 500_000, (3, 1): 100_000, (3, 0): 30_000, (2, 1): 10_000, (1, 1): 10_000}
def theory():
    ev = 0.0; hit3 = 0.0
    for k in range(0, 6):
        pk = comb(5, k) * comb(30, 5 - k) / comb(35, 5)
        for db, pd in ((1, 1 / 12), (0, 11 / 12)):
            ev += pk * pd * PRIZE.get((k, db), 0)
    return ev
EV = theory(); EVJ = EV + 6_000_000_000 / CT      # + Doc dac toi thieu 6 ty
LUT = np.zeros((6, 2), dtype=np.int64)
for (k, d), v in PRIZE.items(): LUT[k, d] = v
def gen_random(R):
    t = np.argsort(rng.random((R * 10, 35)), axis=1)[:, :5] + 1
    db = rng.integers(1, 13, (R * 10)); return t.reshape(R, 10, 5), db.reshape(R, 10)
def gen_cover(R):
    base = (np.argsort(rng.random((R, 35)), axis=1) + 1).reshape(R, 7, 5)
    ex = []
    for _ in range(3):
        g = np.argsort(rng.random((R, 7)), axis=1)[:, :5]; e = rng.integers(0, 5, (R, 5))
        ex.append(base[np.arange(R)[:, None], g, e])
    t = np.concatenate([base, np.stack(ex, axis=1)], axis=1)
    db = (np.argsort(rng.random((R, 12)), axis=1)[:, :10] + 1); return t, db
def gen_cluster(R):
    core = (np.argsort(rng.random((R, 35)), axis=1)[:, :3] + 1)
    t = np.zeros((R, 10, 5), dtype=np.int64)
    # moi ve = 3 so goc + 2 so khac (ngau nhien trong 32 so con lai)
    for r in range(R):
        pool = np.setdiff1d(np.arange(1, 36), core[r])
        for i in range(10):
            t[r, i, :3] = core[r]; t[r, i, 3:] = rng.choice(pool, 2, replace=False)
    db = rng.integers(1, 13, (R, 10)); return t, db
STRATS = {'A ngau nhien': gen_random, 'B phu deu': gen_cover, 'C chum (chung 3 so)': gen_cluster}
res = {k: {'pay': 0.0, 'any3': 0, 'any4': 0, 'n': 0, 'jp': 0, 'sq': 0.0} for k in STRATS}
for (_, nums, sp) in D:
    mask = np.zeros(36, dtype=np.int64); mask[nums] = 1
    for name, g in STRATS.items():
        R = REPS // 20 if name.startswith('C') else REPS     # chum cham hon -> it lan hon
        t, db = g(R); k = mask[t].sum(-1); dm = (db == sp).astype(np.int64)
        pay = LUT[k, dm].sum(1); s = res[name]
        s['pay'] += pay.sum(); s['sq'] += (pay.astype(float) ** 2).sum(); s['n'] += R
        s['any3'] += int((k >= 3).any(1).sum()); s['any4'] += int((k >= 4).any(1).sum()); s['jp'] += int(((k == 5) & (dm == 1)).any(1).sum())
# kiem tra deu cua lich su
freq = np.zeros(36); dbf = np.zeros(13)
for (_, nums, sp) in D:
    for x in nums: freq[x] += 1
    dbf[sp] += 1
e1 = nd * 5 / 35; e2 = nd / 12
chi1 = float(((freq[1:] - e1) ** 2 / e1).sum()); chi2 = float(((dbf[1:] - e2) ** 2 / e2).sum())
try:
    from scipy.stats import chi2 as C2; p1 = float(C2.sf(chi1, 34)); p2 = float(C2.sf(chi2, 11))
except Exception: p1 = p2 = float('nan')
out = [f'BACKTEST CHIEN LUOC 10 VE - LOTTO 5/35 | {nd} ky lich su | {REPS} bo ve/ky/chien luoc (C: {REPS // 20}) | chi phi {10 * COST:,}d/bo',
       f'Ky vong ly thuyet / bo 10 ve (khong tinh Doc dac): {10 * EV:,.0f}d = {EV / COST:.1%} chi phi ; tinh them Doc dac toi thieu 6 ty: {10 * EVJ:,.0f}d = {EVJ / COST:.1%}',
       'Gia dinh: giai co ban (Nhat 10tr, Nhi 5tr, Ba 500k, Tu 100k, Nam 30k, KK 10k cho 2so+DB / 1so+DB), CHUA tinh chia giai/Doc dac tang.', '',
       'chien luoc | tien thuong TB/bo | % chi phi | P(>=1 ve >=3 so) | P(>=1 ve >=4 so) | do lech chuan']
for name, s in res.items():
    m = s['pay'] / s['n']; sd = (s['sq'] / s['n'] - m * m) ** 0.5
    out.append(f"{name} | {m:,.0f}d | {m / (10 * COST):.1%} | {s['any3'] / s['n']:.1%} | {s['any4'] / s['n']:.2%} | {sd:,.0f}d")
out += ['', f'Lich su co deu khong? chi binh phuong 35 so: {chi1:.1f} (df 34), p = {p1:.3f} ; so dac biet: {chi2:.1f} (df 11), p = {p2:.3f}.',
        'KET LUAN: cac chien luoc cho ky vong tien thuong bang nhau (sai khac chi la nhieu mo phong); chi khac do bien dong. Khong chien luoc nao thang ly thuyet.']
os.makedirs('bao_cao', exist_ok=True); open('bao_cao/backtest_chien_luoc_lotto535.txt', 'w').write('\n'.join(out) + '\n'); print('\n'.join(out))
