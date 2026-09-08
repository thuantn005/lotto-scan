#!/usr/bin/env python3
"""
scan_j1_numba.py — Ban Numba tang toc, dung DUNG thuat toan SplitMix64
(_mix, _unrank, ticket, special) giong het scan_j1_triple.py goc.
Da kiem chung: ket qua khop 100% voi ban pure Python tren 4 seed J1=2 da biet.

Tracking song song (khong ton them thoi gian quet, chi them so sanh sau khi da co cnt):
  - J1 >= 2, 3, 4 (khop du 5 so chinh + Dac Biet)
  - Top seed trung nhieu ky 5/5 so chinh nhat (khong can DB) -- "Jackpot 2" best
  - Top seed trung nhieu ky 4/5 so chinh nhat (khong can DB)
  - Top seed trung nhieu ky Dac Biet nhat (khong can 5/5 so chinh)
"""
import csv, json, os, sys, time
from math import comb
from pathlib import Path
import numpy as np
from numba import njit

CSV_PATH = os.environ.get("CSV_PATH", "data/all.csv")
OUT_PATH = os.environ.get("OUT_PATH", "results/chunk.json")
START    = int(os.environ.get("SCAN_START", "1"))
END      = int(os.environ.get("SCAN_END",   "500000000"))
MIN_LOG  = int(os.environ.get("MIN_LOG",    "2"))
CHECKPOINT_SEC = 30
BATCH_SEEDS = int(os.environ.get("BATCH_SEEDS", "2000000"))
TOP_N = 100  # giu top 100 seed cho moi bang xep hang (4/5, 5/5, DB)

M1 = np.uint64(0x9E3779B97F4A7C15)
M2 = np.uint64(0xD1B54A32D192ED03)
M3 = np.uint64(0xBF58476D1CE4E5B9)
M4 = np.uint64(0x94D049BB133111EB)
C  = comb(35, 5)

BINOM = np.zeros((36, 6), dtype=np.int64)
for nn in range(36):
    for kk in range(6):
        BINOM[nn, kk] = comb(nn, kk) if kk <= nn else 0


@njit(cache=True)
def _mix_nb(x):
    z = x
    z ^= z >> np.uint64(30)
    z *= M3
    z ^= z >> np.uint64(27)
    z *= M4
    z ^= z >> np.uint64(31)
    return z


@njit(cache=True)
def _rank_mask(r, binom):
    mask = 0
    rem = r
    for k in range(5, 0, -1):
        x = k - 1
        while binom[x + 1, k] <= rem:
            x += 1
        mask |= (1 << x)
        rem -= binom[x, k]
    return mask


@njit(cache=True)
def _popcount(x):
    """Dem so bit 1 trong x (so so chinh khop)."""
    cnt = 0
    while x:
        cnt += x & 1
        x >>= 1
    return cnt


@njit(cache=True)
def scan_batch(seeds, draw_ids, target_masks, target_special, binom):
    """
    Tra ve 4 mang cho moi seed:
      j1_counts   : so ky khop du 5/5 + DB (J1)
      main5_counts: so ky khop du 5/5 so chinh (khong can DB) -- "Jackpot 2"
      main4_counts: so ky khop dung 4/5 so chinh (khong can DB)
      spec_counts : so ky khop DB (khong can so chinh)
    Khong ton them thoi gian dang ke -- van chi 1 lan tinh mixed/rank/mask cho moi (seed,ky).
    """
    n_seeds = seeds.shape[0]
    n_draws = draw_ids.shape[0]
    j1_counts = np.zeros(n_seeds, dtype=np.int64)
    main5_counts = np.zeros(n_seeds, dtype=np.int64)
    main4_counts = np.zeros(n_seeds, dtype=np.int64)
    spec_counts = np.zeros(n_seeds, dtype=np.int64)

    for i in range(n_seeds):
        seed_u64 = np.uint64(seeds[i])
        c_j1 = 0; c_m5 = 0; c_m4 = 0; c_sp = 0
        for j in range(n_draws):
            d = draw_ids[j]
            combined = seed_u64 * M1 + d * M2
            mixed = _mix_nb(combined)
            rank = np.int64(mixed % np.uint64(C))
            mask = _rank_mask(rank, binom)

            mixed2 = _mix_nb(mixed)
            sp = np.int64(mixed2 % np.uint64(12)) + 1

            overlap = mask & target_masks[j]
            n_match_main = _popcount(overlap)
            sp_match = (sp == target_special[j])

            if n_match_main == 5:
                c_m5 += 1
                if sp_match:
                    c_j1 += 1
            elif n_match_main == 4:
                c_m4 += 1

            if sp_match:
                c_sp += 1

        j1_counts[i] = c_j1
        main5_counts[i] = c_m5
        main4_counts[i] = c_m4
        spec_counts[i] = c_sp

    return j1_counts, main5_counts, main4_counts, spec_counts


def _mask_of(nums):
    m = 0
    for n in nums:
        m |= (1 << (n - 1))
    return m


