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
#include <immintrin.h>
using u64 = uint64_t; using i64 = int64_t;
constexpr u64 M1 = 0x9E3779B97F4A7C15ULL, M2 = 0xD1B54A32D192ED03ULL, M3 = 0xBF58476D1CE4E5B9ULL, M4 = 0x94D049BB133111EBULL;
static inline u64 mix64(u64 x) { x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31; return x; }
static std::string genv(const char* n, const char* d) { const char* v = std::getenv(n); return v ? v : d; }

struct E { u64 seed; int cnt; };
struct Ctx { int m, min_hits; const u64 *dM2, *lo1, *od1, *lo2, *od2; };

static void chunk_scalar(u64 lo, u64 hi, const Ctx& c, std::vector<E>& out) {
    for (u64 seed = lo; seed <= hi; seed++) {
        const u64 base = seed * M1; int hits = 0;
        for (int j = 0; j < c.m; j++) { u64 x = mix64(base + c.dM2[j]); u64 l = x & 63;
            if (l == c.lo1[j] || l == c.lo2[j]) { u64 r = x % 15625; hits += ((l == c.lo1[j] && r == c.od1[j]) || (l == c.lo2[j] && r == c.od2[j])); } }
        if (hits >= c.min_hits) out.push_back({seed, hits});
    }
}

// ---------- AVX-512: 4 vector x 8 seed = 32 seed / vong ----------
__attribute__((target("avx512f,avx512dq")))
static u64 chunk_avx512(u64 lo, u64 hi, const Ctx& c, std::vector<E>& out) {
    const __m512i vM3 = _mm512_set1_epi64((long long)M3), vM4 = _mm512_set1_epi64((long long)M4), v63 = _mm512_set1_epi64(63);
    const __m512i lane = _mm512_set_epi64(7*M1,6*M1,5*M1,4*M1,3*M1,2*M1,1*M1,0);
    const __m512i step = _mm512_set1_epi64((long long)(8*M1));
    u64 seed = lo;
    for (; seed + 31 <= hi; seed += 32) {
        __m512i b0 = _mm512_add_epi64(_mm512_set1_epi64((long long)(seed*M1)), lane), b1 = _mm512_add_epi64(b0, step), b2 = _mm512_add_epi64(b1, step), b3 = _mm512_add_epi64(b2, step);
        int hits[32] = {0};
        for (int j = 0; j < c.m; j++) {
            const __m512i dm = _mm512_set1_epi64((long long)c.dM2[j]), l1 = _mm512_set1_epi64((long long)c.lo1[j]), l2 = _mm512_set1_epi64((long long)c.lo2[j]);
            __m512i x0 = _mm512_add_epi64(b0, dm), x1 = _mm512_add_epi64(b1, dm), x2 = _mm512_add_epi64(b2, dm), x3 = _mm512_add_epi64(b3, dm);
#define MIX(x) x = _mm512_xor_si512(x, _mm512_srli_epi64(x, 30)); x = _mm512_mullo_epi64(x, vM3); x = _mm512_xor_si512(x, _mm512_srli_epi64(x, 27)); x = _mm512_mullo_epi64(x, vM4); x = _mm512_xor_si512(x, _mm512_srli_epi64(x, 31));
            MIX(x0) MIX(x1) MIX(x2) MIX(x3)
#undef MIX
#define MSK(x) (unsigned)(_mm512_cmpeq_epi64_mask(_mm512_and_si512(x, v63), l1) | _mm512_cmpeq_epi64_mask(_mm512_and_si512(x, v63), l2))
            unsigned m0 = MSK(x0), m1 = MSK(x1), m2 = MSK(x2), m3 = MSK(x3);
#undef MSK
            if (m0 | m1 | m2 | m3) {
                alignas(64) u64 t[32]; _mm512_store_si512(t, x0); _mm512_store_si512(t+8, x1); _mm512_store_si512(t+16, x2); _mm512_store_si512(t+24, x3);
                unsigned mm = m0 | (m1 << 8) | (m2 << 16) | (m3 << 24);
                while (mm) { int i = __builtin_ctz(mm); mm &= mm - 1; u64 x = t[i], l = x & 63, r = x % 15625;
                    hits[i] += ((l == c.lo1[j] && r == c.od1[j]) || (l == c.lo2[j] && r == c.od2[j])); }
            }
        }
        for (int i = 0; i < 32; i++) if (hits[i] >= c.min_hits) out.push_back({seed + i, hits[i]});
    }
    return seed;
}

