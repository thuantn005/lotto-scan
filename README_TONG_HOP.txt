GHI CHU - BAN VA DAY DU (AI phien 1 + Consensus phien 2)
==========================================================================

CACH AP DUNG: giai nen DE LEN thu muc goc cua repo lotto-scan (ghi de 8
file .py + 1 file .yml duoi day), roi commit + push binh thuong. Khong
dong cham gi den du lieu (data/, l1_*, l2_*, once*_seed_state.json...).

=== PHAN 1: KHOI PHUC + SUA LOI CHIEN LUOC AI (Gemini/Groq/OpenRouter) ===

1. lotto_common.py
   - Them lai 2 ham da bi xoa (collect_ai_candidates_per_model,
     build_ai_prompt) MA predict_next_draw_ai.py/ai2.py/ai3.py van con
     import - viet lai theo co che "KHOANG CACH TRUNG BINH" (avg_gap):
     tinh 1 con so trung binh cong cua cac gap (so ky giua 2 lan trung
     lien tiep) tu L2 cua model, uu tien seed co gap HIEN TAI gan
     trung binh do nhat, dua top ung vien cho AI chon + giai thich.
   - Ham moi: get_gaps_from_l2_file(), get_gaps_from_l2_dir(),
     collect_avggap_candidates_per_model().
   - FIX BUG: random.Random(tuple) -> random.Random(chuoi) (Python
     3.11+ khong con cho phep tuple lam seed).

2. predict_next_draw.py (chien luoc "base")
   - FIX BUG CRASH (dang xay ra THAT trong pipeline hien tai): cung
     loi random.Random(tuple) o pick_strongest_seed_per_model(). Da
     kiem chung: job "predict_next" dang crash 100% cac lan chay gan
     day. Sau khi sua, chay binh thuong tro lai.

3. predict_next_draw_ai.py / ai2.py / ai3.py (Gemini / Groq / OpenRouter)
   - Doi sang dung collect_avggap_candidates_per_model(). Them bien
     moi truong L2_DIR (mac dinh "l2_merged"). Van can 1 trong 3
     secret: GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY (da
     luu san tren GitHub Settings > Secrets and variables > Actions).

=== PHAN 2: CHIEN LUOC MOI "CONSENSUS" + CONG CU PHAN TICH ===

4. find_consensus_tickets.py
   - Cong cu PHAN TICH cho 1 ky cu the: tim ve ma NHIEU seed DOC LAP
     (tu L1 va/hoac L2) cung du doan ra GIONG NHAU. Ho tro
     KNOWN_UP_TO_DRAW_ID de backtest DUNG CACH (khong ro ri du lieu
     tuong lai). Tu tinh bang Poisson de biet muc dong thuan nao dang
     tin cay. Tu dong so sanh voi ket qua that neu ky da xac nhan.

5. backtest_consensus_batch.py
   - Chay HANG LOAT (dung numpy, vector hoa - ~3-4 phut cho ~850 ky)
     qua nhieu ky lien tiep, moi ky CHI dung du lieu that su co truoc
     no, tong hop ty le trung trung binh so voi ngau nhien.
   - KET QUA DA CHAY (846 ky, tu ky 1 den 847): trung binh 0.7009/5 -
     THAP HON ca moc ngau nhien 0.7143/5. 0 lan trung tuyet doi. =>
     CHIEN LUOC "LAY TOP/ARGMAX" DA DUOC CHUNG MINH KHONG TOT HON NGAU
     NHIEN.

6. predict_next_draw_consensus.py (chien luoc SAN XUAT "consensus")
   - Voi MOI model, TU TINH muc do dong thuan DAC TRUNG cua model do
     (mode cua phan bo "so seed L2 cung trung 1 ky", tinh tu >=2), roi
     tim ve L1 dat DUNG (hoac gan nhat) muc do do cho ky sap toi.
   - MODEL_LEVELS (env, JSON) cho phep CHI DINH THU CONG muc do (hoac
     1 danh sach nhieu "nhom muc" -> ra nhieu ve/model) cho tung
     model theo seed_start. Mac dinh:
       {"682305800400": [2], "1903987714639": [2, [3,4,5,6,7]]}
     (model 1903987714639 se ra 2 ve: 1 o muc 2 - pho bien nhat that
     su trong lich su L2 cua no -, 1 o muc CAO NHAT thuc su ton tai
     trong khoang 3-7 cho ky dang du doan).
   - Ghi vao predict/next_draw_predict_consensus.txt +
     predict/history/{ky}_consensus.txt (DUNG CHUAN de
     check_prediction_result.py/dashboard TU NHAN DIEN, khong can sua
     gi them o cac script do).
   - **CANH BAO**: day la chien luoc MOI, CHUA duoc backtest rieng
     (backtest_consensus_batch.py hien dang test kieu "lay top/argmax"
     don gian, KHONG PHAI kieu "lay dung muc dac trung" nay). Dung de
     doi chieu song song voi cac chien luoc khac, KHONG phai vi da
     duoc chung minh hieu qua.

7. .github/workflows/scan_v2_auto.yml
   - Them 4 job moi, noi DUNG vao giua chuoi push tuan tu (tranh 2 job
     cung push 1 luc):
       predict_next -> predict_next_app -> predict_next_ai
       -> predict_next_ai2 -> predict_next_ai3 -> predict_next_consensus
       -> predict_consensus -> cleanup_l1
   - predict_next_ai/ai2/ai3: nhu phan 1, can secret tuong ung.
   - predict_next_consensus: chay predict_next_draw_consensus.py,
     KHONG can secret nao (khong goi API ngoai), chi can "pip install
     numpy".
   - Da sua "needs" cua predict_consensus (bao cao tong hop) thanh
     predict_next_consensus de chay sau cung. Da kiem tra YAML hop le
     + thu tu needs dung bang PyYAML.

DA KIEM TRA TRUOC KHI GIAO (tren dung du lieu ban vua upload - ky
00895, KHONG can chinh sua gi them):
  - Cu phap Python ca 8 file .py: OK (ast.parse).
  - Cu phap + thu tu "needs" trong .yml: OK (PyYAML, 20 job).
  - predict_next_draw.py: chay lai KHONG CON crash, ra du 6 du doan.
  - predict_next_draw_consensus.py: chay ra 7 du doan (6 model, rieng
    model 1903987714639 ra 2 ve nhu cau hinh), ghi dung file/history.
  - collect_avggap_candidates_per_model() + find_consensus_tickets.py:
    chay dung tren ca 6 model L1 (~16,4 trieu seed) cua bo du lieu
    moi nhat.

CHUA kiem tra duoc (can ban tu chay tren GitHub Actions, vi phai goi
API that): dinh dang JSON thuc te Gemini/Groq/OpenRouter tra ve co
dung {"picks": [...]} nhu yeu cau khong - neu sai dinh dang, script chi
bo qua model do (ghi log), KHONG lam crash toan bo job.
