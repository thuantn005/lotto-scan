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
