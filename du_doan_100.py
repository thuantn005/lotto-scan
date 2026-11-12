#!/usr/bin/env python3
"""Chon DUNG 100 ve du doan cho ky tiep theo (Lotto 5/35 hoac Mega 6/45) va luu vao du_doan/<game>_<ky>.txt.
  python3 du_doan_100.py GAME THU_MUC_GZ        GAME = lotto535 | mega      (so ve: env TARGET_N, mac dinh 10)
Thu tu uu tien (dedupe, du 100 thi dung):
  1) THEO TUNG CAP, CHIA THEO SO LIEU seed_state/hits_<game>.tsv (SPLIT=prob, mac dinh; SPLIT=equal de chia deu): so ve cua cap ~ (so seed muc>=1 cua cap trong tsv) / (seed cua cap x ky da qua sau d2).
     CHON SEED THEO MUC: chi lay ve do DUNG MUC seed cua cap cung sinh ra (env MUC, mac dinh 1; MUC=0 de khong loc theo muc). Thong ke muc (47 cap, moi ky sau cap toi ky 1000): ve trung that o muc 1 = 1,07x ngau nhien (khong co y nghia thong ke).
     Trong cap lay NGAU NHIEN (co dinh theo ky) trong cac seed CHI HIT DUNG 2 KY (cap d1,d2) thoa muc tren; seed trung them bat ky ky nao sau d2 (vd 995) bi LOAI - kiem tra truc tiep voi ket qua that
     (gz + scan_state cho so ky luc quet). Ve trung giua cac cap -> lay ve ke tiep cua cap. Env PER_PAIR (150) = so ung vien du phong/cap.
  2) neu thieu: ve CON LAI = ve con lai trong TO HOP sau khi LOAI moi ve ma seed cua cac cap (USE_PAIRS cap) sinh ra (seed ve nao trung thi loai); lay mau co dinh theo ky (rng seed = ky).
   REM_MODE=dup: cach khac - ve con lai = ve bi seed trung >= MIN_PAIRS cap.
3) neu van thieu: ve it seed nhat (do boi 1 seed, roi 2 seed, ...)
Luon xuat DU TARGET_N ve. Muc/seed chi la thong ke: moi ve van chi co xac suat ngau nhien."""
import os, sys, re, glob, json, csv
import numpy as np, pandas as pd
from math import comb
game, gzdir = sys.argv[1], sys.argv[2]
LOTTO = game == 'lotto535'; NEED = int(os.environ.get('TARGET_N') or 10); USE = int(os.environ.get('USE_PAIRS') or (47 if LOTTO else 0))
KEEP = int(os.environ.get('KEEP_DU_DOAN') or 30)
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
ids = [int(r['draw_id']) for r in csv.DictReader(open(csvf, encoding='utf-8', newline='')) if (r.get('draw_id') or '').isdigit() and (not LOTTO or r.get('product') == 'lotto535')]
N = max(ids) + 1
def _rank(nums): return sum(comb(n - 1, i + 1) for i, n in enumerate(sorted(nums)))
RES = {}                                         # ky -> id ve KET QUA THAT (de loai seed da trung them sau cap)
for r in csv.DictReader(open(csvf, encoding='utf-8', newline='')):
    if (r.get('draw_id') or '').isdigit() and (not LOTTO or r.get('product') == 'lotto535'):
        try:
            j = json.loads(r['result_json']); rk = _rank(j['numbers'])
            RES[int(r['draw_id'])] = rk * 12 + int(j['special_numbers'][0]) - 1 if LOTTO else rk
        except Exception: pass
SCAN_N = {}                                      # cap -> so ky luc quet (gz chi biet hit toi ky do)
for fn in glob.glob('scan_state/first2_*.txt'):
    mm = re.search(r'first2_(?:mega_)?(\d+)_(\d+)\.txt$', fn)
    if mm:
        for l in open(fn, encoding='utf-8', errors='ignore'):
            q = re.search(r'tren (\d+) ky', l)
            if l.startswith('Phan bo so hit') and q: SCAN_N[(int(mm.group(1)), int(mm.group(2)))] = int(q.group(1)); break
nlate = 0
pat = re.compile(r'first2_(?:mega_)?(\d+)_(\d+)\.txt\.gz$'); files = []
for f in glob.glob(os.path.join(gzdir, '*.txt.gz')):
    m = pat.search(f)
    if m: files.append((int(m.group(1)), int(m.group(2)), f))
