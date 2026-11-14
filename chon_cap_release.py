#!/usr/bin/env python3
# CHON CAP TRUOC -> CHI TAI cap duoc chon -> VE CON LAI = DU DOAN
#   python3 chon_cap_release.py lotto535|mega NGUON [KY_DICH]
#   NGUON = thu muc gz tren may (de thu)  hoac  TAG Release (tai bang `gh release download`, xong xoa ngay)
# Quy trinh:
#   1. Lay DANH SACH cap + kich thuoc tu Release (khong tai seed).
#   2. Xep cap: P(trung) tu bang lich su nho (chon_cap/cap_lich_su_<game>.txt) neu co, hoa nhau bang bam (cap, ky) -> moi ky chon bo cap khac nhau.
#   3. Duyet theo thu tu: CHI TAI cap do. Neu ky dich da co ket qua va cap co seed sinh dung ve that -> bo cap, lay cap tiep (khong chon cap trung).
#      Cap duoc chon -> loai ve cua seed cap do khoi tap ve; cap hoan tat thi xoa gz tai ve ngay.
#   4. Dung khi da chon >= KEEP cap VA con <= TARGET ve (khong du cap thi chon het).
#   5. VE CON LAI (khong chon cap nao sinh ra) = DU DOAN, ghi du_doan/<game>_<ky>.txt (cung dinh dang du_doan_100.py).
# env: KEEP(400/40) TARGET(10) HIST(40) MAXLIST(300) WORK(gzwork) DU_DOAN(1)
import sys, os, re, glob, csv, json, math, subprocess, hashlib, shutil
import numpy as np, pandas as pd
from math import comb
game, src = sys.argv[1], sys.argv[2]
LOTTO = game == 'lotto535'
KEEP = int(os.environ.get('KEEP') or (40 if LOTTO else 400)); TARGET = int(os.environ.get('TARGET') or 10)
HIST = int(os.environ.get('HIST') or 40); MAXPRED = int(os.environ.get('MAXPRED') or 100); MAXLIST = int(os.environ.get('MAXLIST') or 300)
WORK = os.environ.get('WORK') or 'gzwork'; DU_DOAN = (os.environ.get('DU_DOAN') or '1') == '1'
MOD = 324632 if LOTTO else 8145060; CT = MOD * 12 if LOTTO else MOD
M1 = np.uint64(0x9E3779B97F4A7C15); M2 = 0xD1B54A32D192ED03; M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
def _mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def tid(s, d):
    with np.errstate(over='ignore'):
        m = _mix(s * M1 + np.uint64((d * M2) & ((1 << 64) - 1))); r = (m % np.uint64(MOD)).astype(np.int64)
        return r * 12 + (_mix(m) % np.uint64(12)).astype(np.int64) if LOTTO else r
if LOTTO:
    import lotto_common as LC
    _lut = LC.build_rank_to_mask(LC.build_binom())
    def dec(v):
        r, sp = divmod(int(v), 12); m = _lut[r]
        return '-'.join(f'{x:02d}' for x in range(1, 36) if m >> (x - 1) & 1) + f' + {sp + 1:02d}'
else:
    _T = [np.array([comb(i, j) if i >= j else 0 for i in range(46)], dtype=np.int64) for j in range(7)]
    def dec(v):
        r = int(v); out = []
        for j in range(6, 0, -1):
            x = int(np.searchsorted(_T[j], r, side='right')) - 1; out.append(x + 1); r -= int(_T[j][x])
        return '-'.join(f'{x:02d}' for x in sorted(out))
def _rank(nums): return sum(comb(n - 1, i + 1) for i, n in enumerate(sorted(nums)))
RES = {}
for r in csv.DictReader(open('data/all.csv' if LOTTO else 'data/mega_all.csv', encoding='utf-8', newline='')):
    if (r.get('draw_id') or '').isdigit() and (not LOTTO or r.get('product') == 'lotto535'):
        try:
            j = json.loads(r['result_json']); rk = _rank(j['numbers'])
            RES[int(r['draw_id'])] = rk * 12 + int(j['special_numbers'][0]) - 1 if LOTTO else rk
        except Exception: pass
latest = max(RES); N = int(sys.argv[3]) if len(sys.argv) > 3 else latest + 1; KNOWN = N in RES
if os.path.exists(f'du_doan/{game}_{N}.txt') and os.environ.get('FORCE') != '1':   # da co du doan ky moi nhat -> KHONG tai Release
    print(f'{game} ky {N}: da co du_doan/{game}_{N}.txt -> bo qua (khong tai Release). FORCE=1 de chay lai'); sys.exit(0)
