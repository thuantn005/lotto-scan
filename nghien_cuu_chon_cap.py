#!/usr/bin/env python3
"""NGHIEN CUU + BACKTEST MU (walk-forward) CHON CAP tren TOAN BO cap - Lotto 5/35 va Mega 6/45.
Muc tieu cot loi: CHON CAP KHONG TRUNG. Cap 'trung' ky D = cap co seed sinh dung ve that cua ky D. Chon cap co cap trung -> ve that bi loai oan
-> ve con lai vo nghia. Thanh cong cua 1 bo cap = KHONG cap nao trung.
Quy trinh: (1) lich su cua TAT CA cap (chon_cap/cap_lich_su_<game>.txt, do chon_cap_release.py tai het Release) -> (2) so sanh cac QUY TAC xep hang bang
backtest mu (ky D chi dung lich su ky < D) tren nua dau (train) va nua sau (test) -> (3) CHI duyet quy tac neu thang ngau nhien ngoai mau
(z test <= -ZPASS va z train <= -ZTRAIN); khong quy tac nao dat -> mac dinh theo ly thuyet (kich thuoc cap) va noi ro la chua hon ngau nhien.
Chay rieng:  python3 nghien_cuu_chon_cap.py lotto535|mega     env: HIST_FILE, WARM (8), ZPASS (2.5), ZTRAIN (1.0), PRIMARY (0.25)
Ghi: bao_cao/nghien_cuu_chon_cap_<game>.txt"""
import os, re, sys, math, hashlib
import numpy as np

WARM = int(os.environ.get('WARM') or 8)
ZPASS = float(os.environ.get('ZPASS') or 2.5)
ZTRAIN = float(os.environ.get('ZTRAIN') or 1.0)
PRIMARY = float(os.environ.get('PRIMARY') or 0.25)       # chi tieu chinh: chon 25% cap co diem thap nhat
MIN_TEST = int(os.environ.get('MIN_TEST') or 15)
RULES = ['ngau_nhien', 'kich_thuoc', 'lich_su_K20', 'lich_su_K5', 'gan_day_10']
CANDIDATES = ['kich_thuoc', 'lich_su_K20', 'lich_su_K5', 'gan_day_10']     # cac quy tac duoc xet duyet (ngau_nhien chi la doi chung)
MOD_OF = {'lotto535': 324632, 'mega': 8145060}


def CT_of(game):
    return MOD_OF[game] * 12 if game == 'lotto535' else MOD_OF[game]


def load_hist(path):
    DB = {}
    if not os.path.exists(path): return DB
    for l in open(path, encoding='utf-8'):
        a = [x.strip() for x in l.split('|')]
        if len(a) >= 5 and re.fullmatch(r'\d+_\d+', a[0]):
            DB[tuple(map(int, a[0].split('_')))] = dict(n=int(a[1]), cov={int(x) for x in a[2].split(',') if x.isdigit()}, thru=int(a[3]), lo=int(a[4]))
    return DB


def prior_of(n, CT):
    return 1 - math.exp(-n / CT)


def build(DB, CT, pairs=None):
    """Ma tran lich su: hang = cap, cot = ky D. Gia tri 1 (cap trung ky D), 0 (khong trung), -1 (khong co du lieu)."""
    pairs = sorted(DB) if pairs is None else list(pairs)
    d0 = min(DB[p]['lo'] for p in pairs); d1 = max(DB[p]['thru'] for p in pairs)
    H = -np.ones((len(pairs), d1 - d0 + 1), dtype=np.int8)
    for i, p in enumerate(pairs):
        e = DB[p]
        H[i, e['lo'] - d0: e['thru'] - d0 + 1] = 0
        for D in e['cov']:
            if e['lo'] <= D <= e['thru']: H[i, D - d0] = 1
    pri = np.array([prior_of(DB[p]['n'], CT) for p in pairs])
    cumH = np.concatenate([np.zeros((len(pairs), 1)), np.cumsum(H == 1, axis=1)], axis=1)
    cumA = np.concatenate([np.zeros((len(pairs), 1)), np.cumsum(H >= 0, axis=1)], axis=1)
    return pairs, d0, d1, H, pri, cumH, cumA


def rule_scores(rule, cumH, cumA, pri, j):
    """Diem P(trung) uoc luong cua tung cap tai cot j, CHI dung cot < j (khong nhin truoc). Thap = tot."""
    if rule == 'ngau_nhien': return np.zeros(len(pri))
    if rule == 'kich_thuoc': return pri.copy()
    if rule in ('lich_su_K20', 'lich_su_K5'):
        K = 20.0 if rule.endswith('K20') else 5.0
        return (cumH[:, j] + K * pri) / (cumA[:, j] + K)
    if rule == 'gan_day_10':
        j0 = max(j - 10, 0)
        return ((cumH[:, j] - cumH[:, j0]) + 10.0 * pri) / ((cumA[:, j] - cumA[:, j0]) + 10.0)
    raise ValueError(rule)


