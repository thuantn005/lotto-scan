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

J. predict_next_app: TINH DO DAO DONG TU l2_merged, LUON CHON SEED TU L1 (MOI)
-------------------------------------------------------------------------
Sua lai theo yeu cau: l2_merged CHI dung LAM MAU THONG KE - seed du doan
LUON LUON lay TU L1, KHONG BAO GIO lay truc tiep 1 seed tu l2_merged.

Co che moi:
  1. Gop TOAN BO seed da thang hang (>=2 lan trung J1) tu MOI file
     l2_merged/*.json lai lam 1 mau chung (khong phan biet model nao),
     tinh khoang cach (so ky) GIUA 2 LAN TRUNG LIEN TIEP cua tung seed.
     Tu mau nay TU DONG tinh ra trung vi + [min, max] - KHONG con hardcode
     con so nao (228/14/494) trong code hay workflow nua, tu tinh lai moi
     lan chay dua tren du lieu l2_merged hien co (cang nhieu du lieu qua
     thoi gian, thong ke cang chinh xac hon).
  2. Voi TUNG model, ap dung thong ke o buoc 1 LEN POOL L1 CUA CHINH model
     do: moi seed con trong L1 (chua thang hang) co 1 moc "lan gan nhat no
     xuat hien" (draw_id). Tinh "so ky da trui qua" ke tu moc do toi ky
     sap toi, loc con lai seed co so ky nay trong [min, max], CHON seed
     gan trung vi NHAT.
  3. Model khong co ung vien phu hop (vd qua moi, chua du du lieu) -> DU
     PHONG: random deu tren pool L1 cua model do (nhu ban cu).

3 bien env APP_GAP_TARGET_MEDIAN/APP_GAP_MIN/APP_GAP_MAX VAN con (de
trong = tu tinh, mac dinh cua workflow), dat gia tri neu muon GHI DE thu
cong thay vi tu tinh.

Da doi ham chinh: load_seed_pool_of_file() (chi tra ve set seed) -> 
load_seed_hits_of_file() (tra ve dict seed -> lan xuat hien gan nhat, de
tinh gap tren CHINH seed L1 do). Them compute_gap_stats_from_l2() va
pick_due_seed_from_l1(). Da bo load_l2_candidates()/pick_l2_due_seed() (2
ham cua ban truoc, chon seed truc tiep tu L2 - khong con dung nua).

Da chay thu tren du lieu that (ky 00890, 6 model): mau 1095 khoang cach
tu l2_merged -> trung vi 153 ky, khoang [1, 751] ky (tu tinh, khac voi
mau lon hon tung dua ra truoc do vi day la mau nho hon, dang scan trong
tien trinh) - ca 6/6 model tim duoc seed L1 "den han" phu hop, khong
model nao phai du phong random.

KHONG doi predict/history/{ky}_app.txt (van dinh dang seed_start|seed|
numbers|special|file) nen khong anh huong check_prediction_result.py/
predict_consensus.py. Van la gia thuyet thong ke, khong bao dam - xem
canh bao o dau file predict_next_draw_app.py.

K. SUA LOI: TINH DO DAO DONG RIENG TUNG MODEL, KHONG GOP CHUNG (SUA LAI)
-------------------------------------------------------------------------
Phat hien loi: muc J tinh do dao dong bang cach GOP TOAN BO l2_merged cua
MOI model lai lam 1 mau chung, roi ap dung DUNG 1 con so (vd trung vi 153
ky) cho TAT CA model. Tren du lieu that, trung vi TUNG model lai khac
nhau ro ret:
  seed_start 108477750639  -> trung vi 129.5 ky (mau 252)
  seed_start 1903987714639 -> trung vi 161   ky (mau 285)
  seed_start 2090920810639 -> trung vi 136.5 ky (mau 232)
  seed_start 682305800400  -> trung vi 267   ky (mau 59)
  seed_start 900477750639  -> trung vi 156   ky (mau 267)
-> gop chung se keo cac model co chu ky ngan (129-161 ky) va model co chu
ky dai (267 ky) ve CUNG 1 muc tieu sai lech, lam du doan cua tung model
KHONG con phan anh dung dac tinh rieng cua no.

Sua lai: predict_next_draw_app.py gio tinh do dao dong RIENG cho TUNG
MODEL, tu DUNG file l2_merged/promoted_seed{seed_start cua CHINH model
do}.json (ham compute_gap_stats()). Chi khi model do CHUA co du lieu L2
rieng (qua moi, chua seed nao thang hang - vd ONCE5 vua chay lan dau) moi
DU PHONG tam bang mau gop toan cuc (compute_gap_stats_global(), giu de
tranh model moi phai roi thang ve random ngay tu dau). Khi model do da co
du lieu L2 rieng, KHONG con dung mau gop nua.

predict/next_draw_predict_app.txt gio in ro moi model dang dung nguon
thong ke nao ("tu tinh RIENG cua model" hay "du phong bang mau GOP TOAN
CUC") de de kiem tra. 3 bien env APP_GAP_TARGET_MEDIAN/MIN/MAX (ghi de
thu cong) van hoat dong nhu cu, ap dung DONG LOAT cho moi model neu duoc
dat (dung khi muon ep 1 gia tri chung co chu dich).

L. SUA LOI: CHON NGAU NHIEN TRONG NHOM SEED DONG HANG (SUA LAI)
-------------------------------------------------------------------------
Phat hien loi: sau khi loc theo do dao dong (muc K), buoc "chon seed gan
trung vi nhat" dang chon CO DINH theo seed nho nhat khi hoa (tie-break).
Van de: vi TAT CA seed cung trung 1 draw_id se co CUNG 1 gia tri gap, nen
1 draw_id co the co HANG NGHIN seed dong hang o muc gan trung vi nhat -
tren du lieu that: 1 model co toi 16134 seed dong hang, model khac (vua
chay lan dau, dang du phong toan bo pool) co 8152 seed dong hang. Chon co
dinh theo seed nho nhat nghia la MOI LAN CHAY DEU RA CUNG 1 SEED (mat het
y nghia "random pick" cua app, chi con "chon deterministic theo gap").

Sua lai: pick_due_seed_from_l1() gio tim khoang cach gan trung vi nhat
(best_diff), gom TOAN BO seed dong hang o muc do vao 1 nhom, roi CHON
NGAU NHIEN 1 seed trong nhom (dung random.SystemRandom, dung tinh than
"random pick" cua app - giong cach chon o nhanh du phong l1_random_
fallback). predict/next_draw_predict_app.txt gio in them so seed dong
hang de de kiem tra ("chon ngau nhien trong nhom N seed dong hang gan
nhat").

M. DUNG HISTOGRAM (KHONG CHI 1 TRUNG VI) - SUA LAI THEO PHAN PHOI THUC L2
-------------------------------------------------------------------------
Van de con lai cua muc K/L: ep tat ca ve "gan trung vi nhat" tao ra nhom
"dong hang" QUA LON (thuc te toi 16134 seed cung dong hang) - vi TAT CA
seed cung 1 draw_id thi cung 1 gap, va vi trung vi la 1 diem duy nhat nen
CA VUNG rong xung quanh no deu bi coi la "ngang nhau", bo phi het HINH
DANG thuc su cua phan phoi L2 (co the lech, co nhieu dinh, co vung thua/
day khac nhau).

Sua lai theo yeu cau "tinh lai theo l2" - dung TOAN BO HISTOGRAM cua L2
(khong rut gon con 1 con so):
  1. Chia khoang cach thanh cac BUCKET rong APP_GAP_BUCKET_WIDTH=20 ky
     (vd 0-19, 20-39, 40-59, ...).
  2. Voi TUNG model, dem so khoang cach l2_merged CUA CHINH model do roi
     vao TUNG bucket -> ra 1 histogram RIENG (vi trung vi tung model da
     khac nhau ro ret - xem muc K).
  3. Gom seed L1 cua model do theo CUNG bucket (dua tren "so ky da trui
     qua" ke tu lan xuat hien gan nhat).
  4. CHON 1 bucket theo TRONG SO cua histogram L2 (random.choices co
     trong so - bucket L2 quan sat nhieu hon thi de duoc chon hon, KHONG
     phai luon chon bucket dinh cao nhat mot cach co dinh).
  5. Trong bucket da chon, CHON NGAU NHIEN DEU 1 seed L1 (co the tu vai
     chuc den vai nghin seed, tuy do rong bucket).
  6. Model chua co L2 rieng (qua moi) -> du phong bang histogram GOP
     TOAN CUC. Hoan toan khong co bucket L1 nao trung voi bucket L2 nao
     (hiem) -> du phong cuoi cung: random deu tren toan bo pool L1.

Ket qua chay thu tren du lieu that (ky 00890): 6/6 model ra bucket KHAC
NHAU (40-59, 0-19, 100-119, 160-179, 220-239, 280-299 ky) - phan anh
dung dang phan phoi rieng cua tung model, khong con dong cung 1 diem.

Da doi ham chinh: bo pick_due_seed_from_l1()/compute_gap_stats() (logic
"1 trung vi") -> them get_gaps_from_l2_file()/get_gaps_from_l2_dir() (lay
RAW list gap, khong rut gon) va pick_seed_by_l2_histogram() (chon bucket
co trong so + chon seed ngau nhien trong bucket). Them ENV moi
APP_GAP_BUCKET_WIDTH (mac dinh 20 ky/bucket). 3 bien APP_GAP_TARGET_
MEDIAN/MIN/MAX van giu lai nhung DOI Y NGHIA: gio la che do GHI DE THU
CONG hoan toan (bo qua histogram, ep ve logic "1 diem" cu) - chi dung khi
muon kiem soat thu cong tuyet doi, mac dinh KHONG dat (de trong) de dung
histogram tu dong.

N. GHI DE THU CONG TUYET DOI, RIENG TUNG MODEL (MOI)
-------------------------------------------------------------------------
Theo yeu cau "kiem soat tuyet doi theo tung ky": thay 3 bien
APP_GAP_TARGET_MEDIAN/MIN/MAX (ap dung CHUNG cho CA 6 model) bang 1 bien
JSON APP_MANUAL_OVERRIDE_JSON, cho phep ghi de TUYET DOI RIENG TUNG
MODEL (theo seed_start):

  {"<seed_start>": {"min": X, "max": Y, "target": Z}, ...}

Model nao co seed_start xuat hien trong JSON nay se BO QUA histogram
hoan toan, chi xet seed L1 co "so ky da trui qua" trong [min, max], chon
seed GAN target nhat (random deu neu nhieu seed dong hang). Dat
min=max=target de bat buoc TUYET DOI dung 1 so ky duy nhat (khong con
vung "gan dung"). Model KHONG co trong JSON van tu dong theo histogram
L2 nhu binh thuong (muc M) - co the ghi de 1, vai, hoac tat ca model tuy
y, khong bat buoc tat-ca-hoac-khong-gi nhu truoc.

Vi du: chi ep model 682305800400 dung chinh xac 267 ky, con lai tu dong:
  APP_MANUAL_OVERRIDE_JSON: '{"682305800400": {"min": 267, "max": 267, "target": 267}}'

Da test: model duoc ghi de chon dung seed cach chinh xac 267 ky (408 seed
dong hang, chon ngau nhien 1 trong so do); 5 model con lai van tu dong
theo histogram rieng cua tung model, khong bi anh huong.

Da xoa 3 bien APP_GAP_TARGET_MEDIAN/MIN/MAX (thay hoan toan boi
APP_MANUAL_OVERRIDE_JSON) - can cap nhat lai secret/variable workflow
neu ban da tung dat 3 bien cu nay thu cong.

O. SUA LOI LOGIC: CHON THEO KY (KHONG GOP BUCKET) - SUA LAI
-------------------------------------------------------------------------
Phat hien loi logic that su trong muc M: gop CA 1 BUCKET (rong 20 ky,
tuc 20 ky khac nhau) lai thanh 1 nhom, roi chon ngau nhien tren TOAN BO
seed cua ca 20 ky do gop chung. Van de: 1 trong 20 ky do co the TINH CO
co RAT NHIEU seed hon 19 ky con lai (thuc te bien thien tu nhien giua
cac ky), khi do ky "dong seed" nay se GAN NHU LUON THANG trong buoc chon
ngau nhien (vi no chiem da so trong tong so seed cua ca bucket) - hoan
toan sai lech y nghia "ky nao dang den han", vi don vi thong ke phai la
KY (moi ky = 1 don vi), KHONG PHAI SEED (1 ky co the co tu vai chuc den
hang chuc nghin seed).

Sua lai: tach RO 2 buoc doc lap, lay KY lam don vi xuyen suot:
  1. TINH MAT DO (khong con la histogram theo bucket) tu l2_merged: voi
     TUNG ky cu the ma pool L1 co seed roi vao, uoc luong trong so bang
     cach dem so khoang cach L2 nam trong 1 CUA SO LAM MUOT quanh ky do
     (rong APP_GAP_SMOOTH_WINDOW=20 ky, thay APP_GAP_BUCKET_WIDTH cu) -
     lam muot CHI de co du liieu (vi L2 thua, dem dung 1 diem se toan so
     0), KHONG gop seed cua cac ky lai voi nhau.
  2. CHON 1 KY CU THE (khong phai 1 khoang) theo trong so mat do do -
     moi ky la 1 don vi ung cu rieng biet, KHONG bi anh huong boi so
     luong seed cua chinh ky do.
  3. Trong ky da chon, CHON NGAU NHIEN DEU 1 seed thuoc DUNG ky do.

Da doi ham chinh: pick_seed_by_l2_histogram() (gop bucket) -> 
pick_seed_by_l2_density() (chon ky truoc, chon seed sau, dung
bisect de tra cuu mat do hieu qua tren mau L2 da sap xep). Doi ENV
APP_GAP_BUCKET_WIDTH -> APP_GAP_SMOOTH_WINDOW (van mac dinh 20 ky, y
nghia gio la "do rong cua so lam muot" chu khong con la "do rong
bucket").

Da chay thu tren du lieu that (ky 00890): 6/6 model ra 1 KY RIENG BIET
(cach 300, 2, 199, 400, 259, 136 ky) - so seed trong dung ky do dao dong
tu nhien (398 den 8152 seed, khong con bi 1 ky "dong seed" nao lan at ca
vung 20-ky nhu truoc).

P. LAM RO LAI: "KHOANG CACH" LA SO KY, KHONG PHAI GIA TRI SO SEED (REVERT)
-------------------------------------------------------------------------
Da thu 1 huong sai: hieu nham "khoang cach" la khoang cach GIA TRI SO
giua cac seed (dung seed da thang hang L2 lam "diem neo", chon L1 seed
GAN NHAT ve gia tri so) - DA REVERT lai, vi khong dung y.

Chot lai dinh nghia DUY NHAT cho ca file predict_next_draw_app.py: "khoang
cach" LUON LA SO KY (draw_id) GIUA 2 LAN TRUNG LIEN TIEP cua 1 seed da
thang hang trong l2_merged - KHONG lien quan gi den gia tri so cua seed.

Co che dung (giu nguyen tu muc O, KHONG doi):
  1. L2 cho biet "khoang cach trung binh" (mat do, lam muot) GIUA 2 LAN
     TRUNG cua cac seed da tung lap lai - dung de tinh TRONG SO cho TUNG
     KY cu the ma L1 co seed.
  2. CHON 1 KY CU THE theo trong so mat do do.
  3. Trong DUNG ky da chon (vd 1 ky co 8000 seed L1), CHON NGAU NHIEN DEU
     1 seed - vi ca 8000 seed nay hoan toan giong nhau ve mat du lieu
     (deu chi trung dung 1 lan, dung vao ky do), KHONG co tieu chi nao
     khac (kem gia tri so seed) de phan biet chung mot cach co y nghia
     thong ke, nen xac suat deu nhau moi la lua chon dung.

Da xoa get_l2_seed_gaps_from_file/_dir va pick_seed_by_l2_locality (huong
"khoang cach gia tri so", sai), khoi phuc lai get_gaps_from_l2_file/_dir
va pick_seed_by_l2_density (dung tu muc O).

Q. QUET GIA TANG CHO MODEL PHU #1/#2/#3 (ONCE/ONCE2/ONCE3) - TOI UU
-------------------------------------------------------------------------
Phat hien: scan_per_draw.cpp da co san co che quet gia tang (doc file cu,
chi quet ky CHUA CO trong file) nhung co 1 lo hong - khi gop ket qua cu+
moi, KHONG tu dong loai bo ky da roi ra ngoai cua so LAST_N_DRAWS (cua so
truot). Vi vay truoc day phai dung FORCE_RESCAN=1 cho ca 3 model ONCE/
ONCE2/ONCE3 de tranh file phinh to vo han - doi lai phai QUET LAI TOAN BO
ONCE_LAST_N_DRAWS=500 ky TU DAU moi lan co ky moi (~1.56 ty seed/chunk x
500 ky = rat ton kem), du that ra chi co 1 ky la MOI.

Da sua scan_per_draw.cpp: sau khi gop existing_results + new_results,
THEM buoc PRUNE - loai bo moi draw_id KHONG con nam trong cua so hien tai
(draws_all, da duoc cat theo LAST_N_DRAWS). Da test thuc te 3 lan chay
lien tiep (them 1 ky moi moi lan, KHONG dung FORCE_RESCAN): xac nhan
- Lan 1 (khoi tao): quet 500 ky, ra file co draw_id 11..510.
- Lan 2 (them ky 511): CHI quet 1 ky moi, tu prune bo ky 11, file van
  dung 500 ky, gio la 12..511.
- Lan 3 (them ky 512): tuong tu, file thanh 13..512.
-> Giam ~500 lan khoi luong tinh toan cho 3 model nay.

Van de kien truc phat sinh: cac job scan_once*_chunk chay tren runner
TAM (fresh checkout, khong luu gi giua cac lan chay khac nhau), nen chi
bo FORCE_RESCAN la CHUA DU - chunk job se khong co file cu nao de doc
lai. Da them 3 thu muc PERSIST rieng (moi model 1 thu muc, cam trong
git): ONCE_CHUNK_DIR=l1_chunks_once, ONCE2_CHUNK_DIR=l1_chunks_once2,
ONCE3_CHUNK_DIR=l1_chunks_once3. Co che:
  1. scan_once*_chunk: OUT_DIR = thu muc persist tuong ung (khong con
     "chunk_out" tam nua), BO FORCE_RESCAN. Vi job nay checkout git truoc
     (da co san buoc Checkout), file chunk cu (neu merge job lan truoc
     da commit) se duoc doc lai tu day, quet gia tang thuc su.
  2. merge_once*: sau khi download 20 chunk artifact nhu cu, THEM buoc
     copy 20 file do vao thu muc persist tuong ung, roi git add CUNG
     luc voi l1_merged/l2_merged khi commit - de lan chay SAU co du lieu
     de doc lai.

Da cap nhat ca 3 cap job (scan_once_chunk/merge_once, scan_once2_chunk/
merge_once2, scan_once3_chunk/merge_once3) dong bo: them ENV *_CHUNK_DIR,
sua OUT_DIR/upload-artifact path, them buoc "Luu lai chunk vao thu muc
PERSIST", sua git add trong buoc Commit, sua lai toan bo comment mo ta.
Da kiem tra YAML hop le sau moi buoc sua.

KHONG anh huong ket qua cuoi cung (cung 1 seed range, cung LAST_N_DRAWS,
cung cong thuc check_j1) - CHI thay doi cach dat duoc ket qua do (gia
tang thay vi quet lai tu dau), nen khong can backtest lai gi ca.

R. DASHBOARD (docs/index.html): SUA HIEN THI VE - BAO GOM SO DAC BIET + LOI LAYOUT
-------------------------------------------------------------------------
Theo yeu cau tu https://thuantn005.github.io/lotto-scan/ :

1. So sanh CA so dac biet: badge "X/5" truoc day CHI tinh 5 so chinh, bo
   qua so dac biet du du lieu (score_ticket() trong lotto_common.py) da
   co san field special_hit/is_j1 cho tung ve (generate_dashboard_data.py
   da dua field nay vao docs/data.json tu truoc, chi la frontend chua
   dung). Da sua renderDraws(): them tag "+ĐB" canh badge khi special_hit
   true, va doi badge thanh mau vang rieng (class "j1") khi trung DU CA
   6/6 (is_j1 true) de de phan biet voi trung 5/5 nhung sai dac biet.

2. Loi layout "ve bi lech man hinh, chi hien 1 hang 1 day": .ticket-line
   truoc day KHONG dat flex-wrap (mac dinh nowrap) trong khi .ticket-numbers
   dung flex:1 - tren man hinh hep, ticket-numbers bi BOP NHO lai de nhuong
   cho .ticket-seed/.match-badge, khien .balls-row (dang flex-wrap:wrap)
   phai xuong DONG THU 2 giua chinh 1 ve, vo bo cuc.
   Sua lai:
     - .balls-row: wrap -> nowrap (5 so + dac biet LUON tren CUNG 1 dong,
       khong bao gio tach doi).
     - .ticket-line: them flex-wrap:wrap (neu khong du cho, CA KHOI
       seed/badge se roi xuong dong MOI, khong lam vo hang so).
     - Them @media (max-width:420px): thu nho vien bi (27px -> 22px) va
       AN han .ticket-seed (chi la thong tin ky thuat/debug, khong can
       thiet xem tren dien thoai) - giai phong khong gian de 1 ve gon
       trong 1 dong duy nhat.
   Da test bang wkhtmltoimage (render CSS thuc te + html mau) o 2 do rong
   320px va 360px (dien thoai hep nhat pho bien) - xac nhan moi ve hien
   dung 1 dong, khong con vo bo cuc.

KHONG dong vao generate_dashboard_data.py/data.json (du lieu da du field
can thiet tu truoc) - CHI sua docs/index.html (CSS + JS render).
