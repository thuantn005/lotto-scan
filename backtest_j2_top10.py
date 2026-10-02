#!/usr/bin/env python3
"""
Walk-forward backtest (strict no-leakage) cho consensus-2 cua L1-1.

DU LIEU DAU VAO (da sua loi doc du lieu):
  - Seed L1-1      : <data>/l1-1/*.json      (moi file {draw_id, seeds:[...]} )
  - Ket qua thuc te: <data>/data/all.csv     (cot draw_id, result_json)
  Khong con tim CSV ben trong l1-1/.

Quy tac:
  - Target T chi dung seed cua cac ky < T (cua so toi da --window ky hoan tat truoc T).
  - Seed xuat hien o ky ngay truoc (T-1) van duoc tinh. Moi seed chi tinh 1 lan trong pool.
  - Consensus-2 = DUNG 2 seed tao cung 5 so + so dac biet tai ky T.
  - J1 = 5/5 + dac biet dung ; J2 = 5/5 so chinh nhung dac biet sai.
  - Xep hang Top-N chi dung thong tin truoc T (tuoi seed, tuoi/khoang cach cua so dac biet).
  - Moi dau ra la .txt (tab-separated), khong tao .csv.
"""
import argparse, json, csv, math, sys
from pathlib import Path
import numpy as np

M1, M2, M3, M4 = 0x9E3779B97F4A7C15, 0xD1B54A32D192ED03, 0xBF58476D1CE4E5B9, 0x94D049BB133111EB
C = math.comb(35, 5)
U = np.uint64

def mixv(x):
    x = x ^ (x >> U(30)); x = x * U(M3); x = x ^ (x >> U(27)); x = x * U(M4)
    return x ^ (x >> U(31))

def unrank(rank):                      # colex, tra ve 5 so 1..35
    out, x, r = [], 35, rank
    for i in range(5, 0, -1):
        while math.comb(x, i) > r: x -= 1
        out.append(x); r -= math.comb(x, i); x -= 1
    return tuple(sorted(v + 1 for v in out))

def rank_of(nums):                     # nghich dao cua unrank
    return sum(math.comb(n - 1, i + 1) for i, n in enumerate(sorted(nums)))

def keys_at(seeds, draw):              # key = rank*12 + (special-1)
    with np.errstate(over="ignore"):
        m = mixv(seeds * U(M1) + U((draw * M2) & 0xFFFFFFFFFFFFFFFF))
        return (m % U(C)).astype(np.int64) * 12 + (mixv(m) % U(12)).astype(np.int64)

def load_l1(root):
    files = sorted((Path(root) / "l1-1").glob("*.json"))
    if not files: sys.exit(f"Khong tim thay {root}/l1-1/*.json")
    L = {}
    for f in files:
        j = json.loads(f.read_text(encoding="utf-8"))
        L[int(j["draw_id"])] = np.array(j["seeds"], dtype=np.uint64)
    return L

