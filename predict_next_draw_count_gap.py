#!/usr/bin/env python3
"""
predict_next_draw_count_gap.py

MODEL 11-HIT: Count + GAP
-------------------------
This is the exact ranking rule reconstructed from the historical model that
produced 11 Top-10 5/5 draws:

    1) snapshot only data available through draw t
    2) COUNT = number of historical appearances of each candidate seed
    3) GAP   = t - last appearance of that seed
    4) sort: COUNT DESC, GAP ASC, SEED ASC
    5) take Top-K (default 10)
    6) generate ticket for draw t+1 with lotto_common.predict_ticket()

IMPORTANT
---------
The historical 11-hit artifact was built from a seed-candidate history
(all_strategy_draws / candidate schedule), not from l1-2 J1 result files.
Therefore this script deliberately uses data/seed_history.csv as its source.

Expected seed_history.csv:
    draw_id,seed
or:
    draw_id,seed,votes

Each row means that the seed was a candidate/selected seed at that draw.
If a seed occurs multiple times in one draw, duplicate rows are allowed and
are counted as multiple occurrences only when --count-duplicates is used.
Default behavior deduplicates seed per draw, which is the safer causal form.

NO target draw information is used in ranking.
"""
import argparse, csv, os
from collections import defaultdict
from lotto_common import build_binom, build_rank_to_mask, predict_ticket

def load_history(path, dedupe=True):
    by_draw = defaultdict(set if dedupe else list)
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or "draw_id" not in r.fieldnames or "seed" not in r.fieldnames:
            raise ValueError("seed_history.csv must contain draw_id,seed columns")
        for row in r:
            try:
                d = int(row["draw_id"]); s = int(row["seed"])
            except Exception:
                continue
            if dedupe:
                by_draw[d].add(s)
            else:
                by_draw[d].append(s)
    return by_draw

def build_snapshot(by_draw, upto):
    stats = {}
    for d in sorted(k for k in by_draw if k <= upto):
        for s in by_draw[d]:
            if s not in stats:
                stats[s] = {"count": 0, "last": None}
            stats[s]["count"] += 1
            stats[s]["last"] = d
    rows = []
    for s, x in stats.items():
        gap = upto - x["last"]
        rows.append((s, x["count"], gap))
    rows.sort(key=lambda x: (-x[1], x[2], x[0]))
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="data/seed_history.csv")
    ap.add_argument("--draw", type=int, default=None,
                    help="snapshot draw t; default = maximum draw in history")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default="predict/next_draw_predict_count_gap.csv")
    ap.add_argument("--count-duplicates", action="store_true")
    args = ap.parse_args()

    by_draw = load_history(args.history, dedupe=not args.count_duplicates)
    if not by_draw:
        raise SystemExit("Khong co seed history hop le.")
    t = args.draw if args.draw is not None else max(by_draw)
    next_draw = t + 1

    ranked = build_snapshot(by_draw, t)[:args.top]
    lut = build_rank_to_mask(build_binom())

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["target_draw","rank","seed","count","gap","numbers","special"])
        for rank, (seed, count, gap) in enumerate(ranked, 1):
            nums, sp = predict_ticket(seed, next_draw, lut)
            w.writerow([next_draw, rank, seed, count, gap,
                        "-".join(f"{n:02d}" for n in nums), sp])

    print(f"MODEL=COUNT_GAP")
    print(f"SNAPSHOT_DRAW={t}")
    print(f"PREDICT_DRAW={next_draw}")
    print(f"TOP={args.top}")
    for rank, (seed,count,gap) in enumerate(ranked,1):
        nums,sp=predict_ticket(seed,next_draw,lut)
        print(f"Top-{rank}: seed={seed} count={count} gap={gap} "
              f"ticket={'-'.join(f'{n:02d}' for n in nums)} DB={sp}")
    print(f"OUT={args.out}")

if __name__ == "__main__":
    main()
