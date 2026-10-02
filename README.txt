MEGA-SCAN - QUET SEED VA DU DOAN MEGA 6/45
==========================================

Cach hoat dong
- scan_mega.cpp: voi moi seed, sinh ve cho tung ky bang
      combined = seed*M1 + draw_id*M2 (mod 2^64)
      rank     = mix64(combined) mod C(45,6)  -> 6 so (colex unrank)
  roi giu seed nao sinh dung ket qua that cua ky do ("seed trung").
- mega_scan.py predict: lay cac seed trung trong N ky gan nhat, sinh ve cho ky ke tiep,
  lay 6 so duoc nhieu seed chon nhat ("ve dong thuan").
- mega_scan.py backtest: walk-forward - dung seed trung truoc ky d de du doan ky d,
  so voi ve ngau nhien.
- mega_scan.py check: doi chieu cac du doan cu trong predict/history voi ket qua that.
- Tat ca ket qua la file .txt (predict/, results/, backtest/).

Chay tren GitHub
1. Tao repo, upload toan bo thu muc nay (data/all.txt da kem du lieu den ky 01570).
2. Tab Actions -> "Mega 6/45 - quet seed va du doan" -> Run workflow.
   Tu dong chay luc 11:45 UTC (18:45 VN) thu 4, 6, CN. Tang "count" de quet nhieu seed hon
   (1 trieu seed x 60 ky ~ 0,13 giay tren 1 nhan; 300 trieu ~ 40 giay-vai phut).
3. Xem predict/next_draw_predict.txt, backtest/backtest.txt, results/check.txt.

Chay tai may
    g++ -O3 -march=native -fopenmp -o scan_mega scan_mega.cpp
    python3 mega_scan.py prepare --window 60
    ./scan_mega --count 100000000
    python3 mega_scan.py predict --recent 20
    python3 mega_scan.py backtest --recent 20 --k 40

LUU Y QUAN TRONG (trung thuc)
- Moi ky quay doc lap. Seed trung ky qua khu chi la trung hop (voi N seed va 8.145.060 ve,
  moi ky se co ~N/8,1 trieu seed "trung" HOAN TOAN NGAU NHIEN). Chung khong mang thong tin
  ve ky sau.
- Backtest mac dinh se cho ket qua xap xi ngau nhien (~0,8 so trung/ve, ky vong 36/45).
  Neu thay lech, hay tang so ky backtest truoc khi tin: vai ky dep la nhieu, khong phai loi the.
- Xac suat Jackpot cua MOI ve van la 1/8.145.060 moi ky. Chi mua so tien ban san sang mat.