files.sort(key=lambda p: -p[0])
if USE > 0 and LOTTO:      # cap LIEN TIEP: (N-2,N-1), (N-3,N-2), ... USE cap (N = ky sap quay); cap nao thieu thi bo qua
    want = {(N - 1 - k - 1, N - 1 - k) for k in range(USE)}
    miss = sorted(want - {(a, b) for a, b, _ in files}, reverse=True)
    if miss: print('CANH BAO thieu cap lien tiep:', miss)
    files = [x for x in files if (x[0], x[1]) in want]
elif USE > 0: files = files[:USE]
cnt = np.zeros(CT, dtype=np.int32); pcnt = np.zeros(CT, dtype=np.int32); nseed = 0; nseed2 = 0
PERPAIR = int(os.environ.get('PER_PAIR') or 150); percand = []
later = np.array([], dtype=np.uint64)   # seed da trung them sau d2 (hit >= 3) theo seed_state
MUC = int(os.environ.get('MUC') or 1); tsvn = {}   # tsvn: cap -> so seed muc>=1 trong hits tsv (so lieu chia ve)
hf0 = f'seed_state/hits_{game}.tsv'
if os.path.exists(hf0):
    later = np.array([int(l.split('\t')[0]) for l in open(hf0) if l.count('\t') == 2 and l.rstrip('\n').split('\t')[2].strip()], dtype=np.uint64)
    for l in open(hf0):
        a_ = l.rstrip('\n').split('\t')
        if len(a_) == 3 and a_[2].strip(): tsvn[a_[1]] = tsvn.get(a_[1], 0) + 1
wseeds = []
for a, b, f in files:
    d = pd.read_csv(f, sep=' ', header=None, usecols=[0, 1], dtype={0: np.uint64, 1: np.int32}, engine='c')
    s = d[0].to_numpy(); h = d[1].to_numpy(); t = tid(s, N)
    wseeds.append(s); nseed += len(s); cp = np.bincount(t, minlength=CT); cnt += cp.astype(np.int32); pcnt += (cp > 0).astype(np.int32)   # cp = so seed CUA CAP sinh tung ve (muc); pcnt = so CAP khac nhau cung sinh ve do
    nl_pair = 0
    m2 = h == 2                                  # seed chi hit dung 2 ky (cap d1,d2) tinh den luc quet
    if len(later): m2 &= ~np.isin(s, later)
    for D in range(max(SCAN_N.get((a, b), b), b) + 1, N):          # seed TRUNG THEM ky nao tu sau luc quet toi nay (vd 995) -> LOAI
        if D in RES and m2.any():
            ix_ = np.flatnonzero(m2); hit_ = tid(s[ix_], D) == RES[D]; m2[ix_[hit_]] = False; nlate += int(hit_.sum()); nl_pair += int(hit_.sum())
    ix = np.flatnonzero(m2); nseed2 += len(ix)
    if MUC > 0: ix = ix[cp[t[ix]] == MUC]          # CHON SEED THEO MUC: chi ve do dung MUC seed cua cap sinh ra
    if len(ix):                                    # ung vien RIENG CUA CAP nay: lay NGAU NHIEN deu trong cac seed hit dung 2 ky (giong cach seed len hit 3: roi ngau nhien)
        rg = np.random.default_rng((N * 1000003 + a * 1009 + b) & 0xFFFFFFFF)
        pk = rg.choice(ix, size=min(len(ix), PERPAIR), replace=False)
        nconv = tsvn.get(f'{a}_{b}', 0) if tsvn else int((h >= 3).sum()) + nl_pair   # so seed muc>=1 cua cap (theo hits tsv)
        percand.append((f'{a}_{b}', [(int(t[q]), len(ix), int(s[q])) for q in pk], nconv, nconv / (len(s) * max(1, N - 1 - b))))   # so seed cua cap da len >= 3 hit (luc quet + trung them sau do)
