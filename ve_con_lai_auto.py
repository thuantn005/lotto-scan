#!/usr/bin/env python3
"""Tu dong: loai ve Lotto 5/35 bang cac seed inverse (inverse/first2_*.txt.gz + seed 4 hit) cho ky tiep theo.
Ghi vao ve_con_lai/: con_lai_<ky>.txt, muc1_<ky>.txt (ve do dung 1 seed), muc2_<ky>.txt (ve do dung 2 seed), nhom theo cap, thong_ke_<ky>.txt (+ loai_<ky>.txt.gz neu EXPORT_LOAI=true).
Neu con lai > TARGET: de xuat hang doi cap quet them (GITHUB_OUTPUT: next_queue).
Bien moi truong: DRAW (de trong = tu tinh ky sap quay), TARGET (mac dinh 1), MAX_PAIRS (12), EXPORT_LOAI (false), KEEP (10).
MODE=dup (mac dinh): VE CON LAI = ve bi loai do SEED TRUNG CAC CAP, tuc ve duoc sinh ra boi >= MIN_PAIRS cap khac nhau (mac dinh 2;
  seed 4 hit tinh nhu 1 nguon). TOP>0: chi giu TOP ve co nhieu cap trung nhat. MODE=old: ve CON LAI = ve khong seed nao sinh ra (cach cu)."""
import os, re, glob, gzip, math, datetime as dt
import numpy as np, pandas as pd
import lotto_common as LC

M1 = np.uint64(0x9E3779B97F4A7C15); M2 = np.uint64(0xD1B54A32D192ED03)
M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
C = 324632; N = C * 12; PER_PAIR = 1_215_000
TARGET = int(os.environ.get('TARGET') or 1); MAX_PAIRS = int(os.environ.get('MAX_PAIRS') or 12)
MODE = (os.environ.get('MODE') or 'dup').lower(); MIN_PAIRS = int(os.environ.get('MIN_PAIRS') or 2); TOP = int(os.environ.get('TOP') or 0)
EXPORT = (os.environ.get('EXPORT_LOAI') or 'false').lower() == 'true'; KEEP = int(os.environ.get('KEEP') or 10)

def next_draw():
    d = (os.environ.get('DRAW') or '').strip()
    if d: return int(d)
    # Lotto 5/35: 2 ky/ngay luc 13:00 va 21:00 (gio VN). Moc: ky 989 luc 13:00 05/11/2026.
    vn = dt.timezone(dt.timedelta(hours=7)); now = dt.datetime.now(vn)
    anchor = dt.datetime(2026, 11, 5, 13, 0, tzinfo=vn); k = 989
    n = math.floor((now - anchor).total_seconds() / (8 * 3600))   # buoc 8h/ky khong dung -> tinh theo lich
    # dem so ky da quay den now theo lich 13:00, 21:00
    slots = 0; t = anchor
    day = anchor.date()
    while True:
        for h in (13, 21):
            s = dt.datetime(day.year, day.month, day.day, h, 0, tzinfo=vn)
            if s <= anchor: continue
            if s <= now: slots += 1
            else: return max(k + slots + 1, LC.get_next_draw_id('data/all.csv'))
        day += dt.timedelta(days=1)

def mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def tid(s, d):
    with np.errstate(over='ignore'):
        m = mix(s * M1 + np.uint64(d) * M2)
        return (m % np.uint64(C)).astype(np.int64) * 12 + (mix(m) % np.uint64(12)).astype(np.int64)

