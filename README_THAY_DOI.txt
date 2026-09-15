CAC THAY DOI TRONG PHIEN LAM VIEC NAY - QUET (CHECKPOINT + MODEL 1 CO DINH) VA DU DOAN (BAO CAO TONG HOP)
==========================================================================================================
Giai nen de dung, COPY DE LEN dung vi tri cu trong repo.

A. QUET: THEM CHECKPOINT/RESUME CHO scan_per_draw.cpp
------------------------------------------------------
Job quet co the chay toi 370 phut/lan (5 job x nhieu gio moi ngay) - neu
bi ngat giua chung (het timeout, runner mat ket noi...) TRUOC DAY se mat
TOAN BO tien do, phai quet lai tu dau. Gio da them checkpoint:

- Cu moi CHECKPOINT_INTERVAL_SEC giay (mac dinh 300 = 5 phut), chuong
  trinh ghi lai VI TRI DA QUET cua TUNG THREAD vao file
  "{OUT_PATH}.ckpt.json" (ghi atomic qua file .tmp + rename, khong bao
  gio bi hong do ghi do dang).
- Lan chay SAU, neu checkpoint con ton tai VA khop HOAN TOAN boi
  seed_start/seed_count/num_threads/danh sach draw_id dang quet, se
  RESUME dung vi tri da quet thay vi quet lai tu dau. Neu bat ky yeu to
  nao khac di (co ky moi phat sinh, doi NUM_THREADS...), checkpoint cu
  bi BO QUA mot cach AN TOAN (quet lai tu dau, khong bao gio sai ket qua).
- Checkpoint tu XOA khi quet xong hoan toan (khong tich luy file rac).
- Danh doi CO Y THUC: cac seed "trung" tim duoc trong khoang tu
  checkpoint gan nhat den luc bi ngat SE BI MAT (khong ghi lai ngay lap
  tuc de tranh phai dong bo hoa - mutex - moi lan tim thay 1 seed, von
  RAT hiem xay ra). Phan mat toi da chi la ty le
  (CHECKPOINT_INTERVAL_SEC / tong thoi gian chay) trong tong so thuong
  chi vai tram-vai nghin luot trung ca lan quet - chap nhan duoc de doi
  lay code don gian, an toan, DA TEST (xem muc C).

ENV moi (co gia tri mac dinh, khong bat buoc phai set):
    CHECKPOINT_INTERVAL_SEC  - mac dinh 300 (giay)
    RESUME_FROM_CHECKPOINT   - mac dinh "1", set "0" de luon quet lai tu dau

KHONG can sua workflow de dung tinh nang nay - checkpoint tu hoat dong
ngay khi dung ban scan_per_draw.cpp moi (file .ckpt.json chi la file
tam trong luc chay, khong can commit vao git).