# SEED HIT >= 3 KY (3, 4, ...) GIU VINH VIEN (seed_state/keep34_<game>.txt, du cap gz da bi xoa) -> cung dung de LOAI VE; bo seed da co trong cac cap cua so (tranh dem trung)
n34 = 0; KEEP34 = f'seed_state/keep34_{game}.txt'
if LOTTO and os.environ.get('USE_KEEP34', '1') == '1' and os.path.exists(KEEP34):
    ks_ = np.array([int(l.split('\t')[0]) for l in open(KEEP34) if l.strip() and l.split('\t')[0].isdigit()], dtype=np.uint64)
    if len(ks_) and wseeds: ks_ = ks_[~np.isin(ks_, np.concatenate(wseeds))]
    if len(ks_):
        c34 = np.bincount(tid(ks_, N), minlength=CT); cnt += c34.astype(np.int32); pcnt += (c34 > 0).astype(np.int32); n34 = len(ks_); nseed += n34
chosen = []; used = set()
nrej = 0
def valid(sd, pr):                                 # KIEM TRA CUOI: seed sinh ve phai hit DUNG 2 ky (d1,d2 cua cap) tren TOAN BO ket qua that; hit 3, 4.. ky -> bo
    global nrej
    if not sd: return True
    a_, b_ = (int(x) for x in pr.split('_')); arr = np.array([sd], dtype=np.uint64)
    hits = {D for D, r_ in RES.items() if D < N and int(tid(arr, D)[0]) == r_}
    if hits == {x for x in (a_, b_) if x in RES}: return True     # ky khong co trong csv thi khong kiem tra duoc ky do
    nrej += 1; return False
def add(v, src, det):
    if len(chosen) < NEED and int(v) not in used: used.add(int(v)); chosen.append((int(v), src, det))
# 1) CHON THEO TUNG CAP: vong 1 lay ve dung dau cua moi cap (cap moi nhat truoc), vong 2 lay ve thu 2 cua moi cap, ... den du NEED
# tieu chi cap: chi cap DA CO seed muc>=1 trong hits tsv, ti le cao nhat truoc, bang nhau thi cap moi hon; PAIR_CRIT=all de dung moi cap
if os.environ.get('PAIR_CRIT', 'conv') == 'conv': percand = [x for x in percand if x[2] > 0]      # CHI lay cap DA CO seed len >= 3 hit
percand.sort(key=lambda x: (-x[3], -int(x[0].split('_')[0])) if os.environ.get('PAIR_CRIT', 'conv') == 'conv' else -int(x[0].split('_')[0]))
# CHIA DEU: moi cap cung so ve (NEED // so cap, phan du chia cho cac cap moi nhat); ve trung giua cac cap thi lay ve ke tiep cua cap do
P = len(percand)
PICK = (os.environ.get('PICK') or ('con_lai' if LOTTO else 'seed')).lower()   # con_lai: 100 ve lay tu VE CON LAI (sau khi loai seed); seed: cach cu (seed hit dung 2 ky)
if P and PICK == 'seed':
    # CHIA THEO XAC SUAT: ti le cua cap = so seed len >= 3 hit / (so seed cua cap x so ky da qua sau d2); so ve cua cap ~ ti le (lam tron lon nhat, tong = NEED)
    if os.environ.get('SPLIT', 'prob') == 'prob' and sum(x[3] for x in percand) > 0:
        tw = sum(x[3] for x in percand); raw = [NEED * x[3] / tw for x in percand]
        quota = [int(r_) for r_ in raw]
        for k in sorted(range(P), key=lambda k: -(raw[k] - quota[k]))[:NEED - sum(quota)]: quota[k] += 1
    else:
        base, extra = divmod(NEED, P); quota = [base + (1 if k < extra else 0) for k in range(P)]
    for k, (pr, lst, nconv, rate) in enumerate(percand):
        q = quota[k]; got = 0
        for v, nsd, sd in lst:
            if got >= q: break
            if v not in used and valid(sd, pr): add(v, 'seed2hit', f'cap {pr} (da co {nconv} seed muc>=1, ti le {rate * CT:.2f}x ngau nhien, {q} ve): muc {MUC}, ngau nhien trong {nsd:,} seed hit dung 2 ky (seed {sd})'); got += 1
    for rd in range(PERPAIR):                      # con thieu (do trung ve) -> bo sung vong tron
        if len(chosen) >= NEED: break
        for pr, lst, nconv, rate in percand:
            if rd < len(lst) and lst[rd][0] not in used and valid(lst[rd][2], pr): add(lst[rd][0], 'seed2hit', f'cap {pr}: ngau nhien trong {lst[rd][1]:,} seed hit dung 2 ky cua cap (seed {lst[rd][2]})')
