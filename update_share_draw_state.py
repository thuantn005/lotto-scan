#!/usr/bin/env python3
"""
Chay may trang thai "ky CHIA GIAI" (share_draw_machine.py) sau moi lan cao
full_results.json, ghi ket qua NGAY VAO trong ban ghi moi nhat cua
full_results.json (truong "share_state") de app doc 1 lan la co du - khong
can them 1 file/URL rieng.

State ben ngoai (share_draw_state.json) duoc GIT COMMIT giua cac lan chay -
day la "bo nho" cua may trang thai, thay cho viec de moi app tu nho lay
tren may cua ho (xem giai thich trong share_draw_machine.py).

Cach dung:
  python3 update_share_draw_state.py \
      --results data/full_results.json \
      --state share_draw_state.json \
      --csv data/all.csv

In ra "NEW_EVENT=true" hoac "NEW_EVENT=false" (dong cuoi, stdout) de
workflow doc va quyet dinh co goi FCM hay khong ngay ca khi jackpot khong
doi (vi du: su kien "reminder" chi phu thuoc NGAY HOM NAY, khong phu thuoc
jackpot co doi hay khong).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from share_draw_machine import ShareDrawState, check


def load_recent_jackpots(csv_path: str, product: str, limit: int = 6) -> list[int]:
    """Doc vai gia tri Doc Dac gan nhat tu file CSV lich su (dung de phat
    hien pot vua reset - xem droppedVsLog trong share_draw_machine.py).
    An toan tra ve [] neu doc loi (khong lam sap toan bo script)."""
    try:
        rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 5 or row[0] != product:
                    continue
                try:
                    parsed = json.loads(row[4])
                except (json.JSONDecodeError, IndexError):
                    continue
                jackpot = parsed.get("jackpot_value") or parsed.get("jackpotVnd")
                if isinstance(jackpot, int):
                    rows.append(jackpot)
        return rows[-limit:]
    except FileNotFoundError:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="data/full_results.json")
    ap.add_argument("--state", default="share_draw_state.json")
    ap.add_argument("--csv", default="data/all.csv")
    args = ap.parse_args()

    results_path = Path(args.results)
    state_path = Path(args.state)

    try:
        records = json.loads(results_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"LOI: khong doc duoc {args.results}: {e}", file=sys.stderr)
        print("NEW_EVENT=false")
        return 1
    if not records:
        print(f"CANH BAO: {args.results} rong, bo qua.", file=sys.stderr)
        print("NEW_EVENT=false")
        return 0

    latest = records[-1]

    if state_path.exists():
        state = ShareDrawState.from_json(json.loads(state_path.read_text(encoding="utf-8")))
    else:
        state = ShareDrawState()

    recent_jackpots = load_recent_jackpots(args.csv, latest.get("product", "lotto535"))

    events = check(
        state=state,
        jackpot_vnd=latest.get("jackpot_value"),
        last_draw_id=latest.get("draw_id"),
        last_draw_date=latest.get("draw_date"),
        recent_jackpots=recent_jackpots,
    )

    state_path.write_text(json.dumps(state.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")

    last_event = None
    if events:
        # Thuong chi co 1 su kien/lan chay; neu (hiem) co hon 1, uu tien su
        # kien CUOI (quan trong hon, vi du "cancelled" ghi de "scheduled"
        # cung ky) - giong thu tu ma ban Dart truoc day xu ly.
        e = events[-1]
        last_event = {
            "id": e.id,
            "kind": e.kind,
            "title_vi": e.title_vi,
            "title_en": e.title_en,
            "message_vi": e.message_vi,
            "message_en": e.message_en,
            "urgent": e.urgent,
        }

    latest["share_state"] = {
        "pending": state.pending,
        "share_date": state.share_date,
        "peak_jackpot": state.peak_jackpot,
        "trigger_draw_id": state.trigger_draw_id,
        "last_event": last_event,
    }
    records[-1] = latest
    results_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    if events:
        for e in events:
            print(f"Su kien moi: {e.kind} ({e.id})", file=sys.stderr)
    print("NEW_EVENT=true" if events else "NEW_EVENT=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
