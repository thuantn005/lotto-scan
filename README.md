# J2 Top-10 Backtest

Chạy backtest walk-forward, strict no-leakage.

- Target: 724–921
- Window: tối đa 200 kỳ hoàn tất trước kỳ target
- L1-1
- Seed không cố định
- Seed xuất hiện ở kỳ ngay trước vẫn được tính
- Mỗi seed chỉ tính một lần trong pool
- Consensus-2 = đúng 2 seed tạo cùng **5 số + số đặc biệt**
- J2 = đúng 5/5 số chính nhưng đặc biệt sai
- Top-10 được xếp hạng chỉ bằng thông tin trước target

GitHub Actions: vào Actions → J2 Top-10 Walkforward Backtest → Run workflow.