B. QUET: MODEL PHU #1 (ONCE) - DOI TU "SEED NOI TIEP" SANG SEED CO DINH
-------------------------------------------------------------------------
Theo yeu cau: Model phu #1 (truoc day tu dong "nhay" sang dai seed moi
moi lan chay, luu vi tri qua once_seed_state.json) nay quet LAI DUNG 1
dai seed CO DINH moi lan co ky moi - giong het co che cua Model phu #2
(ONCE2) va #3 (ONCE3).

    Seed co dinh moi: ONCE_SEED_START = 1903987714639
    (Model phu #4/ONCE4 - "model 5" - VAN GIU seed noi tiep, khong doi)

File .github/workflows/scan_v2_auto.yml da sua:
    - Bo ONCE_INITIAL_SEED_START/ONCE_STATE_FILE, them ONCE_SEED_START co dinh.
    - Job scan_once_chunk: tinh dai seed truc tiep tu ONCE_SEED_START
      (khong doc state file nua).
    - Job merge_once: bo buoc doc state file + buoc xoa file L1/L2 cua
      lan truoc (khong can nua vi ten file luon co dinh, ghi de moi lan).
      Bo buoc ghi state file ke tiep.
    - Job cleanup_l1: ONCE_SEED_START chuyen sang nhom "seed co dinh"
      (cung FIXED_SEED_START/ONCE2/ONCE3), chi con Model phu #4 (ONCE4)
      con doc once4_seed_state.json.

LUU Y: file once_seed_state.json cu (neu con trong repo tu lan chay
truoc khi ap dung thay doi nay) khong con duoc workflow doc/ghi nua -
co the xoa thu cong (git rm once_seed_state.json) cho gon, khong bat
buoc (de lai cung khong gay loi gi).

C. DA TEST checkpoint/resume (bien dich + chay thu, khong the test tren
   GitHub Actions that tu day)
-------------------------------------------------------------------------
    1. Bien dich scan_per_draw.cpp -O2 -std=c++17 -pthread: THANH CONG,
       khong warning.
    2. Chay quet 2 ty seed, kill -9 giua chung sau ~3s -> checkpoint duoc
       ghi dung (co progress cua ca 4 thread).
    3. Chay lai CUNG tham so -> tu dong phat hien checkpoint KHOP, in ra
       "RESUME (da quet ~X/2000000000 seed truoc do)" dung nhu ky vong.
    4. Chay lai VOI SEED_COUNT KHAC -> tu dong phat hien KHONG KHOP, in
       ra "BO QUA, quet lai tu dau (an toan)" dung nhu ky vong.
    (Chi test tren seed_count nho + thoi gian ngan trong sandbox - ban
    nen theo doi log cua 1-2 lan chay Actions dau tien de yen tam truoc
    khi tin tuong hoan toan, dac biet la dong "[checkpoint] da luu tien
    do vao ...").

D. DU DOAN: THEM BAO CAO TONG HOP predict_consensus.py (TINH NANG MOI)
-------------------------------------------------------------------------
File moi: predict_consensus.py + job moi "predict_consensus" trong
workflow (chay SAU CUNG trong chuoi predict, sau predict_next_app).

Day KHONG PHAI 1 chien luoc du doan moi (khong ky vong hon random) - chi
la BAO CAO THAM KHAO: doc lai lich su du doan cua CA 4 chien luoc hien
co (base/ai/ai2/app) cho CUNG 1 ky sap toi, dem so nao dang duoc NHIEU
ve/chien luoc chon nhat, VA in kem MOC SO SANH ngau nhien (neu tat ca ve
la boc so ngau nhien doc lap thi ky vong xuat hien bao nhieu lan) de
nguoi doc tu danh gia muc trung lap quan sat duoc co dang chu y hay chi
la dao dong binh thuong. Co ghi ro luu y: cac chien luoc DUNG CHUNG
nguon seed tu l1_merged/ nen trung lap cao hon ngau nhien mot chut la
BINH THUONG, khong phai bang chung du doan dung.

Da chay thu tren du lieu that cua repo (ky 00887, lich su co san trong
predict/history/) - ra bao cao dung dinh dang, khong loi.

Ghi ra: predict/next_draw_consensus.txt (file MOI, khong ghi de gi ca,
khong lam thay doi cac chien luoc/file hien co).

E. GHI CHU CHUNG
------------------
- File scan_v2_auto.yml o THU MUC GOC repo (ngoai .github/workflows/)
  van la ban cu/thua tu phien truoc - CHUA dong vao, ban nen tu xoa.
- Tat ca thay doi trong phien nay CHI dong vao scan_per_draw.cpp,
  .github/workflows/scan_v2_auto.yml, va them file moi predict_consensus.py
  - khong dong vao thuat toan sinh ve/seed (predict_ticket, mix64,
    check_j1...) nen KHONG anh huong gi den tinh dung dan cua ket qua da
  co san trong l1_merged/l2_merged/predict/history.

F. BO CHIEN LUOC "AI" (GEMINI/GROQ) - THAY BANG CHI CON "APP" (TINH NANG MOI)
-------------------------------------------------------------------------
Theo yeu cau: bo phan du doan dung AI (goi API ngoai), pipeline predict
gio CHI con 2 chien luoc DOC LAP: "base" (predict_next_draw.py, chon seed
theo so lan tung trung) va "app" (predict_next_draw_app.py, mo phong DUNG
co che sinh so cua app Flutter "San Chia Giai 535").

Da xoa:
  - predict_next_draw_ai.py, predict_next_draw_ai2.py (2 job workflow
    predict_next_ai / predict_next_ai2 goi Gemini/Groq).
  - predict_next_draw_ai3.py (file co san trong repo nhung CHUA BAO GIO
    duoc gan vao workflow - xoa luon cho gon).
  - 2 ham dung rieng cho AI trong lotto_common.py: collect_ai_candidates_
    per_model() va build_ai_prompt() (khong con noi nao goi sau khi xoa 3
    file tren).
  - File output cu: predict/next_draw_predict_ai.txt,
    predict/next_draw_predict_ai2.txt, predict/candidate_pool_ai/,
    predict/candidate_pool_ai2/.
  - (predict/history/{ky}_ai.txt va {ky}_ai2.txt CU van GIU LAI - la lich
    su that da xay ra, khong xoa; chi khong con file MOI nao duoc tao nua.)

Da sua trong .github/workflows/scan_v2_auto.yml:
  - Xoa han 2 job predict_next_ai va predict_next_ai2 (khong con can secret
    GEMINI_API_KEY / GROQ_API_KEY nua).
  - Job predict_next_app gio needs truc tiep predict_next (thay vi
    predict_next_ai2) - chuoi push tuan tu con lai CHI: predict_next ->
    predict_next_app -> predict_consensus -> cleanup_l1.
  - Cap nhat lai cac dong comment mo ta chuoi job cho khop thuc te.

KHONG dong vao thuat toan sinh ve/seed (predict_ticket, mix64...) cua ban
"base"/"app" - 2 chien luoc nay khong doi gi, chi bot di 2 chien luoc AI.
predict_consensus.py KHONG can sua (da tu dong glob known_strategies() -
bao cao se tu dong chi con hien "base/app" khi khong con file lich su ai/
ai2 moi nao duoc tao them).

G. BO LOC "CUA SO UU TIEN" TRONG predict_next_app (TINH NANG MOI)
-------------------------------------------------------------------------
Theo yeu cau: predict_next_draw_app.py KHONG con loc seed theo "cua so
uu tien" (APP_GAP_DRAWS/APP_WINDOW_DRAWS - truoc day chi lay seed cua cac
ky cach hien tai 200-700 ky) nua. Gio chon ngau nhien deu tu TOAN BO pool
seed dang co trong l1_merged/ (gop tat ca cac ky lai lam 1 pool duy nhat).

Da xoa ham window_filter() va load_seed_pool_by_draw() (thay bang
load_seed_pool() tra ve 1 set phang), bo 2 bien env APP_GAP_DRAWS/
APP_WINDOW_DRAWS (ca trong script lan trong job predict_next_app cua
scan_v2_auto.yml). APP_LINE_COUNT (so ve moi ky) van giu nguyen.

KHONG anh huong cong thuc sinh ve (predict_ticket/mix64) - chi bot 1
buoc loc truoc khi chon seed. Vi seed chi anh huong toi CACH sinh ra 5 so
(khong quyet dinh tap so co san), viec loc theo cua so hay khong deu
KHONG lam thay doi phan phoi xac suat ket qua cuoi cung mot cach co y
nghia - van la random, backtest_predictions.py van khong doi.

H. predict_next_app: DU DOAN RIENG TUNG FILE MODEL TRONG l1_merged/ (SUA LAI)
-------------------------------------------------------------------------
Theo yeu cau: predict_next_draw_app.py KHONG con gop seed cua TAT CA file
L1 lai thanh 1 pool chung roi rut ngau nhien N ve (cach lam o muc G) -
GIO LAM Y HET "base" (predict_next_draw.py) o cho MOI FILE trong
l1_merged/ (moi model/dai seed rieng) tu sinh ra 1 ve RIENG CUA MODEL DO.

Khac biet DUY NHAT voi base: cach chon seed TRONG TUNG FILE.
  - base: chon seed MANH NHAT (so lan tung trung cao nhat) trong file do.
  - app : chon NGAU NHIEN DEU 1 seed trong file do (random.SystemRandom,
    khong uu tien seed nao) - dung tinh than "random pick" cua app.

-> So ve sinh ra moi ky = so file model L1 co seed (hien tai la 5 file:
FIXED/ONCE/ONCE2/ONCE3/ONCE4), KHONG con co dinh qua bien APP_LINE_COUNT
nua (da bo bien env nay, ca trong script lan trong scan_v2_auto.yml).

Da doi ham load_seed_pool() (gop TAT CA file, tinh nang o muc G) thanh
load_seed_pool_of_file(fp) (chi gop seed CUA RIENG 1 file). predict/
history/{ky}_app.txt gio co so dong = so file model (giong het cau truc
lich su cua "base"), thay vi luon co APP_LINE_COUNT dong nhu truoc.

KHONG anh huong cong thuc sinh ve (predict_ticket/mix64). predict_
consensus.py khong can sua (van tu dong glob theo lich su).

I. THEM MODEL PHU #5 (ONCE5) - SEED NOI TIEP, CHI QUET 1 KY GAN NHAT (MOI)
-------------------------------------------------------------------------
Theo yeu cau: them 1 model quet moi (model thu 6 cua workflow). Co che
GIONG HET Model phu #4 (ONCE4) - seed TU NOI TIEP (khong lap lai dai cu,
tu doc/ghi state file rieng moi lan chay) - CHI KHAC 1 diem: ONCE5 chi
quet DUNG 1 ky gan nhat (ONCE5_LAST_N_DRAWS=1) thay vi 500 ky nhu ONCE4.

