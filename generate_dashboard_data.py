#!/usr/bin/env python3
"""
generate_dashboard_data.py - Tao docs/data.json cho dashboard tinh
(docs/index.html, host qua GitHub Pages) so sanh du doan voi ket qua that.

Doc TAT CA du lieu con trong predict/history/{draw_id}_{strategy}.txt (moi
chien luoc/ky 1 file, xem lotto_common.py) + data/all.csv (ket qua that).
Voi moi (ky, chien luoc) da co CA lich su du doan LAN ket qua that, tinh
diem trung tung ve bang lotto_common.score_ticket() - giong het cach
check_prediction_result.py lam - roi gop lai thanh:

  - "next_draw": ky MOI NHAT dang "cho ket qua" (actual=null, neu co) -
    danh sach ve du doan (kem seed/seed_start tung ve) de hien THANH RIENG
    o dau dashboard.
  - "draws": cac ky DA CO ket qua that, moi ky gom ket qua that + danh
    sach ve tung chien luoc kem so trung VA seed/seed_start tung ve.
  - "summary": tong hop theo TUNG chien luoc (so ve da doi chieu, trung
    binh so trung, ty le trung dac biet, so lan J1) de so sanh voi moc
    ngau nhien (EXPECTED_RANDOM_MATCHES/EXPECTED_RANDOM_SPECIAL_HIT_RATE).
  - "jackpot_wins": danh sach cac lan model doan DUNG TUYET DOI (doc tu
    j1_535/*.json, ghi boi check_prediction_result.py) - dung de ghim
    banner o DAU TRANG khi co.

Neu predict/strategy_stats.json (tich luy tu check_prediction_result.py)
ton tai, uu tien DUNG SO LIEU TICH LUY DO cho phan "summary" (day du hon,
vi lich su tho tung ky se bi don dep - xem prune_old_history()); phan
"draws" (chi tiet tung ky) van chi doc duoc trong pham vi con giu trong
predict/history/ (mac dinh KEEP_LAST_N_HISTORY_DRAWS=60 ky gan nhat).

ENV (deu co mac dinh, giong check_prediction_result.py):
    CSV_PATH        - file CSV cac ky quay (mac dinh data/all.csv)
    HISTORY_DIR     - thu muc lich su du doan (mac dinh predict/history)
    STATS_PATH      - file JSON thong ke tich luy (mac dinh predict/strategy_stats.json)
    OUT_PATH        - file JSON dau ra cho dashboard (mac dinh docs/data.json)
    MAX_DRAWS_OUT   - so ky GAN NHAT dua vao "draws" (mac dinh 60, -1 = tat ca)
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from lotto_common import (
    get_actual_result,
    load_prediction_history,
    known_strategies,
    score_ticket,
    EXPECTED_RANDOM_MATCHES,
    EXPECTED_RANDOM_SPECIAL_HIT_RATE,
)


def load_stats(stats_path):
    p = Path(stats_path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def discover_draw_ids(history_dir):
    d = Path(history_dir)
    if not d.exists():
        return []
    ids = set()
    for p in d.glob("*_*.txt"):
        m = re.match(r"^(\d+)_", p.name)
        if m:
            ids.add(int(m.group(1)))
    return sorted(ids)


def build_draw_entry(csv_path, history_dir, draw_id):
    draw_id_str = f"{draw_id:05d}"
    actual = get_actual_result(csv_path, draw_id_str)
    strategies = known_strategies(history_dir, draw_id)

    entry = {"draw_id": draw_id_str, "actual": None, "strategies": {}}
    actual_numbers = actual_special = None
    if actual:
        nums, special, date = actual
        actual_numbers, actual_special = nums, special
        entry["actual"] = {
            "numbers": sorted(nums),
            "special": special,
            "date": date,
        }

    for strat in strategies:
        entries, _ = load_prediction_history(history_dir, draw_id, strat)
        if not entries:
            continue
        tickets = []
        for e in entries:
            t = {
                "numbers": sorted(e["numbers"]),
                "special": e["special"],
                "seed": e.get("seed"),
                "seed_start": e.get("seed_start"),
                "source_file": e.get("source_file"),
            }
            if actual_numbers is not None:
                t.update(score_ticket(e["numbers"], e["special"], actual_numbers, actual_special))
            tickets.append(t)
        entry["strategies"][strat] = tickets

    return entry


def load_jackpot_wins(j1_dir):
    """Doc TAT CA j1_535/{draw_id}.json (ghi boi check_prediction_result.py
    khi 1 model doan DUNG TUYET DOI ca 5 so + dac biet) - tra ve list, moi
    ky moi nhat len dau."""
    d = Path(j1_dir)
    if not d.exists():
        return []
    wins = []
    for p in sorted(d.glob("*.json")):
        try:
            wins.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    wins.sort(key=lambda w: str(w.get("draw_id", "")), reverse=True)
    return wins


def empty_strategy_summary():
    return {"tickets_checked": 0, "checked_draws": 0, "sum_matches": 0,
            "special_hits": 0, "j1_hits": 0, "matches_hist": {str(i): 0 for i in range(6)}}


def summarize_from_draws(draws):
    """Fallback: tinh summary truc tiep tu 'draws' (dung khi chua co
    predict/strategy_stats.json - vi du lan chay dau tien)."""
    summary = {}
    for d in draws:
        if d["actual"] is None:
            continue
        for strat, tickets in d["strategies"].items():
            s = summary.setdefault(strat, empty_strategy_summary())
            s["checked_draws"] += 1
            for t in tickets:
                if "matches" not in t:
                    continue
                s["tickets_checked"] += 1
                s["sum_matches"] += t["matches"]
                s["matches_hist"][str(t["matches"])] += 1
                if t["special_hit"]:
                    s["special_hits"] += 1
                if t["is_j1"]:
                    s["j1_hits"] += 1
    return summary


def finalize_summary(raw_summary):
    out = {}
    for strat, s in raw_summary.items():
        n = s.get("tickets_checked", 0)
        out[strat] = {
            "tickets_checked": n,
            "checked_draws": s.get("checked_draws", 0),
            "avg_matches": round(s["sum_matches"] / n, 3) if n else 0,
            "special_hit_rate": round(s["special_hits"] / n, 3) if n else 0,
            "j1_hits": s.get("j1_hits", 0),
            "matches_hist": s.get("matches_hist", {}),
        }
    return out


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    stats_path = os.environ.get("STATS_PATH", "predict/strategy_stats.json")
    j1_dir = os.environ.get("J1_DIR", "j1_535")
    out_path = os.environ.get("OUT_PATH", "docs/data.json")
    max_draws_out = int(os.environ.get("MAX_DRAWS_OUT", "60"))

    draw_ids = discover_draw_ids(history_dir)
    if max_draws_out >= 0:
        draw_ids = draw_ids[-max_draws_out:]

    all_entries = [build_draw_entry(csv_path, history_dir, did) for did in draw_ids]
    all_entries.sort(key=lambda d: d["draw_id"], reverse=True)

    # Tach rieng ky dang "cho ket qua" (actual is None, luon la ky MOI NHAT
    # neu co) ra khoi danh sach ky DA CO ket qua that - 2 phan nay hien thi
    # o 2 khu vuc khac nhau tren dashboard (du doan ky toi / lich su da doi
    # chieu), khong nen tron lai voi nhau.
    next_draw = next((d for d in all_entries if d["actual"] is None), None)
    draws = [d for d in all_entries if d["actual"] is not None]

    accumulated = load_stats(stats_path)
    if accumulated:
        summary = finalize_summary(accumulated)
    else:
        summary = finalize_summary(summarize_from_draws(draws))

    jackpot_wins = load_jackpot_wins(j1_dir)

    out = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_baseline": {
            "avg_matches": round(EXPECTED_RANDOM_MATCHES, 3),
            "special_hit_rate": round(EXPECTED_RANDOM_SPECIAL_HIT_RATE, 3),
        },
        "jackpot_wins": jackpot_wins,
        "next_draw": next_draw,
        "summary": summary,
        "draws": draws,
    }

    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Da ghi {out_path}: {len(draws)} ky da co ket qua "
          f"({'co' if next_draw else 'khong co'} ky dang cho ket qua), "
          f"{len(jackpot_wins)} lan trung jackpot, {len(summary)} chien luoc trong summary")


if __name__ == "__main__":
    main()
