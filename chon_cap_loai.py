#!/usr/bin/env python3
# CHON CAP DE LOAI VE CON LAI (du doan CAP "khong trung" thay vi du doan seed / ve)
# Dung: python3 chon_cap_loai.py lotto535|mega THU_MUC_GZ [KY_DICH]
#   env: TARGET=10 (so ve con lai mong muon)  HIST=0 (so ky lich su toi da, 0 = tat ca; mega nen dat 60-100)
#        MAXLIST=300 (so ve ghi ra)  MINPAIRS=2 (so cap toi thieu de backtest)
# Y tuong: cap "trung" ky D neu BAT KY seed nao cua cap sinh dung ve that cua ky D (ve that bi loai oan).
#   Moi cap: lich su trung/khong trung o MOI ky sau cap -> uoc luong P(cap trung ky dich) -> chon cap P thap nhat,
#   cong dan loai ve cua seed cap do cho toi khi con <= TARGET ve.
# Backtest di-ngang (walk-forward) so sanh voi muc ngau nhien de biet lich su cap co du bao duoc khong.
import sys, os, re, glob, csv, json, math
import numpy as np, pandas as pd
from math import comb
game, gzdir = sys.argv[1], sys.argv[2]
LOTTO = game == 'lotto535'
TARGET = int(os.environ.get('TARGET') or 10); HIST = int(os.environ.get('HIST') or 0)
MAXLIST = int(os.environ.get('MAXLIST') or 300); MINPAIRS = int(os.environ.get('MINPAIRS') or 2); KEEP = int(os.environ.get('KEEP') or 0)
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
csvf = 'data/all.csv' if LOTTO else 'data/mega_all.csv'
def _rank(nums): return sum(comb(n - 1, i + 1) for i, n in enumerate(sorted(nums)))
RES = {}
for r in csv.DictReader(open(csvf, encoding='utf-8', newline='')):
    if (r.get('draw_id') or '').isdigit() and (not LOTTO or r.get('product') == 'lotto535'):
        try:
            j = json.loads(r['result_json']); rk = _rank(j['numbers'])
            RES[int(r['draw_id'])] = rk * 12 + int(j['special_numbers'][0]) - 1 if LOTTO else rk
        except Exception: pass
N = int(sys.argv[3]) if len(sys.argv) > 3 else max(RES) + 1
pat = re.compile(r'first2_(?:mega_)?(\d+)_(\d+)\.txt\.gz$')
PAIRS = {}; HISTORY = {}; TN = {}               # (a,b) -> so seed | lich su cap x ky | id ve cua cap o ky dich (int32, nhe RAM)
files = [(int(m.group(1)), int(m.group(2)), f) for f in sorted(glob.glob(os.path.join(gzdir, '*.txt.gz'))) for m in [pat.search(f)] if m]
for i, (a, b, f) in enumerate(files):
    d = pd.read_csv(f, sep=' ', header=None, usecols=[0, 1], dtype={0: np.uint64, 1: np.int32}, engine='c')
    s = d[0].to_numpy()[d[1].to_numpy() >= 2]        # giu ca seed da trung them de lich su cap day du
    del d
    if not len(s): continue
    lo = b + 1 if not HIST else max(b + 1, N - HIST)
    # LICH SU DAY DU: cap x ky -> cap co sinh dung ve that cua ky do khong (1/0)
    HISTORY[(a, b)] = {D: int((tid(s, D) == RES[D]).any()) for D in range(lo, N) if D in RES}
    TN[(a, b)] = tid(s, N).astype(np.int32); PAIRS[(a, b)] = len(s)
    if (i + 1) % 25 == 0: print(f'  {i + 1}/{len(files)} cap', flush=True)
print(f'{game}: {len(PAIRS)} cap, ky dich {N}, {sum(PAIRS.values()):,} seed', flush=True)
if not PAIRS: sys.exit('khong co cap')
prior = {p: 1 - math.exp(-n / CT) for p, n in PAIRS.items()}   # P(cap trung 1 ky) neu ngau nhien (do phu cua cap)
def pcover(p, before, K=20.0):                  # uoc luong co lam tron ve prior, chi dung lich su TRUOC ky 'before'
    h = [v for D, v in HISTORY[p].items() if D < before]
    return (sum(h) + K * prior[p]) / (len(h) + K), len(h)