// ---------- AVX2: 4 vector x 4 seed = 16 seed / vong (nhan 64-bit bang 3 x mul_epu32) ----------
__attribute__((target("avx2")))
static inline __m256i mul64c(__m256i a, __m256i b, __m256i bs) {
    __m256i lo = _mm256_mul_epu32(a, b), t1 = _mm256_mul_epu32(_mm256_srli_epi64(a, 32), b), t2 = _mm256_mul_epu32(a, bs);
    return _mm256_add_epi64(lo, _mm256_slli_epi64(_mm256_add_epi64(t1, t2), 32));
}
__attribute__((target("avx2")))
static u64 chunk_avx2(u64 lo, u64 hi, const Ctx& c, std::vector<E>& out) {
    const __m256i vM3 = _mm256_set1_epi64x((long long)M3), vM3s = _mm256_srli_epi64(vM3, 32), vM4 = _mm256_set1_epi64x((long long)M4), vM4s = _mm256_srli_epi64(vM4, 32), v63 = _mm256_set1_epi64x(63);
    const __m256i lane = _mm256_set_epi64x(3*M1, 2*M1, 1*M1, 0), step = _mm256_set1_epi64x((long long)(4*M1));
    u64 seed = lo;
    for (; seed + 15 <= hi; seed += 16) {
        __m256i b0 = _mm256_add_epi64(_mm256_set1_epi64x((long long)(seed*M1)), lane), b1 = _mm256_add_epi64(b0, step), b2 = _mm256_add_epi64(b1, step), b3 = _mm256_add_epi64(b2, step);
        int hits[16] = {0};
        for (int j = 0; j < c.m; j++) {
            const __m256i dm = _mm256_set1_epi64x((long long)c.dM2[j]), l1 = _mm256_set1_epi64x((long long)c.lo1[j]), l2 = _mm256_set1_epi64x((long long)c.lo2[j]);
            __m256i x0 = _mm256_add_epi64(b0, dm), x1 = _mm256_add_epi64(b1, dm), x2 = _mm256_add_epi64(b2, dm), x3 = _mm256_add_epi64(b3, dm);
#define MIX(x) x = _mm256_xor_si256(x, _mm256_srli_epi64(x, 30)); x = mul64c(x, vM3, vM3s); x = _mm256_xor_si256(x, _mm256_srli_epi64(x, 27)); x = mul64c(x, vM4, vM4s); x = _mm256_xor_si256(x, _mm256_srli_epi64(x, 31));
            MIX(x0) MIX(x1) MIX(x2) MIX(x3)
#undef MIX
#define MSK(x) (unsigned)_mm256_movemask_pd(_mm256_castsi256_pd(_mm256_or_si256(_mm256_cmpeq_epi64(_mm256_and_si256(x, v63), l1), _mm256_cmpeq_epi64(_mm256_and_si256(x, v63), l2))))
            unsigned mm = MSK(x0) | (MSK(x1) << 4) | (MSK(x2) << 8) | (MSK(x3) << 12);
#undef MSK
            if (mm) {
                alignas(32) u64 t[16]; _mm256_store_si256((__m256i*)t, x0); _mm256_store_si256((__m256i*)(t+4), x1); _mm256_store_si256((__m256i*)(t+8), x2); _mm256_store_si256((__m256i*)(t+12), x3);
                while (mm) { int i = __builtin_ctz(mm); mm &= mm - 1; u64 x = t[i], l = x & 63, r = x % 15625;
                    hits[i] += ((l == c.lo1[j] && r == c.od1[j]) || (l == c.lo2[j] && r == c.od2[j])); }
            }
        }
        for (int i = 0; i < 16; i++) if (hits[i] >= c.min_hits) out.push_back({seed + i, hits[i]});
    }
    return seed;
}
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
    Ctx ctx{m, min_hits, dM2.data(), lo1.data(), od1.data(), lo2.data(), od2.data()};
    const char* force = std::getenv("SIMD"); // "avx512" | "avx2" | "scalar" (mac dinh: tu nhan dien)
    int lvl = __builtin_cpu_supports("avx512f") && __builtin_cpu_supports("avx512dq") ? 2 : __builtin_cpu_supports("avx2") ? 1 : 0;
    if (force) { std::string f = force; if (f == "scalar") lvl = 0; else if (f == "avx2" && lvl >= 1) lvl = 1; }
    fprintf(stderr, "SIMD level=%s\n", lvl == 2 ? "avx512" : lvl == 1 ? "avx2" : "scalar");
    const int T = omp_get_max_threads(); std::vector<std::vector<E>> res(T);
    std::atomic<i64> done{0}; const i64 total = end - start + 1, CH = 1 << 16, nch = (total + CH - 1) / CH;
    auto t0 = std::chrono::steady_clock::now(); double last = 0;
    #pragma omp parallel
    { std::vector<E>& out = res[omp_get_thread_num()];
      #pragma omp for schedule(dynamic, 1)
      for (i64 ch = 0; ch < nch; ch++) {
        u64 lo = (u64)start + (u64)ch * CH, hi = std::min((u64)end, lo + CH - 1);
        u64 nx = lo;
        if (lvl == 2) nx = chunk_avx512(lo, hi, ctx, out); else if (lvl == 1) nx = chunk_avx2(lo, hi, ctx, out);
        if (nx <= hi) chunk_scalar(nx, hi, ctx, out);
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
