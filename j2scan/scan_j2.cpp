// scan_j2.cpp - Quet seed trung >= MIN_HITS ky 5/5 SO CHINH ("J2", khong can DB). Toi uu toc do:
//  - Da luong OpenMP, chia chunk dong, dung het nhan CPU.
//  - So sanh THANG rank (khong tra bang). C = 324632 = 8 * 40579:
//      rank == tr  <=>  (mix & 7) == (tr & 7)  &&  mix % 40579 == tr % 40579
//  - Vong 1a: mix64 vector hoa (SIMD); vong 1b: loc 3 bit thap, nen ung vien vao mang nho (khong re nhanh).
//    Vong 2: chi ~1/8 cap con lai moi can phep chia du. Do: ~498k seed/s/nhan (goc scan_j1.cpp: 82k).
//  - Khong tinh DB, khong tinh J1.
// ENV: CSV_PATH, OUT_PATH (thu muc/ten, vd out/c.json), SCAN_START, SCAN_END, MIN_HITS (mac dinh 2), THREADS
// Ket qua: <OUT>_m5_list.txt (moi dong "seed so_ky_trung") va <OUT>.json (trang thai, completed).
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <chrono>
#include <atomic>
#include <omp.h>
using u64 = uint64_t; using i64 = int64_t;
constexpr u64 M1 = 0x9E3779B97F4A7C15ULL, M2 = 0xD1B54A32D192ED03ULL, M3 = 0xBF58476D1CE4E5B9ULL, M4 = 0x94D049BB133111EBULL;
constexpr u64 C_ODD = 40579;   // 324632 = 8 * 40579
static i64 BINOM[36][6];
static inline u64 mix64(u64 x) { x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31; return x; }
static i64 mask_to_rank(i64 mask) { i64 r = 0; int k = 1; for (int x = 0; x < 35; x++) if (mask & (1LL << x)) { r += BINOM[x][k]; k++; } return r; }
static std::string genv(const char* n, const char* d) { const char* v = std::getenv(n); return v ? v : d; }
int main() {
    for (int n = 0; n <= 35; n++) for (int k = 0; k <= 5; k++) {
        if (k == 0) { BINOM[n][k] = 1; continue; } if (k > n) { BINOM[n][k] = 0; continue; }
        i64 num = 1, den = 1; for (int i = 0; i < k; i++) { num *= (n - i); den *= (i + 1); } BINOM[n][k] = num / den; }
    std::string csv = genv("CSV_PATH", "data/all.csv"), outp = genv("OUT_PATH", "out/c.json");
    i64 start = std::stoll(genv("SCAN_START", "1")), end = std::stoll(genv("SCAN_END", "1000000"));
    int min_hits = std::stoi(genv("MIN_HITS", "2")); int thr = std::stoi(genv("THREADS", "0"));
    if (thr > 0) omp_set_num_threads(thr);
    // ---- doc CSV (cung dinh dang scan_j1.cpp) ----
    std::vector<u64> ids; std::vector<i64> masks;
    { std::ifstream f(csv); if (!f) { fprintf(stderr, "Khong mo duoc %s\n", csv.c_str()); return 1; }
      std::string line; std::getline(f, line);
      while (std::getline(f, line)) {
        std::vector<std::string> fl; std::string cur; bool q = false;
        for (size_t i = 0; i < line.size(); i++) { char c = line[i];
            if (c == '"') { if (q && i + 1 < line.size() && line[i + 1] == '"') { cur += '"'; i++; } else q = !q; }
            else if (c == ',' && !q) { fl.push_back(cur); cur.clear(); } else cur += c; }
        fl.push_back(cur); if (fl.size() < 5) continue;
        i64 id; try { id = std::stoll(fl[1]); } catch (...) { continue; }
        size_t p = fl[4].find("\"numbers\""); if (p == std::string::npos) continue;
        p = fl[4].find('[', p); size_t e = fl[4].find(']', p); if (p == std::string::npos || e == std::string::npos) continue;
        std::stringstream ss(fl[4].substr(p + 1, e - p - 1)); std::string t; std::vector<int> nums;
        while (std::getline(ss, t, ',')) { try { nums.push_back(std::stoi(t)); } catch (...) {} }
        if (nums.size() != 5) continue; i64 m = 0; for (int x : nums) m |= (1LL << (x - 1));
        ids.push_back((u64)id); masks.push_back(m); } }
    { std::vector<size_t> o(ids.size()); for (size_t i = 0; i < o.size(); i++) o[i] = i;
      std::sort(o.begin(), o.end(), [&](size_t a, size_t b) { return ids[a] < ids[b]; });
      std::vector<u64> i2; std::vector<i64> m2; for (size_t k : o) { i2.push_back(ids[k]); m2.push_back(masks[k]); } ids = i2; masks = m2; }
    const int n = (int)ids.size();
    std::vector<u64> dM2(n), lo3(n), odd(n);
    for (int j = 0; j < n; j++) { dM2[j] = ids[j] * M2; i64 r = mask_to_rank(masks[j]); lo3[j] = (u64)r & 7; odd[j] = (u64)r % C_ODD; }
    fprintf(stderr, "Loaded %d ky. Quet %lld -> %lld, MIN_HITS=%d, threads=%d\n", n, (long long)start, (long long)end, min_hits, omp_get_max_threads());
    size_t sl = outp.find_last_of('/'); std::string dir = sl == std::string::npos ? "." : outp.substr(0, sl);
    std::string stem = outp.substr(0, outp.find_last_of('.') == std::string::npos ? outp.size() : outp.find_last_of('.'));
    struct E { u64 seed; int cnt; };
    const int T = omp_get_max_threads();
    std::vector<std::vector<E>> res(T);
    std::atomic<i64> done{0}; const i64 total = end - start + 1, CH = 1 << 16, nch = (total + CH - 1) / CH;
    auto t0 = std::chrono::steady_clock::now(); double last = 0;
    const u64* pd = dM2.data(); const u64* pl = lo3.data(); const u64* po = odd.data();
    #pragma omp parallel
    {
        std::vector<E>& out = res[omp_get_thread_num()];
        std::vector<u64> mm(n + 8), mv(n + 8); std::vector<int> ii(n + 8);
        #pragma omp for schedule(dynamic, 1)
        for (i64 ch = 0; ch < nch; ch++) {
            u64 lo = (u64)start + (u64)ch * CH, hi = std::min((u64)end, lo + CH - 1);
            for (u64 seed = lo; seed <= hi; seed++) {
                const u64 base = seed * M1; int cnt = 0;
                for (int j = 0; j < n; j++) mv[j] = mix64(base + pd[j]);          // vong 1a: tu vector hoa (SIMD)
                for (int j = 0; j < n; j++) { mm[cnt] = mv[j]; ii[cnt] = j; cnt += ((mv[j] & 7) == pl[j]); }  // 1b: loc, khong re nhanh
                int hits = 0;
                for (int k = 0; k < cnt; k++) hits += ((mm[k] % C_ODD) == po[ii[k]]);   // vong 2: ~1/8 cap
                if (hits >= min_hits) out.push_back({seed, hits});
            }
            i64 d = done.fetch_add(hi - lo + 1) + (hi - lo + 1);
            if (omp_get_thread_num() == 0) {
                double el = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
                if (el - last >= 60) { last = el; fprintf(stderr, "  %lld/%lld (%.0f seed/s) ETA %.2fh\n", (long long)d, (long long)total, d / el, (total - d) / (d / el) / 3600); }
            }
        }
    }
    std::vector<E> all; for (auto& v : res) all.insert(all.end(), v.begin(), v.end());
    std::sort(all.begin(), all.end(), [](const E& a, const E& b) { return a.seed < b.seed; });
    { FILE* f = fopen((stem + "_m5_list.txt").c_str(), "w"); for (auto& e : all) fprintf(f, "%llu %d\n", (unsigned long long)e.seed, e.cnt); fclose(f); }
    { FILE* f = fopen((stem + ".json").c_str(), "w");
      fprintf(f, "{\"status\":\"completed\",\"scan_start\":%lld,\"scan_end\":%lld,\"scanned\":%lld,\"completed\":true,\"min_hits\":%d,\"found\":%zu}", (long long)start, (long long)end, (long long)total, min_hits, all.size()); fclose(f); }
    double el = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    fprintf(stderr, "Xong: %lld seed / %.1fs (%.0f seed/s), found=%zu\n", (long long)total, el, total / el, all.size());
}