# ---- BACKTEST di-ngang: tai moi ky D, xep cap theo P(trung) tang dan, xem cap xep dau co thuc su it trung hon khong
rows = []; z_num = z_den = 0.0
for D in sorted({D for h in HISTORY.values() for D in h}):
    av = [p for p in PAIRS if p[1] < D and D in HISTORY[p]]
    if len(av) < MINPAIRS: continue
    sc = sorted(av, key=lambda p: pcover(p, D)[0]); k = max(1, len(av) // 2); top = sc[:k]
    obs = sum(HISTORY[p][D] for p in top); exp = sum(prior[p] for p in top); var = sum(prior[p] * (1 - prior[p]) for p in top)
    rows.append((D, len(av), k, obs, round(exp, 2))); z_num += obs - exp; z_den += var
z = z_num / math.sqrt(z_den) if z_den > 0 else float('nan')
# ---- CHON CAP cho ky dich: P(trung) thap nhat truoc, cong dan loai ve cho toi khi con <= TARGET
KNOWN = N in RES                                # ky dich da co ket qua that -> LOAI CUNG cac cap co seed trung ky do (khong chon cap nao trung)
HITN = {p: bool((TN[p] == RES[N]).any()) for p in PAIRS} if KNOWN else {}
order = [p for p in sorted(PAIRS, key=lambda p: pcover(p, N)[0]) if not HITN.get(p)]
surv = math.exp(sum(math.log(1 - pcover(p, N)[0]) for p in order[:0]))
alive = np.ones(CT, dtype=bool); chosen = []
for p in order:
    alive[TN[p]] = False; chosen.append(p)
    if (KEEP and len(chosen) >= KEEP) or (not KEEP and alive.sum() <= TARGET): break
rem = np.flatnonzero(alive); surv = math.exp(sum(math.log(1 - pcover(p, N)[0]) for p in chosen))
real_in = bool(alive[RES[N]]) if KNOWN else None
left_est = CT * math.exp(-sum(PAIRS.values()) / CT)
out = f'chon_cap_loai_{game}_{N}.txt'
with open(out, 'w', encoding='utf-8') as f:
    f.write(f'# CHON CAP LOAI VE | {game} ky {N} | {len(PAIRS)} cap co du lieu | chon {len(chosen)} cap | CON LAI {len(rem):,} ve (muc tieu {TARGET})\n')
    if KNOWN: f.write(f'# KY {N} DA CO KET QUA: loai cung {sum(HITN.values())} cap co seed trung ky nay; {len(chosen)} cap chon deu KHONG co seed nao trung | ve that con trong danh sach: {real_in}\n')
    else: f.write(f'# KY {N} CHUA CO KET QUA: khong the biet truoc cap nao trung. Xac suat uoc luong {len(chosen)} cap chon deu khong chua ve that = {surv:.2e} (~ so ve con lai / tong ve)\n')
    if len(rem) > TARGET:
        f.write(f'# CHUA DU CAP: can them cap de con <= {TARGET} ve (uoc luong voi toan bo cap hien co: ~{left_est:,.1f} ve). Quet them cap bang scan_inverse_first2.\n')
    f.write(f'# BACKTEST di-ngang ({len(rows)} ky): cap xep dau ("se khong trung") thuc te trung {int(z_num + sum(r[4] for r in rows))} lan, ngau nhien ky vong {sum(r[4] for r in rows):.1f} | z = {z:+.2f} (|z|<2: khong khac ngau nhien)\n')
    f.write('# cap | P(trung ky dich) uoc luong | so ky lich su | so lan cap da trung\n')
    for p in chosen:
        pc, n = pcover(p, N); f.write(f'{p[0]}_{p[1]} | {pc:.3f} | {n} | {sum(HISTORY[p].values())}\n')
    f.write(f'# ve con lai (toi da {MAXLIST})\n')
    for v in rem[:MAXLIST]: f.write(dec(v) + '\n')
hist = f'cap_lich_su_{game}.txt'
with open(hist, 'w', encoding='utf-8') as f:
    f.write('# LICH SU CAP: moi dong = cap | so seed | ky cap da sinh dung ve that (cap trung)\n')
    for p in sorted(HISTORY):
        f.write(f'{p[0]}_{p[1]} | {PAIRS[p]} | {",".join(str(D) for D, v in sorted(HISTORY[p].items()) if v) or "-"}\n')
print(f'chon {len(chosen)}/{len(PAIRS)} cap, con lai {len(rem):,} ve | backtest {len(rows)} ky, z={z:+.2f} | -> {out}, {hist}')

# ---- KE HOACH QUET: cap con thieu de co lich su day du + cap moi khi co ket qua moi nhat; danh sach cap GIU / BO
latest = max(RES); A = sorted(a for a, b in PAIRS); step = 2
plan = f'cap_ke_hoach_{game}.txt'
with open(plan, 'w', encoding='utf-8') as f:
    f.write(f'# KE HOACH CAP | {game} | ket qua moi nhat: ky {latest} | dang co {len(PAIRS)} cap ({A[0]}_{A[0]+1} .. {A[-1]}_{A[-1]+1})\n')
    nxt = A[-1] + step
    f.write(f'# CAP MOI: ' + (f'{nxt}_{nxt+1} (da du ket qua ky {nxt+1}, can quet)' if nxt + 1 <= latest else f'{nxt}_{nxt+1} cho ket qua ky {nxt+1} (moi nhat la {latest}), chua quet duoc') + '\n')
    old = list(range(A[0] - step, 0, -step))
    if KEEP and len(PAIRS) < KEEP: old = old[:KEEP - len(PAIRS)]
    f.write(f'# CAP CON THIEU de co lich su day du / du {KEEP or "tat ca"} cap: {len(old)} cap, quet tu {old[0] if old else "-"}_{old[0]+1 if old else "-"} xuong (workflow scan_inverse_auto_prune hoac scan_inverse_first2)\n')
    f.write(f'# CHON cho ky {N}: {len(chosen)} cap (P(trung) thap nhat, khong co seed trung ky da biet; ky khac se chon bo khac):\n' + ' '.join(f'{p[0]}_{p[1]}' for p in sorted(chosen)) + '\n')
    f.write('# LUU Y: 400 cap duoc chon LAI moi ky nen PHAI GIU DAY DU tat ca cap, khong bo cap nao khoi Release.\n')
print('ke hoach ->', plan)