@njit(cache=True)
def _seed_hits_mask(seed, draw_ids, binom):
    n = draw_ids.shape[0]
    ranks = np.zeros(n, dtype=np.int64)
    specials = np.zeros(n, dtype=np.int64)
    seed_u64 = np.uint64(seed)
    for j in range(n):
        d = draw_ids[j]
        combined = seed_u64 * M1 + d * M2
        mixed = _mix_nb(combined)
        ranks[j] = np.int64(mixed % np.uint64(C))
        mixed2 = _mix_nb(mixed)
        specials[j] = np.int64(mixed2 % np.uint64(12)) + 1
    return ranks, specials


def _details_for_seed(seed, draw_ids, draw_ids_np, res, spc, dates):
    hits = []
    ranks, specials = _seed_hits_mask(seed, draw_ids_np, BINOM)
    for j, d in enumerate(draw_ids):
        mask = _rank_mask(int(ranks[j]), BINOM)
        if mask == _mask_of(res[d]) and int(specials[j]) == spc[d]:
            hits.append({"draw_id": d, "draw_date": dates[d], "numbers": res[d], "special": spc[d]})
    return hits


def _update_topn(topn_list, seed, count, top_n=TOP_N):
    """Cap nhat danh sach top-N (seed, count), giu sorted giam dan, gioi han top_n."""
    topn_list.append({"seed": seed, "count": count})
    topn_list.sort(key=lambda x: -x["count"])
    if len(topn_list) > top_n:
        del topn_list[top_n:]