def rank(score, tie):
    return np.lexsort((tie, score))           # diem tang dan, hoa nhau bang tie


def _hyper(M, Hn, k):
    """ky vong, phuong sai, P(khong cap nao trung) khi chon NGAU NHIEN k trong M cap co Hn cap trung."""
    f = Hn / M
    e = k * f; v = k * f * (1 - f) * (M - k) / max(M - 1, 1)
    ps = math.comb(M - Hn, k) / math.comb(M, k) if M - Hn >= k else 0.0
    return e, v, ps


def walk_forward(DB, CT, ks, seed=1, pairs=None):
    pairs, d0, d1, H, pri, cumH, cumA = build(DB, CT, pairs)
    rng = np.random.default_rng(seed)
    nD = H.shape[1]; start = WARM
    cols = [j for j in range(start, nD) if (H[:, j] >= 0).sum() >= 8]
    half = len(cols) // 2
    out = {}
    for rule in RULES:
        acc = {'tr': [0.0, 0.0, 0.0, 0], 'te': [0.0, 0.0, 0.0, 0]}               # obs, exp, var, so ky (chi tieu chinh)
        kk = {k: dict(obs=0.0, exp=0.0, var=0.0, so=0.0, so_e=0.0, nd=0) for k in ks}
        for idx, j in enumerate(cols):
            av = np.flatnonzero(H[:, j] >= 0); M = len(av); hit = (H[av, j] == 1); Hn = int(hit.sum())
            sc = rule_scores(rule, cumH, cumA, pri, j)[av]
            order = rank(sc, rng.random(M)); k = max(1, int(M * PRIMARY))
            e, v, _ = _hyper(M, Hn, k); a = acc['tr' if idx < half else 'te']
            a[0] += hit[order[:k]].sum(); a[1] += e; a[2] += v; a[3] += 1
            for K in ks:
                if K >= M: continue
                e, v, ps = _hyper(M, Hn, K); r = kk[K]
                r['obs'] += hit[order[:K]].sum(); r['exp'] += e; r['var'] += v; r['so'] += int(hit[order[:K]].sum() == 0); r['so_e'] += ps; r['nd'] += 1
        def z(a): return (a[0] - a[1]) / math.sqrt(a[2]) if a[2] > 0 else float('nan')
        tot = [acc['tr'][i] + acc['te'][i] for i in range(4)]
        out[rule] = dict(z_tr=z(acc['tr']), z_te=z(acc['te']), z_all=z(tot), n_tr=acc['tr'][3], n_te=acc['te'][3], obs=tot[0], exp=tot[1], ks=kk)
    return out, cols, d0