n_muc = len(chosen)
# 2) ve con lai = ve bi loai do seed trung cac cap (>= MIN_PAIRS cap cung sinh ra ve do)
REM_MODE = (os.environ.get('REM_MODE') or 'old').lower(); MIN_PAIRS = int(os.environ.get('MIN_PAIRS') or 2)
if REM_MODE == 'old': rem = np.flatnonzero(cnt == 0)
else:
    rem = np.flatnonzero(pcnt >= MIN_PAIRS)
    if len(rem): rem = rem[np.argsort(-pcnt[rem], kind='stable')]      # trung nhieu cap nhat len dau
n_rem_total = int(len(rem)); need = NEED - len(chosen)
SRC_TXT = 've du doan' if PICK == 'seed' else 've CON LAI'
REM_LABEL = 'khong seed nao sinh' if REM_MODE == 'old' else 'bi loai do seed trung >= %d cap' % MIN_PAIRS
if need > 0 and len(rem):
    if REM_MODE == 'old' and LOTTO and os.environ.get('SPREAD', '1') == '1' and len(rem) > need:
        # CHON 100 VE TU VE CON LAI: (1) bo ve dang 'nhieu nguoi chon' (toan so <= 31 kieu ngay sinh, day >= 3 so lien tiep, cap so cong) -> neu trung giai it phai chia;
        # (2) PHU DEU: 2 ve bat ky chung <= 2 so, moi so (1-35) xuat hien khong qua nhieu. Deu chi LOC/SAP XEP, khong doi xac suat 1/{CT} cua tung ve.
        rg_ = np.random.default_rng(N); cand = rg_.choice(rem, size=min(len(rem), 40000), replace=False); good = []
        for v in cand:
            nums = [int(x) for x in dec(int(v)).split(' + ')[0].split('-')]
            ap = len({b - a for a, b in zip(nums, nums[1:])}) == 1
            run = sum(1 for a, b in zip(nums, nums[1:]) if b - a == 1) >= 2
            if max(nums) >= 32 and not ap and not run: good.append((int(v), frozenset(nums)))
        use_cap = int(need * 5 / 35 * 1.8) + 1; sel = []; usage = {}
        for ov in (2, 3, 4):                                       # noi dan chong lan neu chua du
            for v, ns_ in good:
                if len(sel) >= need: break
                if v in {x[0] for x in sel}: continue
                if any(len(ns_ & x[1]) > ov for x in sel): continue
                if any(usage.get(n, 0) >= use_cap for n in ns_): continue
                sel.append((v, ns_))
                for n in ns_: usage[n] = usage.get(n, 0) + 1
            if len(sel) >= need: break
        pick = np.array(sorted(x[0] for x in sel), dtype=np.int64)
        if len(pick) < need:                                       # van thieu -> bo sung ngau nhien tu ve con lai
            extra = np.setdiff1d(rem, pick); pick = np.sort(np.concatenate([pick, rg_.choice(extra, size=min(len(extra), need - len(pick)), replace=False)]))
    elif REM_MODE == 'old':
        pick = np.sort(rem if len(rem) <= need else np.random.default_rng(N).choice(rem, size=need, replace=False))
    else:                                                               # lay ve trung nhieu cap nhat; cung so cap thi lay mau co dinh theo ky
        top = pcnt[rem[0]]; pick = []
        for lv in range(int(top), MIN_PAIRS - 1, -1):
            g = rem[pcnt[rem] == lv]
            if len(g) > need - len(pick): g = np.sort(np.random.default_rng(N + lv).choice(g, size=need - len(pick), replace=False))
            pick.extend(g.tolist())
            if len(pick) >= need: break
        pick = np.array(pick, dtype=np.int64)
    for v in pick: add(v, 'con_lai', 'khong seed nao sinh ra, loc it nguoi chon + phu deu' if REM_MODE == 'old' and LOTTO else 'khong seed nao sinh ra' if REM_MODE == 'old' else f'bi loai do seed trung {int(pcnt[v])} cap')
n_rem = len(chosen) - n_muc
# 3) ve it seed nhat
c = 1
while len(chosen) < NEED and c <= 200:
    for v in np.flatnonzero(cnt == c)[:NEED]: add(v, 'it_seed', f'{c} seed')
    c += 1
