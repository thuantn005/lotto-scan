# J2 Top-10 Backtest

Walk-forward, strict no-leakage. Dữ liệu đọc đúng chỗ:

- Seed L1-1: `l1-1/*.json` (không tìm CSV trong `l1-1/`)
- Kết quả thực tế: `data/all.csv`

Quy tắc: target 724–921; cửa sổ tối đa 200 kỳ trước target; seed của kỳ ngay trước vẫn tính; mỗi seed 1 lần trong pool; Consensus-2 = đúng 2 seed cùng 5 số + số đặc biệt; J2 = đúng 5/5 chính nhưng đặc biệt sai; Top-10 xếp hạng chỉ bằng thông tin trước target. Kết quả xuất `.txt` (per_draw, top_tickets, summary).

Chạy: `python3 backtest_j2_top10.py --data . --start 724 --end 921` (cần numpy).
GitHub Actions: Actions → J2 Top-10 Walkforward Backtest → Run workflow.
