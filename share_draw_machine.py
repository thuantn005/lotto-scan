#!/usr/bin/env python3
"""
May trang thai ky CHIA GIAI Doc Dac (PORT tu ShareDrawMachine.kt / .dart).

QUAN TRONG - VI SAO CHAY O DAY (SERVER) CHU KHONG PHAI TREN TUNG MAY NGUOI
DUNG: neu de moi may tu tinh lay trang thai nay (nhu ban dau), may nao mat
mang/tat app dung luc co bien dong (bo lo 1-2 lan kiem tra dinh ky) se tinh
RA KET QUA KHAC voi may khac, du cung theo doi 1 ky quay thuc te. Vi du: may
A thay Doc Dac vuot 12 ty truoc, xac dinh ky chia giai la ngay X; may B bo lo
lan do, lan sau moi thay Doc Dac da giam (do da co nguoi trung) nen KHONG
BAO GIO tu xac dinh duoc ky chia giai, dan den 2 nguoi dung thay 2 trang
thai khac nhau cho CUNG 1 ky quay. Chay 1 LAN o server (co lich chay deu
dan, khong bao gio "mat mang") thi loai bo hoan toan kieu sai lech nay - moi
may doc lai CUNG 1 ket qua da tinh san.

State duoc luu ben trong 1 file JSON git-track (mac dinh
`share_draw_state.json`) giua cac lan chay.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

THRESHOLD_VND = 12_000_000_000
SHARE_DRAW_TIME = "21:00"


def today_vn() -> date:
    # Gio VN = UTC+7, khong phu thuoc muy gio may chay (runner GitHub luon
    # UTC).
    return (datetime.utcnow() + timedelta(hours=7)).date()


def fmt_vnd(vnd: Optional[int]) -> str:
    if vnd is None:
        return "?"
    s = _thousands(vnd)
    if vnd >= 1_000_000_000:
        ty = f"{vnd / 1e9:.1f}"
        return f"{s} (~{ty} tỷ)"
    return s


def _thousands(v: int) -> str:
    s = str(v)
    out = []
    for i, ch in enumerate(s):
        if i > 0 and (len(s) - i) % 3 == 0:
            out.append(".")
        out.append(ch)
    return "".join(out)


def _dm(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}"


def _dmy(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


@dataclass
class ShareDrawState:
    pending: bool = False
    share_date: Optional[str] = None  # yyyy-MM-dd
    reminded: bool = False
    peak_jackpot: int = 0
    trigger_draw_id: Optional[str] = None
    trigger_draw_date: Optional[str] = None
    prev_jackpot: int = 0

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(j: dict) -> "ShareDrawState":
        return ShareDrawState(
            pending=j.get("pending", False),
            share_date=j.get("share_date"),
            reminded=j.get("reminded", False),
            peak_jackpot=j.get("peak_jackpot", 0),
            trigger_draw_id=j.get("trigger_draw_id"),
            trigger_draw_date=j.get("trigger_draw_date"),
            prev_jackpot=j.get("prev_jackpot", 0),
        )


@dataclass
class ShareEvent:
    kind: str  # scheduled | reminder | cancelled | completed
    title_vi: str
    title_en: str
    message_vi: str
    message_en: str
    urgent: bool = False
    id: str = field(default="")


def _reminder_event(share_date: date, peak: int, draw_id: Optional[str]) -> ShareEvent:
    return ShareEvent(
        kind="reminder",
        title_vi="🔔 TỐI NAY: kỳ CHIA GIẢI Độc Đắc Lotto 5/35!",
        title_en="🔔 TONIGHT: Lotto 5/35 jackpot SHARE DRAW!",
        message_vi=(
            f"Kỳ quay {SHARE_DRAW_TIME} hôm nay ({_dmy(share_date)}) là kỳ CHIA GIẢI. "
            f"Độc Đắc ~{fmt_vnd(peak)} sẽ chia cho Giải Nhất (2/6) và Nhì/Ba/Tư/Năm "
            f"(mỗi giải 1/6) nếu không ai trúng trực tiếp. Nhớ mua vé trước giờ quay!"
        ),
        message_en=(
            f"Tonight's {SHARE_DRAW_TIME} draw ({_dmy(share_date)}) is the SHARE draw. "
            f"The ~{fmt_vnd(peak)} jackpot will be split among 1st prize (2/6 shares) and "
            f"2nd/3rd/4th/5th (1/6 each) if nobody wins outright. Get your ticket before the draw!"
        ),
        urgent=True,
        id=f"reminder-{share_date.isoformat()}-{draw_id or ''}",
    )


def check(
    state: ShareDrawState,
    jackpot_vnd: Optional[int],
    last_draw_id: Optional[str],
    last_draw_date: Optional[str],
    recent_jackpots: list[int],
) -> list[ShareEvent]:
    """Cap nhat `state` TAI CHO (giong ban Dart) va tra ve cac su kien MOI
    phat sinh trong lan chay nay (0, 1, hiem khi 2+ su kien)."""
    events: list[ShareEvent] = []
    today = today_vn()

    if jackpot_vnd is None:
        # Khong co du lieu jackpot lan nay (VD scrape that bai) - khong co
        # gi de tinh, giu nguyen state, khong sinh su kien. (Loi mang o day
        # la chuyen cua may chu, khong lien quan gi den viec nguoi dung co
        # thay loi mang tren app cua ho hay khong - 2 khai niem khac nhau.)
        return events

    valid = [v for v in recent_jackpots if v > 1_000_000_000]
    last3 = valid[-3:] if len(valid) >= 3 else valid
    max_last3 = max(last3) if last3 else 0
    dropped_vs_log = len(valid) >= 2 and jackpot_vnd < max_last3 * 0.92

    if state.pending:
        share_date = _parse_date(state.share_date)
        if share_date is None:
            _reset_to(state, jackpot_vnd)
            return events
        peak = state.peak_jackpot if state.peak_jackpot > 0 else 0
        prev = state.prev_jackpot
        dropped_vs_prev = prev > 0 and jackpot_vnd < prev * 0.95
        dropped_vs_peak = jackpot_vnd < peak * 0.90

        if dropped_vs_prev or dropped_vs_peak or dropped_vs_log:
            if today <= share_date:
                events.append(ShareEvent(
                    kind="cancelled",
                    title_vi="🚫 Huỷ kỳ chia giải Lotto 5/35",
                    title_en="🚫 Lotto 5/35 share draw cancelled",
                    message_vi=(
                        f"Đã có người trúng Độc Đắc (~{fmt_vnd(peak)}) trước kỳ chia giải "
                        f"{_dm(share_date)}. Pot quay về ~6 tỷ."
                    ),
                    message_en=(
                        f"Someone already won the jackpot (~{fmt_vnd(peak)}) before the "
                        f"{_dm(share_date)} share draw. Pot resets to ~6 billion VND."
                    ),
                    id=f"cancelled-{share_date.isoformat()}-{state.trigger_draw_id or ''}",
                ))
            else:
                events.append(ShareEvent(
                    kind="completed",
                    title_vi="✅ Kỳ chia giải Lotto 5/35 đã diễn ra",
                    title_en="✅ Lotto 5/35 share draw has taken place",
                    message_vi=(
                        f"Kỳ chia giải ngày {_dmy(share_date)} đã xong (pot trước chia "
                        f"~{fmt_vnd(peak)}). Pot hiện tại: {fmt_vnd(jackpot_vnd)}."
                    ),
                    message_en=(
                        f"The {_dmy(share_date)} share draw is complete (pot before sharing "
                        f"was ~{fmt_vnd(peak)}). Current pot: {fmt_vnd(jackpot_vnd)}."
                    ),
                    id=f"completed-{share_date.isoformat()}-{state.trigger_draw_id or ''}",
                ))
            _reset_to(state, jackpot_vnd)
        else:
            state.peak_jackpot = max(peak, jackpot_vnd)
            if today == share_date and not state.reminded:
                events.append(_reminder_event(share_date, state.peak_jackpot, state.trigger_draw_id))
                state.reminded = True
            elif (today - share_date).days > 2:
                _reset_to(state, jackpot_vnd)  # du lieu tre bat thuong
    else:
        if dropped_vs_log:
            state.peak_jackpot = jackpot_vnd
        else:
            state.peak_jackpot = max(state.peak_jackpot, jackpot_vnd)

        if jackpot_vnd > THRESHOLD_VND:
            trigger = _parse_date(last_draw_date) or today
            share_date = trigger + timedelta(days=1)
            state.pending = True
            state.share_date = share_date.isoformat()
            state.reminded = False
            state.trigger_draw_id = last_draw_id
            state.trigger_draw_date = trigger.isoformat()
            events.append(ShareEvent(
                kind="scheduled",
                title_vi="📅 Đã xác định kỳ CHIA GIẢI Lotto 5/35",
                title_en="📅 Lotto 5/35 SHARE DRAW confirmed",
                message_vi=(
                    f"Độc Đắc {fmt_vnd(jackpot_vnd)} đã vượt 12 tỷ sau kỳ "
                    f"#{last_draw_id or '?'}. Kỳ quay {SHARE_DRAW_TIME} ngày "
                    f"{_dmy(share_date)} là kỳ CHIA GIẢI."
                ),
                message_en=(
                    f"The jackpot ({fmt_vnd(jackpot_vnd)}) passed 12 billion VND after draw "
                    f"#{last_draw_id or '?'}. The {SHARE_DRAW_TIME} draw on {_dmy(share_date)} "
                    f"is the SHARE draw."
                ),
                urgent=True,
                id=f"scheduled-{share_date.isoformat()}-{last_draw_id or ''}",
            ))

    state.prev_jackpot = jackpot_vnd
    return events


def _reset_to(state: ShareDrawState, jackpot: int) -> None:
    state.pending = False
    state.share_date = None
    state.reminded = False
    state.peak_jackpot = jackpot
    state.trigger_draw_id = None
    state.trigger_draw_date = None
    state.prev_jackpot = jackpot
