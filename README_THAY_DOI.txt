CAC THAY DOI TRONG PHIEN LAM VIEC NAY - BO CHIEN LUOC "ml", TAP TRUNG VAO "app"
================================================================================
Giai nen de dung, COPY DE LEN dung vi tri cu trong repo (giu nguyen cau
truc thu muc - file .github/workflows/scan_v2_auto.yml phai nam dung
trong .github/workflows/).

A. FILE CAN XOA KHOI REPO (khong con dung nua)
-----------------------------------------------
1. predict_next_draw_ml.py
2. ml_scoring.py
3. predict/next_draw_predict_ml.txt (neu con trong repo)
4. predict/ml_scores.json (neu con trong repo)
5. predict/history/*_ml.txt (tat ca file lich su du doan cu cua ml,
   vi du predict/history/00887_ml.txt)

Chay lenh sau tai goc repo la du (khong anh huong file nao khac):
    git rm -f predict_next_draw_ml.py ml_scoring.py
    git rm -f predict/next_draw_predict_ml.txt predict/ml_scores.json 2>/dev/null
    git rm -f predict/history/*_ml.txt 2>/dev/null

B. FILE DA SUA (COPY DE LEN)
-----------------------------
1. .github/workflows/scan_v2_auto.yml
   - Xoa han job "predict_next_ml" (khong con goi predict_next_draw_ml.py,
     khong con cai scikit-learn/numpy trong runner).
   - Noi lai chuoi push tuan tu (de tranh dua nhau push vao predict/):
       TRUOC: predict_next -> predict_next_ml -> predict_next_ai -> predict_next_ai2 -> predict_next_app
       SAU:   predict_next -> predict_next_ai -> predict_next_ai2 -> predict_next_app
   - "predict_next_app" gio la CHIEN LUOC CHINH cua pipeline, chay sau
     cung trong chuoi predict truoc khi push.
   - SUA LOI: job "cleanup_l1" truoc day needs [..., predict_next,
     predict_next_ml] - tuc no CO THE chay song song voi predict_next_ai/
     ai2/app va don l1_merged truoc khi 3 job do doc xong (loi tiem an,
     khong lien quan ml nhung lo ra khi go bo predict_next_ml). Gio sua
     lai needs [..., predict_next_app] de cleanup_l1 luon cho TOAN BO
     chuoi predict xong roi moi don dep.

2. lotto_common.py
   - Cap nhat docstring dau file: danh sach script dung chung gio la
     predict_next_draw.py / _ai.py / _ai2.py / _app.py (bo _ml.py).
   - Cap nhat comment o phan luu lich su du doan: chien luoc con lai la
     base/ai/ai2/app (bo ml). KHONG doi logic - known_strategies() van
     tu dong glob theo file .txt dang co trong predict/history/, nen tu
     dong "quen" ml ngay khi cac file *_ml.txt bi xoa (muc A.5), khong
     can sua them gi o day hay o check_prediction_result.py.

3. predict_next_draw.py, predict_next_draw_ai.py, predict_next_draw_ai2.py,
   predict_next_draw_ai3.py
   - Chi sua docstring/dong ghi file ket qua (bo nhac predict_next_draw_ml.py
     trong phan "doc lap voi ..."), KHONG doi logic sinh ve.

C. GHI CHU
----------
- predict_next_draw_ai3.py (OpenRouter) hien KHONG nam trong workflow tu
  dong (khong co job predict_next_ai3 trong scan_v2_auto.yml) - chi sua
  docstring cho nhat quan, ban tu quyet dinh co them job cho no hay khong.
- File scan_v2_auto.yml o THU MUC GOC repo (ngoai .github/workflows/) la
  ban cu/thua tu phien lam viec truoc, KHONG phai file workflow that su
  duoc GitHub Actions chay - ban nen xoa no di (hoac dong bo lai) de
  tranh nham lan sau nay, nhung phien nay CHUA dong vao file do.
- Sau khi ap dung, lan chay Actions tiep theo se chi con 4 chien luoc
  song song: base / ai / ai2 / app - dung nhu check_prediction_result.py
  va predict/strategy_stats.json da thiet ke san (tu dong phat hien theo
  file lich su, khong hard-code danh sach nen khong bi anh huong).
