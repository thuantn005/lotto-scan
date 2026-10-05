#!/usr/bin/env python3
"""
build_seed_history.py

Build data/seed_history.csv from a directory of per-draw JSON files.

The JSON format used by this project is:
{"draw_id": ..., "seeds": [...]}

Usage:
    python build_seed_history.py --input l1-2 --output data/seed_history.csv

IMPORTANT:
For reproducing the historical 11-hit Count+GAP model, the input must be
the ORIGINAL candidate-seed history used to make the candidate schedule.
Do NOT substitute l1-2 merely because it is available: l1-2 contains seeds
that already hit J1 and would create the "second J1" recurrence problem.
This utility is generic so the project can ingest the correct candidate
history when supplied.
"""
import argparse, csv, glob, json, os

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="data/seed_history.csv")
    args=ap.parse_args()
    rows=[]
    for fp in glob.glob(os.path.join(args.input,"*.json")):
        try:
            d=json.load(open(fp,encoding="utf-8"))
            did=int(d["draw_id"])
            for s in d.get("seeds",[]):
                rows.append((did,int(s)))
        except Exception as e:
            print("skip",fp,e)
    rows=sorted(set(rows))
    os.makedirs(os.path.dirname(args.output) or ".",exist_ok=True)
    with open(args.output,"w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["draw_id","seed"]); w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {args.output}")

if __name__=="__main__":
    main()