pat = re.compile(r'^first2_(?:mega_)?(\d+)_(\d+)\.txt\.gz$')
# ---- 1. danh sach cap (khong tai seed)
ISDIR = os.path.isdir(src); SIZE = {}
if ISDIR:
    for f in os.listdir(src):
        m = pat.match(f)
        if m: SIZE[(int(m.group(1)), int(m.group(2)))] = os.path.getsize(os.path.join(src, f))
else:
    out = subprocess.run(['gh', 'release', 'view', src, '--json', 'assets', '-q', '.assets[]|"\\(.name) \\(.size)"'], capture_output=True, text=True, check=True).stdout
    for l in out.split('\n'):
        a = l.split()
        if len(a) == 2 and pat.match(a[0]):
            m = pat.match(a[0]); SIZE[(int(m.group(1)), int(m.group(2)))] = int(a[1])
if not SIZE: sys.exit('khong co cap tren nguon')
def fetch(p):
    name = f'first2_{p[0]}_{p[1]}.txt.gz' if LOTTO else f'first2_mega_{p[0]}_{p[1]}.txt.gz'
    if ISDIR: return os.path.join(src, name), False
    os.makedirs(WORK, exist_ok=True); path = os.path.join(WORK, name)
    subprocess.run(['gh', 'release', 'download', src, '--pattern', name, '--dir', WORK, '--clobber'], check=True, capture_output=True)
    return path, True
def seeds_of(path):
    d = pd.read_csv(path, sep=' ', header=None, usecols=[0, 1], dtype={0: np.uint64, 1: np.int32}, engine='c')
    return d[0].to_numpy()[d[1].to_numpy() >= 2]
# ---- 2. bang lich su nho (cap -> cac ky cap da sinh dung ve that); cap chua co lich su dung prior theo kich thuoc
HF = f'chon_cap/cap_lich_su_{game}.txt'; DB = {}
if os.path.exists(HF):
    for l in open(HF, encoding='utf-8'):
        a = [x.strip() for x in l.split('|')]
        if len(a) >= 5 and re.fullmatch(r'\d+_\d+', a[0]):
            DB[tuple(map(int, a[0].split('_')))] = dict(n=int(a[1]), cov={int(x) for x in a[2].split(',') if x.isdigit()}, thru=int(a[3]), lo=int(a[4]))
avg = np.mean(list(SIZE.values()))
NAVG = 1214316 if LOTTO else 278234
def prior(p): return 1 - math.exp(-(DB[p]['n'] if p in DB else NAVG * SIZE[p] / avg) / CT)
def pcover(p, before=None, K=20.0):
    pr = prior(p)
    if p not in DB: return pr
    dd = [D for D in range(DB[p]['lo'], DB[p]['thru'] + 1) if before is None or D < before]
    return (sum(1 for D in dd if D in DB[p]['cov']) + K * pr) / (len(dd) + K)
def tie(p): return hashlib.md5(f'{p[0]}_{p[1]}_{N}'.encode()).hexdigest()
order = sorted(SIZE, key=lambda p: (round(pcover(p, N), 6), tie(p)))
# ---- 3. duyet: chi tai cap duoc xet; cap trung ky da biet bi bo
alive = np.ones(CT, dtype=bool); TRAJ = []; chosen = []; skipped_hit = []; downloaded = 0
def update_hist(p, s):
    b = p[1]; lo = b + 1 if not HIST else max(b + 1, latest - HIST + 1)
    old = DB.get(p); start = max(lo, old['thru'] + 1) if old else lo
    cov = set(old['cov']) if old else set()
    for D in range(start, latest + 1):
        if D in RES and (tid(s, D) == RES[D]).any(): cov.add(D)
    DB[p] = dict(n=len(s), cov=cov, thru=max(latest, old['thru'] if old else 0), lo=old['lo'] if old else lo)
for p in order:
    if len(chosen) >= KEEP and (TARGET == 0 or np.count_nonzero(alive) <= TARGET): break   # TARGET=0: KHONG rang buoc so ve, chi chon dung KEEP cap
    path, tmp = fetch(p); s = seeds_of(path); downloaded += 1
    try:
        update_hist(p, s)
        if KNOWN and (tid(s, N) == RES[N]).any(): skipped_hit.append(p); continue
        alive[tid(s, N)] = False; chosen.append(p); TRAJ.append((len(chosen), int(np.count_nonzero(alive))))
    finally:
        if tmp: os.remove(path)
