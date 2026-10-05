#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COUNT-GAP TOP-3
Snapshot draw = t -> du doan draw t+1.
Ranking: COUNT giam dan, GAP tang dan, SEED tang dan.
Khong dung target_mask / target_special / matches / j1 de xep hang.
lotto_common.py phai la file goc cua project, KHONG sua.
"""
from pathlib import Path
import csv
import os
import sys

ROOT = Path(__file__).resolve().parent

_default_csv = ROOT / "data" / "candidate_scores_and_tickets.csv"
if not _default_csv.exists():
    _default_csv = ROOT / "candidate_scores_and_tickets.csv"
CSV_FILE = Path(os.environ.get("CANDIDATE_CSV", _default_csv))
OUT_DIR = ROOT / "predict"
OUT_FILE = OUT_DIR / "next_top3.csv"

TOP_K = 3


def find_column(row, names):
    for name in names:
        if name in row:
            return name
    return None


def load_latest_snapshot(path):
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("candidate_scores_and_tickets.csv không có dữ liệu.")
    draw_col = find_column(rows[0], ["draw", "draw_id"])
    seed_col = find_column(rows[0], ["seed"])
    if not draw_col or not seed_col:
        raise ValueError("CSV phải có ít nhất 2 cột: draw và seed.")
    latest_draw = max(int(r[draw_col]) for r in rows)
    latest = [r for r in rows if int(r[draw_col]) == latest_draw]
    return latest_draw, latest, draw_col, seed_col


def rank_count_gap(rows, seed_col):
    for col in ("count", "gap"):
        if col not in rows[0]:
            raise ValueError(f"Thiếu cột bắt buộc: {col}")
    rows = sorted(
        rows,
        key=lambda r: (-int(r["count"]), int(r["gap"]), int(r[seed_col])),
    )
    return rows[:TOP_K]


def load_original_lotto_common():
    sys.path.insert(0, str(ROOT))
    try:
        import lotto_common
        return lotto_common
    except Exception as exc:
        raise RuntimeError(f"Không import được lotto_common.py gốc: {exc}")


_RANK_TO_MASK = None


def generate_ticket(lotto_common, seed, target_draw):
    """Gọi đúng lotto_common.predict_ticket(seed, draw_id, rank_to_mask)."""
    global _RANK_TO_MASK
    if _RANK_TO_MASK is None:
        _RANK_TO_MASK = lotto_common.build_rank_to_mask(lotto_common.build_binom())
    numbers, special = lotto_common.predict_ticket(seed, target_draw, _RANK_TO_MASK)
    return numbers, special


def format_main(numbers):
    return "-".join(f"{int(x):02d}" for x in sorted(numbers))


def format_special(special):
    if isinstance(special, (list, tuple)) and len(special) == 1:
        special = special[0]
    return f"{int(special):02d}"


def latest_actual_draw(path):
    """Ky moi nhat da co ket qua trong data/all.csv (None neu khong doc duoc)."""
    if not path.exists():
        return None
    best = None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                v = int(row.get("draw_id", ""))
            except ValueError:
                continue
            best = v if best is None or v > best else best
    return best


def main():
    latest_draw, rows, draw_col, seed_col = load_latest_snapshot(CSV_FILE)
    target_draw = latest_draw + 1

    # Canh bao/dung neu CSV candidate cu hon du lieu ket qua that.
    actual = latest_actual_draw(ROOT / "data" / "all.csv")
    if actual is not None and actual > latest_draw:
        msg = (f"CANH BAO: snapshot candidate moi nhat la #{latest_draw} nhung "
               f"data/all.csv da co ky #{actual} (cu {actual - latest_draw} ky). "
               f"Du doan se la cho #{target_draw}, KHONG phai ky tiep theo that.")
        print(msg)
        if os.environ.get("STRICT_FRESH") == "1":
            print("STRICT_FRESH=1 -> khong ghi du doan cu.")
            sys.exit(3)
    top3 = rank_count_gap(rows, seed_col)
    lotto_common = load_original_lotto_common()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    output_rows = []
    for rank, row in enumerate(top3, start=1):
        seed = int(row[seed_col])
        numbers, special = generate_ticket(lotto_common, seed, target_draw)
        output_rows.append({
            "target_draw": target_draw,
            "snapshot_draw": latest_draw,
            "rank": rank,
            "seed": seed,
            "count": int(row["count"]),
            "gap": int(row["gap"]),
            "streak": row.get("streak", ""),
            "votes": row.get("votes", ""),
            "main5": format_main(numbers),
            "special": format_special(special),
        })

    fields = ["target_draw", "snapshot_draw", "rank", "seed", "count",
              "gap", "streak", "votes", "main5", "special"]
    with OUT_FILE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(output_rows)

    print("=" * 70)
    print("COUNT-GAP TOP-3 PREDICTION")
    print("=" * 70)
    print(f"Snapshot      : #{latest_draw}")
    print(f"Target        : #{target_draw}")
    print("Ranking       : COUNT ↓, GAP ↑, SEED ↑\n")
    for r in output_rows:
        print(f"TOP-{r['rank']} | SEED={r['seed']} | COUNT={r['count']} | "
              f"GAP={r['gap']} | {r['main5']} | DB={r['special']}")
    print(f"\nOutput: {OUT_FILE}")


if __name__ == "__main__":
    main()
