CAC FILE DA SUA/THEM TRONG PHIEN LAM VIEC NAY
==============================================
Giai nen de dung, COPY DE LEN dung vi tri cu trong repo
(giu nguyen cau truc thu muc - file .github/workflows/scan_v2_auto.yml
phai nam dung trong .github/workflows/).

1. .github/workflows/scan_v2_auto.yml
   - Go bo co che "3 model phu (708477750639/108477750639/900477750639)
     chi quet 1 LAN DUY NHAT roi khoa vinh vien". Gio ca 5 model deu tu
     dong quet lai MOI KHI CO KY MOI, giong model chinh.
   - Xoa cac file co (once_done.flag/once2_done.flag/once3_done.flag) -
     khong con duoc doc/ghi nua, co the xoa thu cong khoi repo.
   - Them HISTORY_DIR cho 3 job predict_next_ml/ai/ai2 (truoc thieu).
   - Job check_prediction gio commit them predict/strategy_stats.json.

2. lotto_common.py (MOI)
   - Gom code dung chung (sinh ve, doc CSV...) truoc day bi copy-paste
     y het o ca 4 script predict_next_draw*.py.
   - Them ham luu/doc lich su du doan theo TUNG chien luoc rieng
     (save_prediction_history/load_prediction_history/known_strategies).
   - Them ham cham diem trung TUNG PHAN (score_ticket) + moc so sanh
     ngau nhien (EXPECTED_RANDOM_MATCHES).
   - Them ham thong ke cho backtest (load_all_actual_results) va cho
     nguong thang hang L1->L2 (expected_false_positive_count,
     choose_promotion_threshold - HIEN KHONG duoc check_l1_merged.py su
     dung de tu dong doi nguong nua, chi de tham khao/du phong sau nay).

3. predict_next_draw.py / predict_next_draw_ml.py / predict_next_draw_ai.py
   / predict_next_draw_ai2.py (SUA)
   - Dung chung lotto_common.py thay vi code trung lap.
   - BUG DA SUA: truoc day CHI predict_next_draw.py (chien luoc "base")
     ghi lich su du doan de doi chieu sau nay - 3 chien luoc con lai
     (ml/ai/ai2) KHONG BAO GIO duoc kiem chung dung/sai. Gio moi chien
     luoc ghi rieng 1 file predict/history/{ky}_{strategy}.txt.

4. check_prediction_result.py (VIET LAI)
   - Tu dong doi chieu CA 4 chien luoc (khong hard-code danh sach).
   - Them cham diem trung TUNG PHAN (0-5 so + co/khong trung dac biet)
     thay vi chi DUNG/SAI tuyet doi (qua hiem de tich luy du lieu).
   - Tich luy thong ke vao predict/strategy_stats.json, so sanh voi moc
     ngau nhien ly thuyet (~0.714 so/ve) de biet chien luoc nao dang hon
     - hay chi dang ngang muc ngau nhien.
   - Van luu j1_535/ nhu cu khi co model doan DUNG TUYET DOI (J1).

5. backtest_predictions.py (MOI)
   - Backtest WALK-FORWARD (khong nhin truoc tuong lai) chien luoc
     "base" tren TOAN BO lich su co san trong l1_merged/ - cho ra hang
     tram diem du lieu ngay lap tuc thay vi phai cho tung ngay 1 mau.
   - Ket qua da chay thu: model chinh (871 ky backtest) cho trung binh
     0.719 so/ve, gan nhu y het moc ngau nhien ly thuyet 0.714 - CHUA co
     bang chung chien luoc nay hon xac suat ngau nhien.
   - Ghi ra predict/backtest_report.txt + predict/backtest_stats.json.

6. check_l1_merged.py (SUA RUI REVERT LAI THEO YEU CAU)
   - Nguong thang hang L1->L2 VAN LA SO CO DINH PROMOTION_MIN_WEIGHT
     (mac dinh 2, giong het ban goc) - KHONG tu dong dieu chinh theo
     model nhu ban de xuat truoc do (da bi tu choi, giu nguyen hanh vi
     cu theo yeu cau).
   - CHI THEM: in ra log so seed KY VONG dat nguong nay THUAN TUY NGAU
     NHIEN (dung lotto_common.expected_false_positive_count) - CHI DE
     THAM KHAO, KHONG anh huong ket qua thang hang.
   - Phat hien dang chu y (chua sua, chi de tham khao): model chinh
     (682305800400, 872 ky) dang co 58 seed "thang hang" trong khi ly
     thuyet du kien ~39 seed dat nguong do CHI VI TRUNG HOP NGAU NHIEN -
     tuc phan lon co the la nhieu thong ke, khong phai tin hieu that.