os.makedirs('du_doan', exist_ok=True)
out = f'du_doan/{game}_{N}.txt'
with open(out, 'w') as o:
    o.write(f'# Ky {N} ({game}): {len(chosen)} {SRC_TXT} | {len(files)} cap, {nseed:,} seed ({nseed2:,} seed hit dung 2 ky, loai {nlate} seed trung them, {nrej} seed bi loai o buoc kiem tra cuoi) | ve con lai ({REM_LABEL}): {n_rem_total:,}\n')
    o.write(f'# nguon: seed 2 hit {n_muc} | con_lai {n_rem} | it_seed {len(chosen) - n_muc - n_rem} | seed hit>=3 ky giu de loai: {n34:,}. Moi ve chi co xac suat ngau nhien 1/{CT:,}.\n# ve | nguon | chi tiet\n')
    for v, src, det in chosen: o.write(f'{dec(v)} | {src} | {det}\n')
# danh sach VE CON LAI DAY DU -> du_doan/con_lai_<game>_<ky>.txt
CLMAX = int(os.environ.get('CON_LAI_MAX') or (0 if LOTTO else 500))      # 0 = ghi DAY DU tat ca ve con lai (Lotto ~1,1 trieu ve ~25 MB/ky, giu 5 ky); >0 = chi ghi CLMAX ve dau
if n_rem_total > 0:
    lst_ = rem if CLMAX <= 0 else rem[:CLMAX]
    with open(f'du_doan/con_lai_{game}_{N}.txt', 'w') as o:
        if REM_MODE == 'old': o.write(f'# Ky {N} ({game}): {n_rem_total:,} ve CON LAI trong to hop sau khi loai ve do seed cua {len(files)} cap sinh ra; ghi {len(lst_):,} ve (danh sach day du)\n')
        else: o.write(f'# Ky {N} ({game}): {n_rem_total:,} ve CON LAI = ve bi loai do seed trung >= {MIN_PAIRS} cap (tren {len(files)} cap); ghi {len(lst_)} ve trung nhieu cap nhat | ve | so cap trung\n')
        for v in lst_: o.write(dec(v) + ('\n' if REM_MODE == 'old' else f' | {int(pcnt[v])} cap\n'))
# DANH SACH DAY DU ve con lai (rat lon, vd ~1 trieu ve) -> khong commit vao repo; ghi .gz vao CON_LAI_RELEASE_DIR de workflow day len Release
RDIR = os.environ.get('CON_LAI_RELEASE_DIR')
if RDIR and n_rem_total > 0:
    import gzip; os.makedirs(RDIR, exist_ok=True)
    with gzip.open(f'{RDIR}/con_lai_full_{game}_{N}.txt.gz', 'wt') as o:
        o.write(f'# Ky {N} ({game}): {n_rem_total:,} ve CON LAI ' + (f'(khong seed nao cua {len(files)} cap sinh ra)' if REM_MODE == 'old' else f'(bi seed trung >= {MIN_PAIRS} cap tren {len(files)} cap) | ve | so cap trung') + '\n')
        for v in rem: o.write(dec(v) + ('\n' if REM_MODE == 'old' else f' | {int(pcnt[v])} cap\n'))
    print('da ghi', f'{RDIR}/con_lai_full_{game}_{N}.txt.gz', n_rem_total)
# giu KEEP file gan nhat
KEEP_CL = int(os.environ.get('KEEP_CON_LAI') or 5)      # ve CON LAI chi giu 5 ky gan nhat (ve trung da luu vinh vien o ve_trung/)
for pre, kp in ((f'du_doan/{game}_*.txt', KEEP), (f'du_doan/con_lai_{game}_*.txt', KEEP_CL)):
    fs = sorted(glob.glob(pre), key=lambda p: int(re.search(r'_(\d+)\.txt$', p).group(1)))
    for p in fs[:-kp]: os.remove(p)
print('Phan bo so cap trung moi ve (' + str(len(files)) + ' cap): ' + ' | '.join(f'{k} cap: {int((pcnt == k).sum()):,}' for k in range(len(files) + 1)))
print(f'{game} ky {N}: {len(chosen)} ve (muc {n_muc}, con_lai {n_rem}, it_seed {len(chosen) - n_muc - n_rem}) | con lai tong {n_rem_total:,} -> {out}')
