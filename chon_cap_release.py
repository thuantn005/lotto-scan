#!/usr/bin/env python3
# CHON CAP (COT LOI) - TAI HET CAP -> NGHIEN CUU/BACKTEST -> MOI CHON CAP -> doi chieu ket qua that cua cap da chon
#   python3 chon_cap_release.py lotto535|mega NGUON [KY_DICH]
#   NGUON = thu muc gz tren may (de thu)  hoac  TAG Release (tai bang `gh release download`, xu ly xong xoa ngay)
# Cot loi la CAP, khong phai ve con lai: cap "trung" = co seed sinh dung ve that -> ve that bi loai oan -> ve con lai vo nghia.
# Quy trinh:
#   1. Lay danh sach cap tren Release, TAI HET moi cap (khong chi cap duoc chon -> khong thien lech), cap nao xu ly xong xoa gz ngay.
#      Cap nao cung duoc cap nhat lich su: moi ky da quay, cap co sinh dung ve that khong (chon_cap/cap_lich_su_<game>.txt, TAT CA cap).
#   2. NGHIEN CUU + BACKTEST MU tren lich su TOAN BO cap (nghien_cuu_chon_cap.py): so quy tac xep hang vs ngau nhien, train/test.
#   3. MOI CHON CAP theo quy tac da duyet (khong quy tac nao thang ngau nhien -> theo ly thuyet kich thuoc cap + hoa ngau nhien).
#      Ky dich da co ket qua (chay lai ky cu) -> bo cap trung ky do. Ky chua quay -> ghi SO DU DOAN CAP.
#   4. Doi chieu: cac ky da du doan cap, nay da co ket qua -> bao nhieu cap da chon bi trung, ky do THANH CONG (0 cap trung) khong.
#   5. PHU: ve con lai (khong cap chon nao sinh ra) ghi du_doan/<game>_<ky>.txt. CHI co nghia khi khong cap chon nao trung.
# env: KEEP(40/400) so cap chon | P_SONG (vd 0.3: chon so cap LON NHAT sao cho xac suat khong cap nao trung >= 30%, bo qua KEEP)
#      TARGET(0) >0: chon them cap cho toi khi ve con lai <= TARGET | HIST(120) so ky lich su | MAXPRED(100) MAXLIST(300) WORK(gzwork)
#      DU_DOAN(1) ghi ve con lai phu | BATCH(6) so cap tai song song | FORCE(1) chay lai ky da co
import sys, os, re, glob, csv, json, math, subprocess, hashlib
import numpy as np, pandas as pd
from math import comb
from concurrent.futures import ThreadPoolExecutor
import nghien_cuu_chon_cap as NC

game, src = sys.argv[1], sys.argv[2]
LOTTO = game == 'lotto535'
KEEP = int(os.environ.get('KEEP') or (40 if LOTTO else 400)); TARGET = int(os.environ.get('TARGET') or 0)
P_SONG = float(os.environ.get('P_SONG') or 0)
HIST = int(os.environ.get('HIST') or 120); MAXPRED = int(os.environ.get('MAXPRED') or 100); MAXLIST = int(os.environ.get('MAXLIST') or 300)
WORK = os.environ.get('WORK') or 'gzwork'; DU_DOAN = (os.environ.get('DU_DOAN') or '1') == '1'; BATCH = int(os.environ.get('BATCH') or 6)
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
LEDGER = f'chon_cap/du_doan_cap_{game}.jsonl'


def read_ledger():
    L = {}
    if os.path.exists(LEDGER):
        for l in open(LEDGER, encoding='utf-8'):
            try: r = json.loads(l); L[int(r['ky'])] = r
            except Exception: pass
    return L


if os.environ.get('FORCE') != '1' and (os.path.exists(f'du_doan/{game}_{N}.txt') or N in read_ledger()):
    print(f'{game} ky {N}: da co du doan cap/ve cho ky nay -> bo qua (khong tai Release). FORCE=1 de chay lai'); sys.exit(0)
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


def fname(p): return f'first2_{p[0]}_{p[1]}.txt.gz' if LOTTO else f'first2_mega_{p[0]}_{p[1]}.txt.gz'


def fetch(p):
    if ISDIR: return os.path.join(src, fname(p)), False
    os.makedirs(WORK, exist_ok=True); path = os.path.join(WORK, fname(p))
    subprocess.run(['gh', 'release', 'download', src, '--pattern', fname(p), '--dir', WORK, '--clobber'], check=True, capture_output=True)
    return path, True


def seeds_of(path):
    d = pd.read_csv(path, sep=' ', header=None, usecols=[0, 1], dtype={0: np.uint64, 1: np.int32}, engine='c')
    return d[0].to_numpy()[d[1].to_numpy() >= 2]


HF = f'chon_cap/cap_lich_su_{game}.txt'; DB = NC.load_hist(HF)


