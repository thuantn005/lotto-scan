#!/usr/bin/env python3
"""
predict_consensus.py - Tong hop (KHONG phai "1 chien luoc moi") du doan
cua TAT CA chien luoc dang co (base/ai/ai2/app/...) cho CUNG 1 ky sap
toi, dua vao lich su da luu (predict/history/{draw_id}_{strategy}.txt -
xem lotto_common.save_prediction_history).

Y NGHIA: day la BAO CAO THAM KHAO xem so nao dang duoc NHIEU
chien luoc/ve chon nhat cho ky nay, kem MOC SO SANH voi muc do trung lap
KY VONG THUAN TUY NGAU NHIEN (neu tat ca ve la 5 so boc ngau nhien tu 35
so, khong lien quan gi seed) - de nguoi doc tu danh gia muc trung lap
quan sat duoc co dang chu y hay chi la dao dong ngau nhien binh thuong.
KHONG suy ra day la "so sap ve" - cac chien luoc deu lay seed tu cung
nguon l1_merged/ nen trung lap cao hon random 1 chut la BINH THUONG (dung
nguon du lieu), khong phai bang chung du doan dung.

KHONG ghi vao predict/history/ (day khong phai 1 chien luoc de
check_prediction_result.py doi chieu dung/sai - chi la bao cao tong hop
tuc thoi, tao lai moi lan chay tu du doan MOI NHAT cua tung chien luoc).

ENV:
    CSV_PATH     - file CSV cac ky quay (dung de xac dinh next_draw_id,
                   mac dinh data/all.csv)
    HISTORY_DIR  - thu muc lich su du doan (mac dinh predict/history)
    OUT_PATH     - file bao cao (mac dinh predict/next_draw_consensus.txt)
    TOP_N        - so muc top hien thi cho so chinh (mac dinh 10)
"""

import os
from collections import Counter
from pathlib import Path

from lotto_common import (
    get_next_draw_id,
    known_strategies,
    load_prediction_history,
)


def expected_random_count(num_tickets, value_pool_size, picks_per_ticket):
    """Ky vong so LAN 1 gia tri CU THE xuat hien trong num_tickets ve,
    NEU moi ve la picks_per_ticket gia tri BOC NGAU NHIEN DOC LAP tu
    value_pool_size gia tri (khong lien quan gi seed):
        E[count] = num_tickets * picks_per_ticket / value_pool_size
    Dung lam MOC SO SANH, giong tinh than EXPECTED_RANDOM_MATCHES trong
    lotto_common.py - tranh nguoi doc hieu nham "xuat hien nhieu lan" tu
    dong nghia voi "co kha nang trung cao"."""
    if value_pool_size <= 0:
        return 0.0
    return num_tickets * picks_per_ticket / value_pool_size


def build_report(next_draw_id, history_dir):
    strategies = known_strategies(history_dir, next_draw_id)

    number_counter = Counter()
    special_counter = Counter()
    total_tickets = 0
    per_strategy_ticket_count = {}

    for strat in strategies:
        entries, _ = load_prediction_history(history_dir, next_draw_id, strat)
        if not entries:
            continue
        per_strategy_ticket_count[strat] = len(entries)
        for e in entries:
            total_tickets += 1
            for n in e["numbers"]:
                number_counter[n] += 1
            special_counter[e["special"]] += 1

    return strategies, per_strategy_ticket_count, number_counter, special_counter, total_tickets


def format_report(next_draw_id, strategies, per_strategy_ticket_count,
                   number_counter, special_counter, total_tickets, top_n=10):
    lines = []
    lines.append(f"BAO CAO TONG HOP DU DOAN KY {next_draw_id:05d} - "
                 f"{len(strategies)} chien luoc, {total_tickets} ve")
    lines.append("(KHONG phai 1 chien luoc moi - chi tong hop cac chien luoc "
                 "DOC LAP da co de tham khao, xem docstring file nay)")
    lines.append("")

    if not strategies or total_tickets == 0:
        lines.append("Chua co du doan nao cho ky nay (cac job predict_next_* "
                     "co the chua chay xong, hoac chua co lich su cho ky nay).")
        return "\n".join(lines) + "\n"

    lines.append("So ve theo tung chien luoc: " +
                 ", ".join(f"{s}={c}" for s, c in sorted(per_strategy_ticket_count.items())))
    lines.append("")

    exp_number = expected_random_count(total_tickets, 35, 5)
    exp_special = expected_random_count(total_tickets, 12, 1)
    lines.append(f"Moc ngau nhien (NEU {total_tickets} ve nay la boc ngau nhien "
                 f"DOC LAP, khong lien quan seed):")
    lines.append(f"  moi so chinh (1-35) ky vong xuat hien ~{exp_number:.2f} lan; "
                 f"moi so dac biet (1-12) ky vong ~{exp_special:.2f} lan.")
    lines.append("")

    lines.append(f"TOP {top_n} so chinh xuat hien NHIEU ve nhat:")
    for n, c in number_counter.most_common(top_n):
        flag = " <-- vuot moc ngau nhien" if c > exp_number else ""
        lines.append(f"  so {n:02d}: xuat hien trong {c}/{total_tickets} ve{flag}")
    lines.append("")

    lines.append("TOP so dac biet xuat hien NHIEU ve nhat:")
    for n, c in special_counter.most_common(5):
        flag = " <-- vuot moc ngau nhien" if c > exp_special else ""
        lines.append(f"  DB {n:02d}: xuat hien trong {c}/{total_tickets} ve{flag}")
    lines.append("")

    lines.append("Luu y: cac chien luoc KHONG doc lap hoan toan ve nguon seed "
                 "(deu lay tu cung l1_merged/), nen trung lap CAO HON moc ngau")
    lines.append("nhien mot chut la BINH THUONG (dung nguon du lieu dau vao), "
                 "KHONG co nghia la so do 'sap ve' - backtest_predictions.py")
    lines.append("da xac nhan chua chien luoc nao hon random mot cach co y "
                 "nghia thong ke.")
    return "\n".join(lines) + "\n"


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_consensus.txt")
    top_n = int(os.environ.get("TOP_N", "10"))

    next_draw_id = get_next_draw_id(csv_path)
    strategies, per_strategy_ticket_count, number_counter, special_counter, total_tickets = \
        build_report(next_draw_id, history_dir)

    report = format_report(next_draw_id, strategies, per_strategy_ticket_count,
                            number_counter, special_counter, total_tickets, top_n)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    Path(out_path).write_text(report, encoding="utf-8")

    print(report)
    print(f"NEXT_DRAW_ID={next_draw_id}")
    print(f"TOTAL_STRATEGIES={len(strategies)}")
    print(f"TOTAL_TICKETS={total_tickets}")


if __name__ == "__main__":
    main()
