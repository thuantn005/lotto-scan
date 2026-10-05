# Model 11 kỳ trúng — Count + GAP

Đã thêm model dự đoán dựa đúng quy tắc đã được tái tạo từ artifact lịch sử cho 11 kỳ Top-10 đạt 5/5.

## Quy tắc

Tại snapshot kỳ `t`:

1. Chỉ dùng seed history đến `t`.
2. `COUNT` = số kỳ seed xuất hiện.
3. `GAP = t - kỳ xuất hiện gần nhất`.
4. Xếp hạng:
   `COUNT DESC -> GAP ASC -> SEED ASC`.
5. Lấy Top-1/3/5/10.
6. Sinh vé kỳ `t+1` bằng `lotto_common.predict_ticket()`.

## File

- `predict_next_draw_count_gap.py`: dự đoán kỳ kế tiếp.
- `backtest_count_gap.py`: backtest walk-forward, không dùng target khi xếp hạng.
- `build_seed_history.py`: chuyển JSON per-draw thành `data/seed_history.csv`.

## Quan trọng

Model lịch sử 11-hit không lấy trực tiếp `l1-2/*.json` làm nguồn candidate. `l1-2` là kết quả seed đã J1; dùng nó làm history sẽ biến bài toán thành recurrence/second-J1.

Để tái tạo đúng 11-hit, `data/seed_history.csv` phải là **candidate seed history gốc** đã dùng để tạo candidate schedule. Khi chưa có nguồn đó, code vẫn chạy được với một seed-history khác, nhưng kết quả không được gọi là bản tái tạo 11-hit.

## Chạy

```bash
python predict_next_draw_count_gap.py
python backtest_count_gap.py --start 2
```

Output dự đoán:
`predict/next_draw_predict_count_gap.csv`

## Tu dong (GitHub Actions)

`.github/workflows/predict_count_gap.yml` tu chay sau moi lan "Scan V2" xong,
khi `data/all.csv` doi, hoac bam Run workflow. Workflow tu dung history tu
`l1-2/` (`--build-from` / bien `L1_DIRS`), du doan ky ke tiep, luu:

- `predict/next_draw_predict_count_gap.csv` (ban moi nhat)
- `predict/count_gap_history/{ky}_count_gap.csv` (luu tung ky de doi chieu)

`data/seed_history.csv` chi dung tam, khong commit (da them vao .gitignore).
Luu y: nguon `l1-2` khong phai candidate history goc cua ban 11-hit.
