// scan_m3d.cpp - Quet seed trung >= MIN_HITS ky J1 Max 3D Pro (giai Dac biet: 2 day 3 chu so).
// GIA DINH bo sinh ve (giong lotto-scan): rank = mix64(seed*M1 + draw_id*M2) % 1.000.000 ; a = rank/1000, b = rank%1000.
// MODE=ordered (mac dinh): trung khi (a,b) == (s1,s2).  MODE=either: them (a,b) == (s2,s1) (Dac biet phu, dao thu tu).
// Toi uu: 1.000.000 = 64 * 15625 -> rank==t <=> (mix&63)==(t&63) && mix%15625==t%15625 (loc 6 bit thap, ~1/64 cap can phep chia).
// ENV: DATA_PATH (file "draw_id s1 s2"), OUT_PATH (vd out/c.txt), SCAN_START, SCAN_END, MIN_HITS (2), MODE, THREADS, LAST_N (0 = tat ca)
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <string>
#include <algorithm>
#include <chrono>
#include <atomic>
#include <omp.h>
using u64 = uint64_t; using i64 = int64_t;
constexpr u64 M1 = 0x9E3779B97F4A7C15ULL, M2 = 0xD1B54A32D192ED03ULL, M3 = 0xBF58476D1CE4E5B9ULL, M4 = 0x94D049BB133111EBULL;
static inline u64 mix64(u64 x) { x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31; return x; }
static std::string genv(const char* n, const char* d) { const char* v = std::getenv(n); return v ? v : d; }
int main() {
    std::string dp = genv("DATA_PATH", "m3dscan/data_special.txt"), outp = genv("OUT_PATH", "out/c.txt"), mode = genv("MODE", "ordered");
    i64 start = std::stoll(genv("SCAN_START", "1")), end = std::stoll(genv("SCAN_END", "1000000"));
    int min_hits = std::stoi(genv("MIN_HITS", "2")), thr = std::stoi(genv("THREADS", "0")), lastn = std::stoi(genv("LAST_N", "0"));
    if (thr > 0) omp_set_num_threads(thr);
    std::vector<u64> ids; std::vector<u64> t1, t2;
    { FILE* f = fopen(dp.c_str(), "r"); if (!f) { fprintf(stderr, "Khong mo duoc %s\n", dp.c_str()); return 1; }
      long id, a, b; while (fscanf(f, "%ld %ld %ld", &id, &a, &b) == 3) { ids.push_back(id); t1.push_back(a * 1000 + b); t2.push_back(mode == "either" ? b * 1000 + a : a * 1000 + b); } fclose(f); }
    int n = (int)ids.size(), from = (lastn > 0 && lastn < n) ? n - lastn : 0, m = n - from;
    std::vector<u64> dM2(m), lo1(m), od1(m), lo2(m), od2(m);
    for (int j = 0; j < m; j++) { dM2[j] = ids[from + j] * M2; lo1[j] = t1[from + j] & 63; od1[j] = t1[from + j] % 15625; lo2[j] = t2[from + j] & 63; od2[j] = t2[from + j] % 15625; }
    fprintf(stderr, "Loaded %d ky (dung %d ky cuoi). Quet %lld -> %lld, MIN_HITS=%d, MODE=%s, threads=%d\n", n, m, (long long)start, (long long)end, min_hits, mode.c_str(), omp_get_max_threads());
    struct E { u64 seed; int cnt; };
    const int T = omp_get_max_threads(); std::vector<std::vector<E>> res(T);
    std::atomic<i64> done{0}; const i64 total = end - start + 1, CH = 1 << 16, nch = (total + CH - 1) / CH;
    auto t0 = std::chrono::steady_clock::now(); double last = 0;
    #pragma omp parallel
    { std::vector<E>& out = res[omp_get_thread_num()];
      #pragma omp for schedule(dynamic, 1)
      for (i64 ch = 0; ch < nch; ch++) {
        u64 lo = (u64)start + (u64)ch * CH, hi = std::min((u64)end, lo + CH - 1);
        for (u64 seed = lo; seed <= hi; seed++) {
            const u64 base = seed * M1; int hits = 0;
            for (int j = 0; j < m; j++) { u64 x = mix64(base + dM2[j]); u64 l = x & 63;
                if (l == lo1[j] || l == lo2[j]) { u64 r = x % 15625; hits += ((l == lo1[j] && r == od1[j]) || (l == lo2[j] && r == od2[j])); } }
            if (hits >= min_hits) out.push_back({seed, hits});
        }
        i64 d = done.fetch_add(hi - lo + 1) + (hi - lo + 1);
        if (omp_get_thread_num() == 0) { double el = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
            if (el - last >= 60) { last = el; fprintf(stderr, "  %lld/%lld (%.0f seed/s) ETA %.2fh\n", (long long)d, (long long)total, d / el, (total - d) / (d / el) / 3600); } }
      } }
    std::vector<E> all; for (auto& v : res) all.insert(all.end(), v.begin(), v.end());
    std::sort(all.begin(), all.end(), [](const E& a, const E& b) { return a.seed < b.seed; });
    { FILE* f = fopen(outp.c_str(), "w"); for (auto& e : all) fprintf(f, "%llu %d\n", (unsigned long long)e.seed, e.cnt); fclose(f); }
    double el = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    fprintf(stderr, "Xong: %lld seed / %.1fs (%.0f seed/s), found=%zu\n", (long long)total, el, total / el, all.size());
}