def main():
    res = {}; spc = {}; dates = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                d = int(row["draw_id"]); rj = json.loads(row["result_json"])
                res[d] = sorted(rj["numbers"]); spc[d] = rj["special_numbers"][0]
                dates[d] = row.get("draw_date", "")
            except: continue

    draw_ids = sorted(res.keys())
    n = len(draw_ids)
    print(f"Loaded {n} ky. Quet seed {START:,} -> {END:,}, MIN_LOG={MIN_LOG}, batch={BATCH_SEEDS:,}", flush=True)

    draw_ids_np = np.array(draw_ids, dtype=np.uint64)
    target_masks = np.array([_mask_of(res[d]) for d in draw_ids], dtype=np.int64)
    target_special = np.array([spc[d] for d in draw_ids], dtype=np.int64)

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)

    if START > END:
        OUT_DIR = Path(OUT_PATH).parent
        OUT_STEM = Path(OUT_PATH).stem
        base = {"status": "empty", "scan_start": START, "scan_end": END, "scanned": 0, "completed": True}
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump({**base, "min_log": MIN_LOG, "found_j1_2plus": 0, "found_j1_3plus": 0, "found_j1_4plus": 0}, f, ensure_ascii=False, indent=1)
        for suffix, extra in [
            ("_j1_2plus", {"level":"j1>=2","found":0,"results":[]}),
            ("_j1_3plus", {"level":"j1>=3","found":0,"results":[]}),
            ("_j1_4plus", {"level":"j1>=4","found":0,"results":[]}),
            ("_top_main5", {"level":"top_5_of_5_main_numbers","results":[]}),
            ("_top_main4", {"level":"top_4_of_5_main_numbers","results":[]}),
            ("_top_special", {"level":"top_special_number","results":[]}),
        ]:
            with open(OUT_DIR / f"{OUT_STEM}{suffix}.json", "w", encoding="utf-8") as f:
                json.dump({**base, **extra}, f, ensure_ascii=False, indent=1)
        print("Range rong.")
        return

    t_warm = time.time()
    _ = scan_batch(np.array([1], dtype=np.int64), draw_ids_np, target_masks, target_special, BINOM)
    print(f"Warm-up JIT compile: {time.time()-t_warm:.2f}s", flush=True)

    OUT_DIR = Path(OUT_PATH).parent
    OUT_STEM = Path(OUT_PATH).stem  # vd: "chunk_0"

    def _atomic_write(path, data):
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def save_checkpoint(scanned_count, found_by_level, top_main5, top_main4, top_special, done=False):
        base = {
            "status": "completed" if done else "partial",
            "scan_start": START, "scan_end": END,
            "scanned": scanned_count, "completed": done,
        }

        # File chinh (tuong thich workflow cu -- de Validate/Merge doc duoc)
        _atomic_write(OUT_PATH, {
            **base, "min_log": MIN_LOG,
            "found_j1_2plus": len(found_by_level[2]),
            "found_j1_3plus": len(found_by_level[3]),
            "found_j1_4plus": len(found_by_level[4]),
        })

        # Tach rieng tung file theo yeu cau
        _atomic_write(OUT_DIR / f"{OUT_STEM}_j1_2plus.json", {
            **base, "level": "j1>=2",
            "found": len(found_by_level[2]),
            "results": sorted(found_by_level[2], key=lambda x: -x["j1_count"])[:200],
        })
        _atomic_write(OUT_DIR / f"{OUT_STEM}_j1_3plus.json", {
            **base, "level": "j1>=3",
            "found": len(found_by_level[3]),
            "results": sorted(found_by_level[3], key=lambda x: -x["j1_count"])[:200],
        })
        _atomic_write(OUT_DIR / f"{OUT_STEM}_j1_4plus.json", {
            **base, "level": "j1>=4",
            "found": len(found_by_level[4]),
            "results": sorted(found_by_level[4], key=lambda x: -x["j1_count"])[:200],
        })
        _atomic_write(OUT_DIR / f"{OUT_STEM}_top_main5.json", {
            **base, "level": "top_5_of_5_main_numbers",
            "results": top_main5[:TOP_N],
        })
        _atomic_write(OUT_DIR / f"{OUT_STEM}_top_main4.json", {
            **base, "level": "top_4_of_5_main_numbers",
            "results": top_main4[:TOP_N],
        })
        _atomic_write(OUT_DIR / f"{OUT_STEM}_top_special.json", {
            **base, "level": "top_special_number",
            "results": top_special[:TOP_N],
        })

    found_by_level = {2: [], 3: [], 4: []}
    top_main5 = []   # [{seed, count}]
    top_main4 = []
    top_special = []
    scanned_count = 0
    t0 = time.time(); last_checkpoint = t0; last_log = t0

    seed = START
    while seed <= END:
        batch_end = min(seed + BATCH_SEEDS - 1, END)
        seeds_np = np.arange(seed, batch_end + 1, dtype=np.int64)

        j1_counts, main5_counts, main4_counts, spec_counts = scan_batch(
            seeds_np, draw_ids_np, target_masks, target_special, BINOM
        )

        # -- J1 hits (nhu cu) --
        hit_idx = np.where(j1_counts >= MIN_LOG)[0]
        for idx in hit_idx:
            s = int(seeds_np[idx]); cnt = int(j1_counts[idx])
            hits = _details_for_seed(s, draw_ids, draw_ids_np, res, spc, dates)
            entry = {"seed": s, "j1_count": cnt, "jackpot1_hits": hits}
            for level in (2, 3, 4):
                if cnt >= level:
                    found_by_level[level].append(entry)
            print(f"HIT J1 seed={s} J1={cnt}x", flush=True)

        # -- Top 5/5 so chinh (Jackpot 2, khong can DB) --
        min_top5 = top_main5[-1]["count"] if len(top_main5) >= TOP_N else 0
        cand5_idx = np.where(main5_counts > min_top5)[0]
        for idx in cand5_idx:
            s = int(seeds_np[idx]); cnt = int(main5_counts[idx])
            _update_topn(top_main5, s, cnt)
            if cnt >= (top_main5[-1]["count"] if len(top_main5) == TOP_N else 1):
                pass  # da cap nhat, khong can log rieng de tranh spam

        # -- Top 4/5 so chinh --
        min_top4 = top_main4[-1]["count"] if len(top_main4) >= TOP_N else 0
        cand4_idx = np.where(main4_counts > min_top4)[0]
        for idx in cand4_idx:
            s = int(seeds_np[idx]); cnt = int(main4_counts[idx])
            _update_topn(top_main4, s, cnt)

        # -- Top Dac Biet --
        min_topsp = top_special[-1]["count"] if len(top_special) >= TOP_N else 0
        candsp_idx = np.where(spec_counts > min_topsp)[0]
        for idx in candsp_idx:
            s = int(seeds_np[idx]); cnt = int(spec_counts[idx])
            _update_topn(top_special, s, cnt)

        scanned_count = batch_end - START + 1
        now = time.time()
        if now - last_checkpoint >= CHECKPOINT_SEC:
            save_checkpoint(scanned_count, found_by_level, top_main5, top_main4, top_special, done=False)
            last_checkpoint = now
        if now - last_log >= 15:
            rate = scanned_count / (now - t0)
            eta = (END - batch_end) / rate if rate > 0 else 0
            best5 = top_main5[0]["count"] if top_main5 else 0
            best4 = top_main4[0]["count"] if top_main4 else 0
            bestsp = top_special[0]["count"] if top_special else 0
            print(f"  scanned={scanned_count:,}/{END-START+1:,} ({rate:,.0f}/s) ETA {eta/3600:.2f}h "
                  f"f2={len(found_by_level[2])} f3={len(found_by_level[3])} f4={len(found_by_level[4])} "
                  f"best5/5={best5} best4/5={best4} bestDB={bestsp}", flush=True)
            last_log = now

        seed = batch_end + 1

    save_checkpoint(scanned_count, found_by_level, top_main5, top_main4, top_special, done=True)
    elapsed = time.time() - t0
    print(f"\nXong: {scanned_count:,} seed / {elapsed:.0f}s ({scanned_count/elapsed:,.0f}/s). "
          f"J1>=2:{len(found_by_level[2])} J1>=3:{len(found_by_level[3])} J1>=4:{len(found_by_level[4])}")
    print(f"Best 5/5 so chinh: {top_main5[0] if top_main5 else None}")
    print(f"Best 4/5 so chinh: {top_main4[0] if top_main4 else None}")
    print(f"Best Dac Biet: {top_special[0] if top_special else None}")


if __name__ == "__main__":
    main()