Env moi (trong scan_v2_auto.yml):
  ONCE5_INITIAL_SEED_START = "1700477750639" (diem bat dau lan dau tien,
    sau do tu nhay tiep, khong bao gio quay lai)
  ONCE5_LAST_N_DRAWS       = "1"
  ONCE5_STATE_FILE         = "once5_seed_state.json"
  (dung chung ONCE_BATCH_SIZE voi ONCE4 cho kich thuoc moi chunk)

Job moi:
  - scan_once5_chunk (20 chunk song song, giong het cau truc
    scan_once4_chunk, chi doi state file + LAST_N_DRAWS).
  - merge_once5 (needs: scan_once5_chunk, merge_once4 - xich SAU
    merge_once4 de giu dung nguyen tac CHI 1 job push l1_merged/l2_merged
    tai 1 thoi diem): gop 20 chunk -> l1_merged/merged_seed{X}.json (X =
    seed cua lan nay), thang hang qua check_l1_merged.py, xoa file L1/L2
    cua lan truoc, ghi vi tri ke tiep vao once5_seed_state.json, commit+push.

Da cap nhat needs cua predict_next/predict_next_app/predict_consensus/
cleanup_l1 de bao gom merge_once5 (dam bao doi model 6 quet+merge xong
truoc khi predict, va cleanup_l1 khong xoa nham file cua model 6 vi seed
noi tiep doi ten file moi lan chay - da them logic doc once5_seed_state.json
vao buoc don dep, giong het cach lam voi once4_seed_state.json).

KHONG doi thuat toan sinh ve/seed (scan_per_draw.cpp giu nguyen). File
l1_merged/merged_seed{X}.json cua model 6 se tu dong duoc predict_next
(base) va predict_next_app (moi file = 1 ve rieng, xem muc H) dua vao
tinh toan nhu 5 model con lai - khong can sua predict_next_draw.py hay
predict_next_draw_app.py vi ca 2 deu tu dong glob theo L1_GLOB.
