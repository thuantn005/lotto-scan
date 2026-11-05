#!/usr/bin/env python3
"""Tao data/draws_rank_mega.txt (draw_id rank 0) tu data/mega_all.csv (dung mega_lib: colex rank, C(45,6))."""
import os
from mega_lib import load_draws, rank, unrank
csv = os.environ.get("CSV_PATH", "data/mega_all.csv"); out = os.environ.get("OUT", "data/draws_rank_mega.txt")
rows = []
for d, date, nums in load_draws(csv):
    r = rank(nums); assert unrank(r) == nums
    rows.append(f"{d} {r} 0")
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write("\n".join(rows) + "\n"); print(f"{len(rows)} ky -> {out}")