def update_hist(p, s):
    b = p[1]; new_lo = b + 1 if not HIST else max(b + 1, latest - HIST + 1)
    old = DB.get(p); cov = set(old['cov']) if old else set()
    if old:
        todo = list(range(new_lo, old['lo'])) if new_lo < old['lo'] else []     # mo rong lich su ve truoc neu HIST tang
        todo += list(range(max(new_lo, old['thru'] + 1), latest + 1)); lo = min(old['lo'], new_lo)
    else:
        todo = list(range(new_lo, latest + 1)); lo = new_lo
    for D in todo:
        if D in RES and (tid(s, D) == RES[D]).any(): cov.add(D)
    DB[p] = dict(n=len(s), cov=cov, thru=max(latest, old['thru'] if old else 0), lo=lo)


# ---- 2. TAI HET cap: cap nhat lich su + giu id ve cua ky dich (int32) de tinh ve con lai ve sau; xong cap thi xoa gz
TN = {}; HITN = {}; failed = []; order_all = sorted(SIZE)
for i in range(0, len(order_all), BATCH):
    grp = order_all[i:i + BATCH]
    with ThreadPoolExecutor(max_workers=BATCH) as ex:
        futs = [(p, ex.submit(fetch, p)) for p in grp]
        for p, fu in futs:
            path = None; tmp = False
            try:
                path, tmp = fu.result(); s = seeds_of(path)
                update_hist(p, s)
                TN[p] = tid(s, N).astype(np.int32)
                HITN[p] = bool(KNOWN and (TN[p] == RES[N]).any())
            except Exception as e:
                failed.append(p); print(f'  loi cap {p[0]}_{p[1]}: {e}')
            finally:
                if tmp and path and os.path.exists(path): os.remove(path)
    if (i // BATCH) % 10 == 9: print(f'  da xu ly {min(i + BATCH, len(order_all))}/{len(order_all)} cap', flush=True)
os.makedirs('chon_cap', exist_ok=True)
with open(HF, 'w', encoding='utf-8') as f:
    f.write('# LICH SU CAP: cap | so seed | ky cap da sinh dung ve that | da kiem tra den ky | ky bat dau tinh (TAT CA cap tren Release, tai het)\n')
    for p in sorted(DB):
        f.write(f"{p[0]}_{p[1]} | {DB[p]['n']} | {','.join(map(str, sorted(DB[p]['cov']))) or '-'} | {DB[p]['thru']} | {DB[p]['lo']}\n")
cand = [p for p in TN]                                  # cap tai + xu ly thanh cong
if not cand: sys.exit('khong tai duoc cap nao')
print(f'{game} ky {N}: da tai/xu ly {len(cand)}/{len(SIZE)} cap' + (f', loi {len(failed)}' if failed else ''), flush=True)

# ---- 3. NGHIEN CUU + BACKTEST MU tren TOAN BO cap, roi MOI chon cap
SUB = {p: DB[p] for p in cand}
st = NC.nghien_cuu(game, SUB, CT, N, KEEP, f'bao_cao/nghien_cuu_chon_cap_{game}.txt', quiet=True)
rule, approved = st['rule'], st['approved']
print('  nghien cuu: ' + [l for l in st['lines'] if l.startswith('KET LUAN')][0], flush=True) if any(l.startswith('KET LUAN') for l in st['lines']) else None
pool = [p for p in cand if not HITN.get(p)]            # ky da biet ket qua: loai cap trung (chay lai/thu nghiem)
ranked = NC.choose(rule, SUB, CT, N, pool)
if P_SONG > 0:
    K = 0; ps = 1.0
    for p, sc, pr in ranked:
        if ps * (1 - pr) < P_SONG and K >= 1: break
        ps *= (1 - pr); K += 1
else:
    K = min(KEEP, len(ranked))
alive = np.ones(CT, dtype=bool); chosen = []; TRAJ = []
for p, sc, pr in ranked:
    if len(chosen) >= K and (TARGET == 0 or np.count_nonzero(alive) <= TARGET): break
    alive[TN[p]] = False; chosen.append((p, sc, pr)); TRAJ.append((len(chosen), int(np.count_nonzero(alive))))
rem = np.flatnonzero(alive); real_in = bool(alive[RES[N]]) if KNOWN else None
p_ok = math.exp(sum(math.log(1 - c[2]) for c in chosen))          # P(khong cap chon nao trung) ly thuyet = ~ ve con lai / to hop
skipped_hit = sum(1 for p in cand if HITN.get(p))
verdict = ('quy tac "' + rule + '" thang ngau nhien ngoai mau') if approved else 'KHONG quy tac nao hon ngau nhien -> cap chon cung xac suat nhu cap ngau nhien'
for old in glob.glob(f'chon_cap/chon_cap_loai_{game}_*.txt') + glob.glob(f'chon_cap/chon_cap_{game}_*.txt') + glob.glob(f'chon_cap/bang_k_{game}_*.txt'):
    os.remove(old)
# ---- 3a. FILE CAP CHON (chinh)
out = f'chon_cap/chon_cap_{game}_{N}.txt'
with open(out, 'w', encoding='utf-8') as f:
    f.write(f'# CHON CAP (CHINH) | {game} ky {N} | chon {len(chosen)} cap / {len(cand)} cap da tai het | quy tac: {rule} | {verdict}\n')
    if KNOWN:
        f.write(f'# KY {N} DA CO KET QUA (chay lai/thu nghiem): bo {skipped_hit} cap trung ky nay; ve that con trong tap ve con lai: {real_in}\n')
    else:
        f.write(f'# KY {N} CHUA QUAY: xac suat KHONG cap nao trung (thanh cong) ~ {p_ok:.3e} = ve con lai / to hop. Co cap trung -> ve con lai VO NGHIA.\n')
    f.write('# cap | P(trung) ly thuyet | diem quy tac\n')
    for p, sc, pr in chosen: f.write(f'{p[0]}_{p[1]} | {pr:.4f} | {sc:.4f}\n')
with open(f'chon_cap/bang_k_{game}_{N}.txt', 'w', encoding='utf-8') as f:
    f.write(f'# {game} ky {N}: K cap chon | P(thanh cong: khong cap nao trung) | so ve con lai R (R / {CT:,} = P thanh cong)\n')
    pk = 1.0
    for k, r in TRAJ:
        pk *= (1 - chosen[k - 1][2])
        if k <= 5 or k % 5 == 0 or k == len(chosen): f.write(f'{k} | {pk:.3e} | {r:,}\n')
# ---- 3b. SO DU DOAN CAP (chi ky chua quay) + 4. DOI CHIEU cac ky da quay
led = read_ledger()
if not KNOWN:
    led[N] = dict(ky=N, quy_tac=rule, duyet=approved, K=len(chosen), p_thanh_cong=p_ok, cap=[f'{c[0][0]}_{c[0][1]}' for c in chosen], p_trung=[round(c[2], 6) for c in chosen])
with open(LEDGER, 'w', encoding='utf-8') as f:
    for k in sorted(led): f.write(json.dumps(led[k], ensure_ascii=False) + '\n')
rows = []; n_ok = 0; sum_hit = 0; sum_exp = 0.0; sum_pok = 0.0
for k in sorted(led):
    if k not in RES or k > latest: continue
    e = led[k]; ps = [tuple(map(int, x.split('_'))) for x in e['cap']]; miss = [p for p in ps if p not in DB or not (DB[p]['lo'] <= k <= DB[p]['thru'])]
    if miss: continue
    hit = [p for p in ps if k in DB[p]['cov']]; ok = not hit
    n_ok += ok; sum_hit += len(hit); sum_exp += sum(e['p_trung']); sum_pok += e['p_thanh_cong']
    hs = ','.join('%d_%d' % (p[0], p[1]) for p in hit[:6]) + (',...' if len(hit) > 6 else '')
    kq = 'THANH CONG' if ok else 'THAT BAI (cap trung: ' + hs + ')'
    rows.append('%d | %s | %d | %d | %s | %.2f | %.2e' % (k, e['quy_tac'], e['K'], len(hit), kq, sum(e['p_trung']), e['p_thanh_cong']))
with open(f'chon_cap/ket_qua_chon_cap_{game}.txt', 'w', encoding='utf-8') as f:
    f.write(f'# KET QUA THAT cua cap da chon (ngoai mau: so cap duoc ghi TRUOC khi ky quay) | {game}\n# ky | quy tac | K | so cap trung | ket qua | cap trung ky vong | P(thanh cong) ly thuyet\n')
    for r in rows: f.write(r + '\n')
    f.write(f'# TONG: {len(rows)} ky da quay | thanh cong {n_ok} (ky vong ngau nhien {sum_pok:.2f}) | tong cap trung {sum_hit} (ky vong {sum_exp:.1f})\n')
    f.write('# Thanh cong = KHONG cap nao trung. Chua co ky nao thi can doi ky tiep theo quay roi chay lai (bo cap duoc ghi truoc khi quay).\n')
# ---- 5. PHU: ve con lai
if DU_DOAN:
    cap = MAXPRED if TARGET == 0 else TARGET
    pick = rem if len(rem) <= cap else rem[np.linspace(0, len(rem) - 1, cap).astype(np.int64)]
    os.makedirs('du_doan', exist_ok=True)
    with open(f'du_doan/{game}_{N}.txt', 'w', encoding='utf-8') as f:
        f.write(f'# Ky {N} ({game}): {len(pick)} ve du doan = VE CON LAI (PHU) sau khi loai ve cua {len(chosen)} cap chon | ve con lai: {len(rem):,}\n')
        f.write(f'# nguon: con_lai {len(pick)} | CHI CO NGHIA neu khong cap nao trung (xac suat ~ {p_ok:.2e}); {verdict}. Moi ve chi co xac suat ngau nhien 1/{CT:,}.\n# ve | nguon | chi tiet\n')
        for v in pick: f.write(f'{dec(v)} | con_lai | khong seed nao cua {len(chosen)} cap chon sinh ra\n')
print(f'{game} ky {N}: chon {len(chosen)} cap (da tai het {len(cand)}), quy tac {rule} ({"DAT" if approved else "chua hon ngau nhien"}), P thanh cong ~ {p_ok:.2e}, con lai {len(rem):,} ve, bo {skipped_hit} cap trung | ket qua that: {n_ok}/{len(rows)} ky thanh cong -> {out}')