D = next_draw(); print('Ky tiep theo:', D)
b = LC.build_binom(); lut = LC.build_rank_to_mask(b)
def dec(v):
    mk = lut[v // 12]; return '-'.join(f'{x:02d}' for x in range(1, 36) if mk >> (x - 1) & 1) + f' + {v % 12 + 1:02d}'

USE = int(os.environ.get('USE_PAIRS') or 47)   # gioi han: chi dung N cap MOI NHAT (d1 lon nhat); 0 = khong gioi han
files = sorted(glob.glob('inverse/first2_*_*.txt.gz'), key=lambda f: -int(re.search(r'first2_(\d+)_', f).group(1)))
if USE > 0: files = files[:USE]
files = sorted(files)
pairs = []; data = {}; cnt = np.zeros(N, np.int32); pcnt = np.zeros(N, np.int32); nseed = 0
for f in files:
    a, bb = [int(x) for x in re.search(r'first2_(\d+)_(\d+)', f).groups()]; pairs.append((a, bb))
    s = pd.read_csv(f, sep=' ', header=None, usecols=[0], dtype={0: np.uint64})[0].to_numpy()
    data[(a, bb)] = s; nseed += len(s); t_ = tid(s, D); cnt += np.bincount(t_, minlength=N).astype(np.int32)
    pcnt[np.unique(t_)] += 1   # moi cap chi tinh 1 lan cho moi ve -> pcnt = so CAP khac nhau cung sinh ra ve do
S4 = set()
for f in glob.glob('inverse/all_*_r*_*[0-9].txt'):
    for l in open(f):
        p = l.split()
        if len(p) == 3 and p[0].isdigit(): S4.add(int(p[0]))
excl = cnt > 0
if S4:
    t4 = tid(np.array(sorted(S4), dtype=np.uint64), D); excl[t4] = True
    pcnt[np.unique(t4)] += 1   # seed 4 hit = 1 nguon them
if MODE == 'old':
    rem = np.nonzero(~excl)[0]                      # cach cu: ve khong seed nao sinh ra
else:
    rem = np.nonzero(pcnt >= MIN_PAIRS)[0]          # cach moi: ve bi loai vi seed cua >= MIN_PAIRS cap trung nhau
    if TOP > 0 and len(rem) > TOP:
        rem = rem[np.argsort(-pcnt[rem], kind='stable')[:TOP]]
    rem = rem[np.argsort(-pcnt[rem], kind='stable')]  # nhieu cap trung nhat len dau
R = len(rem)
os.makedirs('ve_con_lai', exist_ok=True)
with open(f've_con_lai/con_lai_{D}.txt', 'w') as o:
    for v in rem: o.write(dec(int(v)) + ('' if MODE == 'old' else f' | {int(pcnt[v])} cap') + '\n')
# ---- Muc 1 / Muc 2 tinh RIENG TUNG CAP (khong xet cap khac) ------------------------------------
# muc 1 = ve do DUNG 1 seed cua cap do sinh ra; muc 2 = ve do DUNG 2 seed cua cap do sinh ra.
# Chi tiet (rat lon) ghi vao out_muc/muc_theo_cap_<ky>.txt.gz (workflow day len Release, KHONG commit); bang dem theo cap ghi vao ve_con_lai/.
rank_str = []
for r in range(C):
    mk = lut[r]; rank_str.append('-'.join(f'{x:02d}' for x in range(1, 36) if mk >> (x - 1) & 1))
sp_str = [f' + {i + 1:02d}' for i in range(12)]
os.makedirs('out_muc', exist_ok=True); per_stats = []
class _Null:
    def write(self, *a): pass
    def writelines(self, *a): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
# da co asset tren Release (release_assets.txt do workflow ghi) -> khong sinh lai file chi tiet, chi dem
_have = os.path.exists('release_assets.txt') and f'muc_theo_cap_{D}.txt.gz' in open('release_assets.txt').read().split()
if _have: print('muc_theo_cap da co tren Release, bo qua ghi chi tiet')
with (_Null() if _have else gzip.open(f'out_muc/muc_theo_cap_{D}.txt.gz', 'wt')) as o:
    o.write(f'# ky {D}: moi cap RIENG - muc 1 = ve do DUNG 1 seed cua cap do; muc 2 = DUNG 2 seed cua cap do (khong xet cap khac)\n# cap | muc | ve | seed(s)\n')
    for pr in sorted(data):
        sd_ = data[pr]; t = tid(sd_, D); od = np.argsort(t, kind='stable'); ts = t[od]; ss = sd_[od]
        st = np.flatnonzero(np.concatenate(([True], ts[1:] != ts[:-1]))); cn = np.diff(np.concatenate((st, [len(ts)])))
        i1 = st[cn == 1]; i2 = st[cn == 2]; pk = f'{pr[0]}:{pr[1]}'
        o.writelines(f'{pk} | 1 | {rank_str[int(ts[i]) // 12]}{sp_str[int(ts[i]) % 12]} | {int(ss[i])}\n' for i in i1)
        o.writelines(f'{pk} | 2 | {rank_str[int(ts[i]) // 12]}{sp_str[int(ts[i]) % 12]} | {int(ss[i])},{int(ss[i + 1])}\n' for i in i2)
        per_stats.append((pk, len(i1), len(i2)))
tot1 = sum(x[1] for x in per_stats); tot2 = sum(x[2] for x in per_stats)
os.makedirs('ve_con_lai', exist_ok=True)
with open(f've_con_lai/muc_theo_cap_{D}.txt', 'w') as o:
    o.write(f'# ky {D}: so ve muc 1 / muc 2 cua TUNG CAP (chi tiet ve: out_muc/muc_theo_cap_{D}.txt.gz tren Release)\n# cap | muc1 | muc2\n')
    for pk, a1, a2 in per_stats: o.write(f'{pk} | {a1} | {a2}\n')
if EXPORT:
    with gzip.open(f've_con_lai/loai_{D}.txt.gz', 'wt') as o:
        for v in np.nonzero(excl)[0]: o.write(dec(int(v)) + '\n')
# de xuat quet them
queue = ''
if MODE == 'old' and R > TARGET:
    extra = N * math.log(R / TARGET); need = max(1, min(MAX_PAIRS, math.ceil(extra / PER_PAIR)))
    done = set(pairs); low = [a for a, _ in pairs if a >= 100]; m = min(low) if low else 0
    cand = []; d = m - 2
    while len(cand) < need and d >= 17:
        if (d, d + 1) not in done: cand.append(f'{d}:{d+1}')
        d -= 2
    queue = ','.join(cand)
exp = N * math.exp(-(nseed + len(S4)) / N)
txt = [f'Ky {D} | {len(pairs)} cap | {nseed + len(S4):,} seed (gom {len(S4)} seed 4 hit)',
       (f'Ve bi loai: {int(excl.sum()):,} / {N:,} | CON LAI: {R:,} (ky vong theo cong thuc ~{exp:.1f})' if MODE == 'old' else
        f'Ve bi loai: {int(excl.sum()):,} / {N:,} | CON LAI = ve bi loai do seed trung >= {MIN_PAIRS} cap: {R:,}' + (f' (giu TOP {TOP})' if TOP > 0 else '') + f' | nhieu cap nhat: {int(pcnt.max())} cap'),
       f'{len(pairs)} cap moi nhat (gioi han {USE}) | muc 1 theo cap: {tot1:,} ve | muc 2 theo cap: {tot2:,} ve | cap quet them de xuat: {queue or "khong can (da <= " + str(TARGET) + " ve)"}',
       'Luu y: ve con lai chi la ket qua loc theo seed, khong co xac suat trung cao hon ve khac (1/3.895.584 moi ve).']
open(f've_con_lai/thong_ke_{D}.txt', 'w').write('\n'.join(txt) + '\n'); print('\n'.join(txt))
# don file cu
for pre in ('con_lai_', '1_2_seed_', 'muc1_', 'muc2_', 'muc_theo_cap_', 'thong_ke_', 'loai_'):
    fs = sorted(glob.glob(f've_con_lai/{pre}*'), key=lambda x: int(re.search(r'_(\d+)\.', x).group(1)))
    for f in fs[:-KEEP]: os.remove(f)
go = os.environ.get('GITHUB_OUTPUT')
if go:
    with open(go, 'a') as o: o.write(f'draw={D}\nremaining={R}\nnext_queue={queue}\n')