rem = np.flatnonzero(alive); real_in = bool(alive[RES[N]]) if KNOWN else None
surv = math.exp(sum(math.log(1 - pcover(p, N)) for p in chosen))
# ---- 4a. BANG K -> so ve con lai -> xac suat trung: K cang lon, ve cang it, xac suat trung (= ve con lai / tong ve) cang nho
with open(f'chon_cap/bang_k_{game}_{N}.txt', 'w', encoding='utf-8') as f:
    f.write(f'# {game} ky {N}: so cap da chon K | so ve con lai R | xac suat ve that nam trong R ve (ngau nhien) = R / {CT:,} ve\n')
    for k, r in TRAJ:
        if k <= 5 or k % 5 == 0 or k == len(chosen): f.write(f'{k} | {r:,} | {r / CT:.2e}\n')
# ---- 4. ghi lich su + ket qua
os.makedirs('chon_cap', exist_ok=True)
with open(HF, 'w', encoding='utf-8') as f:
    f.write('# LICH SU CAP: cap | so seed | ky cap da sinh dung ve that | da kiem tra den ky | ky bat dau tinh (chi cap da tung duoc chon/tai)\n')
    for p in sorted(DB):
        f.write(f"{p[0]}_{p[1]} | {DB[p]['n']} | {','.join(map(str, sorted(DB[p]['cov']))) or '-'} | {DB[p]['thru']} | {DB[p]['lo']}\n")
note = (f'KY {N} DA CO KET QUA: bo {len(skipped_hit)} cap co seed trung ky nay; ve that con trong danh sach: {real_in}' if KNOWN else
        f'KY {N} CHUA CO KET QUA: khong the biet truoc cap nao trung; xac suat {len(chosen)} cap chon deu khong chua ve that ~ {surv:.2e}')
out = f'chon_cap/chon_cap_loai_{game}_{N}.txt'
for old in glob.glob(f'chon_cap/chon_cap_loai_{game}_*.txt'): os.remove(old)
with open(out, 'w', encoding='utf-8') as f:
    f.write(f'# CHON CAP LOAI VE | {game} ky {N} | {len(SIZE)} cap tren Release | chon {len(chosen)} cap (chi tai {downloaded}) | CON LAI {len(rem):,} ve ({'khong rang buoc so ve' if TARGET == 0 else f'muc tieu {TARGET}'})\n# {note}\n')
    if TARGET and len(rem) > TARGET: f.write(f'# CHUA DU CAP: can them cap de con <= {TARGET} ve\n')
    f.write('# cap | P(trung) uoc luong\n')
    for p in chosen: f.write(f'{p[0]}_{p[1]} | {pcover(p, N):.3f}\n')
    f.write(f'# ve con lai (toi da {MAXLIST})\n')
    for v in rem[:MAXLIST]: f.write(dec(v) + '\n')
# ---- 5. DU DOAN = ve con lai (khong chon cap nao sinh ra)
if DU_DOAN:
    cap = MAXPRED if TARGET == 0 else TARGET
    pick = rem if len(rem) <= cap else rem[np.linspace(0, len(rem) - 1, cap).astype(np.int64)]
    os.makedirs('du_doan', exist_ok=True)
    with open(f'du_doan/{game}_{N}.txt', 'w', encoding='utf-8') as f:
        f.write(f'# Ky {N} ({game}): {len(pick)} ve du doan = VE CON LAI sau khi loai ve cua {len(chosen)} cap duoc chon (cap khong trung) | ve con lai: {len(rem):,}\n')
        f.write(f'# nguon: con_lai {len(pick)} | {note}. Moi ve chi co xac suat ngau nhien 1/{CT // 12 * 12 if LOTTO else CT:,}.\n# ve | nguon | chi tiet\n')
        for v in pick: f.write(f'{dec(v)} | con_lai | khong seed nao cua {len(chosen)} cap chon sinh ra\n')
print(f'{game} ky {N}: chon {len(chosen)} cap (tai {downloaded}/{len(SIZE)}), bo {len(skipped_hit)} cap trung, con lai {len(rem):,} ve, ve that con: {real_in} -> {out}')