def nghien_cuu(game, DB, CT, N, K, report_path=None, quiet=False):
    """Chay toan bo nghien cuu tren DB (tat ca cap). Tra ve dict(rule, approved, lines...)."""
    ks = sorted({k for k in (1, 2, 3, 5, 8, 10, 15, 20, 40, 100, 200) if k < len(DB)} | ({K} if 0 < K < len(DB) else set()))
    L = [f'NGHIEN CUU + BACKTEST MU CHON CAP | {game} | ky dich {N} | {len(DB)} cap (TAI HET Release)',
         'Cot loi: chon cap KHONG trung (khong cap nao sinh dung ve that). Co cap trung thi ve con lai vo nghia.', '']
    if len(DB) < 8:
        L.append('Chua du cap de backtest (can >= 8 cap co lich su).')
        return dict(rule='kich_thuoc', approved=False, lines=L, reason='it cap')
    res, cols, d0 = walk_forward(DB, CT, ks)
    nd = len(cols)
    pri = np.array([prior_of(DB[p]['n'], CT) for p in sorted(DB)])
    sp = (pri.max() - pri.min()) / pri.mean()
    L += [f'Backtest mu: {nd} ky (ky {d0 + cols[0]}..{d0 + cols[-1]}), nua dau = train ({res["kich_thuoc"]["n_tr"]} ky), nua sau = test ({res["kich_thuoc"]["n_te"]} ky).',
          f'Chi tieu chinh: chon {int(PRIMARY * 100)}% cap co diem thap nhat; z < 0 = cap chon trung IT hon ngau nhien (hypergeometric, cung tap cap tung ky).',
          f'Duyet quy tac khi z_test <= -{ZPASS:.1f} VA z_train <= -{ZTRAIN:.1f} (nguong chat vi thu {len(CANDIDATES)} quy tac) VA >= {MIN_TEST} ky test.',
          f'Do chenh P(trung) ly thuyet giua cac cap (theo so seed): {sp:.2%} cua gia tri TB -> kich thuoc cap gan nhu khong phan biet duoc cap.', '',
          'quy tac | z train | z test | z chung | cap chon trung / ky vong | ket luan']
    approved = []
    for r in RULES:
        o = res[r]
        ok = r in CANDIDATES and o['z_te'] <= -ZPASS and o['z_tr'] <= -ZTRAIN and o['n_te'] >= MIN_TEST
        if ok: approved.append((o['z_te'], r))
        tag = 'DOI CHUNG (phai ~ 0)' if r == 'ngau_nhien' else ('DAT: thang ngau nhien ngoai mau' if ok else 'chua hon ngau nhien')
        L.append(f'{r} | {o["z_tr"]:+.2f} | {o["z_te"]:+.2f} | {o["z_all"]:+.2f} | {int(o["obs"])} / {o["exp"]:.1f} | {tag}')
    if abs(res['ngau_nhien']['z_all']) > 2.5:
        L.append('CANH BAO: doi chung ngau nhien |z| > 2.5 -> kiem tra du lieu lich su (thieu ky/lech) truoc khi tin ket qua.')
    if approved:
        rule = sorted(approved)[0][1]; ap = True
        L += ['', f'KET LUAN: quy tac "{rule}" thang ngau nhien ngoai mau -> DUNG de chon cap (van can theo doi them ky moi).']
    else:
        rule = 'kich_thuoc'; ap = False
        L += ['', 'KET LUAN: KHONG quy tac lich su nao hon ngau nhien ngoai mau. Chon cap = chon cap it seed nhat (ly thuyet, khac biet rat nho) + hoa ngau nhien.',
              'Hieu: neu lich su cap khong du bao duoc, xac suat K cap deu khong trung = ve con lai / to hop, cap nao cung nhu cap nao.']
    L += ['', 'Theo K (so cap chon): thanh cong = ca K cap deu KHONG trung (ve that con trong tap ve con lai)', 'K | ky | cap chon trung / ky vong | thanh cong that / ky vong (ngau nhien) | quy tac ' + rule]
    for K_, r in res[rule]['ks'].items():
        if r['nd']: L.append(f'{K_} | {r["nd"]} | {int(r["obs"])} / {r["exp"]:.1f} | {int(r["so"])} / {r["so_e"]:.1f} | z = {((r["obs"] - r["exp"]) / math.sqrt(r["var"]) if r["var"] > 0 else float("nan")):+.2f}')
    L += ['', 'LUU Y: ky quay la su kien doc lap -> cap trung ky D khong phu thuoc cac ky truoc; chi so seed cua cap (rat gan nhau) quyet dinh P(trung).',
          'Mau backtest it ky -> p-value chi mang tinh tham khao; tiep tuc tich luy ky moi (chon_cap/ket_qua_chon_cap_<game>.txt la ket qua THAT ngoai mau).']
    if report_path:
        os.makedirs(os.path.dirname(report_path) or '.', exist_ok=True)
        open(report_path, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    if not quiet: print('\n'.join(L))
    return dict(rule=rule, approved=ap, lines=L, res=res)


def choose(rule, DB, CT, N, cand=None, tie_seed=''):
    """Xep hang cap de CHON cho ky N (chua biet ket qua): diem chi tu lich su, hoa nhau bang bam (cap, ky)."""
    cand = sorted(DB) if cand is None else sorted(cand)
    sub = {p: DB[p] for p in cand}
    pairs, d0, d1, H, pri, cumH, cumA = build(sub, CT, cand)
    j = H.shape[1]                                     # cot 'ngay sau cuoi' -> dung toan bo lich su
    sc = rule_scores(rule, cumH, cumA, pri, j)
    tie = np.array([int(hashlib.md5(f'{p[0]}_{p[1]}_{N}{tie_seed}'.encode()).hexdigest()[:12], 16) for p in pairs], dtype=np.float64)
    order = rank(sc, tie)
    return [(pairs[i], float(sc[i]), float(pri[i])) for i in order]


if __name__ == '__main__':
    game = sys.argv[1] if len(sys.argv) > 1 else 'lotto535'
    CT = CT_of(game); DB = load_hist(os.environ.get('HIST_FILE') or f'chon_cap/cap_lich_su_{game}.txt')
    if not DB: sys.exit('chua co lich su cap (chay chon_cap_release.py truoc de tai het cap)')
    N = max(v['thru'] for v in DB.values()) + 1
    nghien_cuu(game, DB, CT, N, int(os.environ.get('KEEP') or 0), f'bao_cao/nghien_cuu_chon_cap_{game}.txt')