def load_actual(root):
    p = Path(root) / "data" / "all.csv"
    if not p.exists(): sys.exit(f"Khong tim thay {p}")
    res = {}
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                j = json.loads(r["result_json"])
                res[int(r["draw_id"])] = (tuple(sorted(j["numbers"])), int(j["special_numbers"][0]))
            except Exception:
                continue
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="."); ap.add_argument("--start", type=int, default=724)
    ap.add_argument("--end", type=int, default=921); ap.add_argument("--window", type=int, default=200)
    ap.add_argument("--top", type=int, default=10); ap.add_argument("--out", default="j2_top10_results")
    a = ap.parse_args()
    L, actual = load_l1(a.data), load_actual(a.data)
    l1_draws = sorted(L)
    print(f"L1-1: {len(L)} ky ({l1_draws[0]}..{l1_draws[-1]}) | all.csv: {len(actual)} ky")

    # Tu kiem tra: seed trong l1-1/D.json phai tai tao dung ket qua that cua ky D
    d0 = next(d for d in l1_draws if d in actual); n0, s0 = actual[d0]
    k = keys_at(L[d0][:50], d0)
    assert all(int(x) // 12 == rank_of(n0) and int(x) % 12 + 1 == s0 for x in k), "Du lieu/thuat toan khong khop!"
    assert unrank(rank_of(n0)) == n0

    sp_hist = {}                                    # dac biet theo ky (chi dung ky < T)
    per_draw, tickets = [], []
    for T in range(a.start, a.end + 1):
        if T not in actual: continue
        wd = [d for d in l1_draws if d < T][-a.window:]
        if not wd: continue
        seeds = np.concatenate([L[d] for d in wd])
        draws = np.concatenate([np.full(len(L[d]), d, dtype=np.int64) for d in wd])
        # moi seed 1 lan, lay ky xuat hien GAN NHAT truoc T
        rs, rd = seeds[::-1], draws[::-1]
        useed, idx = np.unique(rs, return_index=True)
        age = T - rd[idx]
        key = keys_at(useed, T)
        order = np.argsort(key, kind="stable")
        ks, ag = key[order], age[order]
        u, st, cnt = np.unique(ks, return_index=True, return_counts=True)
        pair = np.nonzero(cnt == 2)[0]                          # consensus-2 dung 2 seed
        pk, a1, a2 = u[pair], ag[st[pair]], ag[st[pair] + 1]
        # dac biet: tuoi & khoang cach dua tren ket qua cac ky < T
        past = sorted(d for d in actual if d < T)
        last, gap = {}, {}
        for d in past:
            s = actual[d][1]
            gap[s] = d - last[s] if s in last else 0
            last[s] = d
        sp = pk % 12 + 1
        sage = np.array([T - last[s] if s in last else 10**9 for s in sp])
        sgap = np.array([gap.get(s, 0) for s in sp])
        # score (nho = xep truoc): tong tuoi, tuoi lon nhat, tuoi dac biet, khoang cach dac biet, rank, dac biet
        o = np.lexsort((sp, pk // 12, sgap, sage, np.maximum(a1, a2), a1 + a2))[: a.top]
        an, asp = actual[T]; arank = rank_of(an)
        j1 = j2 = False; j2r = []
        for r, i in enumerate(o, 1):
            rk, s = divmod(int(pk[i]), 12); s += 1
            main_hit = rk == arank
            h1, h2 = main_hit and s == asp, main_hit and s != asp
            j1 |= h1; j2 |= h2
            if h2: j2r.append(r)
            tickets.append((T, r, "-".join(f"{x:02d}" for x in unrank(rk)), s, int(a1[i]), int(a2[i]),
                            int(sage[i]), int(sgap[i]), int(h1), int(h2)))
        per_draw.append((T, len(wd), len(useed), len(pair), ",".join(map(str, j2r)), int(j2), int(j1)))
        if len(per_draw) % 20 == 0: print(f"  ...da xong ky {T}", flush=True)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with open(out / "per_draw.txt", "w", encoding="utf-8") as f:
        f.write("draw\twindow_draws\tpool_seeds\tconsensus2_count\ttop_j2_ranks\tj2_hit\tj1_hit\n")
        for r in per_draw: f.write("\t".join(map(str, r)) + "\n")
    with open(out / "top_tickets.txt", "w", encoding="utf-8") as f:
        f.write("draw\trank\tnumbers\tspecial\tage1\tage2\tspecial_age\tspecial_gap\tj1\tj2\n")
        for r in tickets: f.write("\t".join(map(str, r)) + "\n")
    n = len(per_draw); h2 = sum(r[5] for r in per_draw); h1 = sum(r[6] for r in per_draw)
    exp = len(tickets) / C
    s = (f"J2 TOP-{a.top} WALK-FORWARD | ky {a.start}..{a.end} | window<= {a.window}\n"
         f"ky da test: {n} | tong ve top: {len(tickets)}\n"
         f"J2 (5/5 chinh, DB sai): {h2} ky ({h2/max(n,1):.4%}) | J1 (5/5 + DB): {h1} ky\n"
         f"Ky vong ngau nhien cho {len(tickets)} ve: ~{exp:.5f} lan trung 5/5 chinh\n")
    (out / "summary.txt").write_text(s, encoding="utf-8"); print(s)

if __name__ == "__main__":
    main()
