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
import argparse, csv, glob, json, os
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

def build_history_from_dirs(dirs, out_path):
    """Tu dong dung data/seed_history.csv tu cac thu muc per-draw JSON
    ({"draw_id":..,"seeds":[..]}), vd "l1-2" hoac "l1-2,l1-1"."""
    rows = set()
    for d in [x.strip() for x in dirs.split(",") if x.strip()]:
        for fp in glob.glob(os.path.join(d, "*.json")):
            try:
                with open(fp, encoding="utf-8") as f:
                    j = json.load(f)
                did = int(j["draw_id"])
                for s in j.get("seeds", []):
                    rows.add((did, int(s)))
            except Exception as e:
                print("skip", fp, e)
    if not rows:
        raise SystemExit(f"Khong doc duoc seed nao tu: {dirs}")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["draw_id", "seed"])
        w.writerows(sorted(rows))
    print(f"BUILD_HISTORY rows={len(rows)} dirs={dirs} -> {out_path}")

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
    ap.add_argument("--build-from", default=os.environ.get("L1_DIRS", ""),
                    help="thu muc JSON per-draw de tu dong dung lai history "
                         "(vd 'l1-2'); de trong = dung history co san")
    ap.add_argument("--archive-dir", default=os.environ.get("HISTORY_DIR", ""),
                    help="neu co, luu ban sao du doan vao {dir}/{ky:05d}_count_gap.csv")
    args = ap.parse_args()

    if args.build_from:
        build_history_from_dirs(args.build_from, args.history)
    elif not os.path.exists(args.history):
        raise SystemExit(f"Thieu {args.history}. Dung --build-from l1-2 de tu dong tao.")

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
    if args.archive_dir:
        os.makedirs(args.archive_dir, exist_ok=True)
        arc = os.path.join(args.archive_dir, f"{next_draw:05d}_count_gap.csv")
        with open(args.out, "rb") as fi, open(arc, "wb") as fo:
            fo.write(fi.read())
        print(f"ARCHIVE={arc}")

if __name__ == "__main__":
    main()
