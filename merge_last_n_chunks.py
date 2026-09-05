#!/usr/bin/env python3
"""
merge_last_n_chunks.py — Gop nhieu file chunk (moi file la output cua
scan_last_n.cpp cho 1 doan seed con, nhung CUNG mot bo N ky gan nhat)
thanh 1 file merged_seed{BATCH_START}.json duy nhat, cung dinh dang voi
l1_merged/merged_seed*.json (de check_l1_merged.py dung lai duoc nguyen
xi, khong can sua gi).

Khac merge_l1_per_draw.py (gop theo TRUC ky) o cho script nay gop theo
TRUC dai-seed: moi file chunk co cung tap draw_id nhung seed_start/
seed_end khac nhau -> seeds cua tung draw_id duoc NOI lai roi sap xep.

ENV:
    CHUNK_GLOB   - pattern tim file chunk (mac dinh: results_last10/chunk_*.json)
    OUT_DIR      - thu muc ghi file gop (mac dinh: l1_merged_last10)
    BATCH_START  - seed_start cua ca batch (bat buoc, dung lam ten file va seed_start)
    BATCH_END    - seed_end cua ca batch (bat buoc)
"""
import json
import os
import glob
import sys
from collections import defaultdict


def main():
    chunk_glob = os.environ.get("CHUNK_GLOB", "results_last10/chunk_*.json")
    out_dir = os.environ.get("OUT_DIR", "l1_merged_last10")
    batch_start = os.environ.get("BATCH_START")
    batch_end = os.environ.get("BATCH_END")
    if not batch_start or not batch_end:
        print("Can BATCH_START va BATCH_END", file=sys.stderr)
        sys.exit(1)
    batch_start = int(batch_start)
    batch_end = int(batch_end)

    files = sorted(glob.glob(chunk_glob))
    if not files:
        print(f"Khong tim thay file chunk nao khop {chunk_glob}", file=sys.stderr)
        sys.exit(1)
    print(f"Tim thay {len(files)} file chunk, dang gop...", file=sys.stderr)

    seeds_by_draw = defaultdict(set)
    date_by_draw = {}

    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            d = json.load(f)
        for draw in d.get("draws", []):
            did = draw["draw_id"]
            date_by_draw[did] = draw["draw_date"]
            seeds_by_draw[did].update(draw["seeds"])

    draws_out = []
    total_found = 0
    for did in sorted(seeds_by_draw.keys()):
        seeds_sorted = sorted(seeds_by_draw[did])
        total_found += len(seeds_sorted)
        draws_out.append({
            "draw_id": did,
            "draw_date": date_by_draw[did],
            "found": len(seeds_sorted),
            "seeds": seeds_sorted,
        })

    merged = {
        "seed_start": batch_start,
        "seed_end": batch_end,
        "total_draws": len(draws_out),
        "total_found": total_found,
        "draws": draws_out,
    }

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"merged_seed{batch_start}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, separators=(",", ":"))

    print(f"Da gop {len(draws_out)} ky tu {len(files)} chunk -> {out_path}", file=sys.stderr)
    print(f"Tong luot trung J1: {total_found}", file=sys.stderr)
    print(f"MERGED_FILE={out_path}")
    print(f"TOTAL_FOUND={total_found}")


if __name__ == "__main__":
    main()
