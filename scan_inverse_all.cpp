// scan_inverse_first2.cpp - nhu scan_inverse.cpp nhung CHI GHI NHAN seed co:
//   - ky trung J1 DAU TIEN  = D1
//   - ky trung J1 THU HAI   = D2      (D1 < D2)
//   tuc la seed khong trung bat ky ky nao < D1, va khong trung ky nao trong (D1, D2).
//   Cac ky sau D2 co the trung them (hit thu 3, 4, ...). MIN_HITS = tong so hit toi thieu (mac dinh 2).
// TIM SEED TRUNG J1 NHIEU LAN bang cach DAO ham hash (khong quet mu).
//
// ve(seed, d): combined = seed*M1 + d*M2 ; mixed = mix64(combined) ; rank = mixed % C ; special = mix64(mixed) % 12 + 1
// mix64 va phep nhan voi M1 deu KHAC 0 va kha nghich (mod 2^64) => voi 1 ky d1 cho truoc, MOI seed trung ky d1
// deu liet ke truc tiep duoc: mixed = r1 + C*k (k = 0..K-1), loc dac biet (1/12), roi suy nguoc ra seed.
// So seed trong KHONG GIAN 64-bit trung ky d1 la ~2^64/3.9tr = 4.7e12 (thay vi quet 1e19 seed).
// Moi ung vien da trung d1 -> kiem tra tiep ky d2 (1 lan hash, qua 1/3.9tr) -> song sot -> dem so ky trung tren TAT CA ky.
// => Voi 1 cap (d1,d2): tim DUOC MOI seed 64-bit trung ca d1 va d2 (~1.2 trieu seed) roi dem hit tren 971 ky.
//    Neu ham hash nay la bo sinh that voi seed 64-bit, seed that se co ~971 hit va phai nam trong tap nay.
//
// Dung: ./scan_inverse_first2 DRAWS_RANK.txt D1 D2 K_BEGIN K_END THREADS OUT.txt [MIN_HITS=3]
//   DRAWS_RANK.txt: moi dong "draw_id rank special" (data/draws_rank.txt)
//   k chay trong [K_BEGIN, K_END); K_total = ceil((2^64 - r1)/C) ~ 5.68e13 (in ra khi chay voi K_END=0)
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <thread>
#include <atomic>
#include <mutex>
#include <chrono>
#include <fstream>
#include <map>
#include <algorithm>
#if defined(SCAN_AVX512) && defined(__AVX512F__) && defined(__AVX512DQ__)
#include <immintrin.h>
#define USE_AVX512 1
#endif
using u64 = uint64_t;
constexpr u64 M1 = 0x9E3779B97F4A7C15ULL, M2 = 0xD1B54A32D192ED03ULL, M3 = 0xBF58476D1CE4E5B9ULL, M4 = 0x94D049BB133111EBULL;
constexpr u64 C = 324632;

static inline u64 mix64(u64 x) { x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31; return x; }
static u64 inv_mul(u64 a) { u64 x = a; for (int i = 0; i < 6; i++) x *= 2 - a * x; return x; }  // nghich dao mod 2^64 (a le)
static inline u64 inv_xs(u64 y, int s) { u64 x = y; for (int i = 0; i < 64 / s + 1; i++) x = y ^ (x >> s); return x; }
static u64 M3I, M4I, M1I;
static inline u64 inv_mix(u64 y) { y = inv_xs(y, 31); y *= M4I; y = inv_xs(y, 27); y *= M3I; y = inv_xs(y, 30); return y; }


#ifdef USE_AVX512
static inline __m512i mix64_v(__m512i x) {   // mix64 cho 8 lane (vpmullq can AVX512DQ)
    x = _mm512_xor_si512(x, _mm512_srli_epi64(x, 30)); x = _mm512_mullo_epi64(x, _mm512_set1_epi64((long long)M3));
    x = _mm512_xor_si512(x, _mm512_srli_epi64(x, 27)); x = _mm512_mullo_epi64(x, _mm512_set1_epi64((long long)M4));
    return _mm512_xor_si512(x, _mm512_srli_epi64(x, 31));
}
// lane i = 1 neu x[i] % 12 == t. x%4 = x&3; x%3 bang gap tong chu so co so 2^s (2^s = 1 mod 3 khi s chan)
static inline __mmask8 eq_mod12_v(__m512i x, u64 t) {
    __m512i y = _mm512_add_epi64(_mm512_srli_epi64(x, 32), _mm512_and_si512(x, _mm512_set1_epi64(0xFFFFFFFFLL)));
    y = _mm512_add_epi64(_mm512_srli_epi64(y, 16), _mm512_and_si512(y, _mm512_set1_epi64(0xFFFFLL)));
    y = _mm512_add_epi64(_mm512_srli_epi64(y, 8),  _mm512_and_si512(y, _mm512_set1_epi64(0xFFLL)));
    y = _mm512_add_epi64(_mm512_srli_epi64(y, 4),  _mm512_and_si512(y, _mm512_set1_epi64(0xFLL)));
    y = _mm512_add_epi64(_mm512_srli_epi64(y, 2),  _mm512_and_si512(y, _mm512_set1_epi64(3LL)));
    y = _mm512_add_epi64(_mm512_srli_epi64(y, 2),  _mm512_and_si512(y, _mm512_set1_epi64(3LL)));   // y <= 6
    __m512i m3 = _mm512_permutexvar_epi64(y, _mm512_setr_epi64(0, 1, 2, 0, 1, 2, 0, 1));
    __mmask8 k3 = _mm512_cmpeq_epi64_mask(m3, _mm512_set1_epi64((long long)(t % 3)));
    __mmask8 k4 = _mm512_cmpeq_epi64_mask(_mm512_and_si512(x, _mm512_set1_epi64(3LL)), _mm512_set1_epi64((long long)(t % 4)));
    return k3 & k4;
}
#endif

struct Draw { int id; u64 rank; int sp; };

int main(int argc, char** argv) {
    if (argc < 7) { fprintf(stderr, "Dung: %s DRAWS_RANK.txt D3 K_BEGIN K_END THREADS OUT.txt [MIN_HITS=3]\n", argv[0]); return 1; }
    M3I = inv_mul(M3); M4I = inv_mul(M4); M1I = inv_mul(M1);
    // tu kiem tra phep dao
    for (u64 t : {1ULL, 12345ULL, 0xDEADBEEFCAFEBABEULL, ~0ULL}) {
        if (inv_mix(mix64(t)) != t || mix64(inv_mix(t)) != t) { fprintf(stderr, "LOI phep dao mix64\n"); return 2; }
        if (t * M1 * M1I != t) { fprintf(stderr, "LOI nghich dao M1\n"); return 2; }
    }
    std::vector<Draw> draws; std::map<int, Draw> byid;
    { std::ifstream f(argv[1]); Draw d; while (f >> d.id >> d.rank >> d.sp) { draws.push_back(d); byid[d.id] = d; } }
    int D1 = atoi(argv[2]);                       // D1 = ky moi nhat (neo), khong con D2 co dinh
    u64 kb = strtoull(argv[3], 0, 10), ke = strtoull(argv[4], 0, 10); int nt = atoi(argv[5]);
    int minhits = argc > 7 ? atoi(argv[7]) : 3;
    std::sort(draws.begin(), draws.end(), [](const Draw& x, const Draw& y) { return x.id < y.id; });
    Draw a = byid.at(D1);
    u64 Ktot = (~0ULL - a.rank) / C + 1;              // so k hop le: a.rank + C*k <= 2^64-1
    if (ke == 0 || ke > Ktot) ke = Ktot;
    fprintf(stderr, "d(moi nhat)=%d (rank %llu, sp %d) %d | K_total=%llu | chay k=[%llu,%llu)\n", D1, (unsigned long long)a.rank, a.sp, 0,
            (unsigned long long)Ktot, (unsigned long long)kb, (unsigned long long)ke);
    const u64 offd1 = (u64)D1 * M2;
    std::atomic<u64> next(kb), cand(0), surv(0), rej(0); std::mutex mu; std::ofstream out(argv[6]);
    std::map<int, u64> hist; const u64 CH = 1 << 22; auto t0 = std::chrono::steady_clock::now();
    auto work = [&]() {
        u64 lc = 0, ls = 0, lrej = 0; std::map<int, u64> lh;
        for (;;) {
            u64 s = next.fetch_add(CH); if (s >= ke) break; u64 e = s + CH < ke ? s + CH : ke;
            auto handle = [&](u64 k) {
                u64 mixed = a.rank + C * k;
                lc++;
                u64 comb = inv_mix(mixed);                                    // = seed*M1 + d1*M2
                ls++;
                u64 seed = (comb - offd1) * M1I; int hits = 0; std::vector<int> hl; bool ok = true;
                for (auto& d : draws) {                                      // draws da sap tang theo id
                    u64 mx = mix64(seed * M1 + (u64)d.id * M2);
                    if (mx % C != d.rank) continue;
                    if (mix64(mx) % 12 == (u64)(d.sp - 1)) {
                        hits++; hl.push_back(d.id);
                    }
                }
                if (!ok) { lrej++; return; }
                lh[hits]++;
                if (hits >= minhits) {
                    std::lock_guard<std::mutex> g(mu);
                    out << seed << " " << hits << " "; for (size_t i = 0; i < hl.size(); i++) out << (i ? "," : "") << hl[i]; out << "\n"; out.flush();
                }
            };
            u64 k = s;
#ifdef USE_AVX512
            {   // loc nhanh 8 lane: mix64(rank + C*k) % 12 == sp-1 (ky d1); lane dat -> handle() scalar
                const __m512i rk = _mm512_set1_epi64((long long)a.rank), cv = _mm512_set1_epi64((long long)C),
                              lane = _mm512_setr_epi64(0, 1, 2, 3, 4, 5, 6, 7);
                for (; k + 8 <= e; k += 8) {
                    __m512i kv = _mm512_add_epi64(_mm512_set1_epi64((long long)k), lane);
                    __m512i mixed = _mm512_add_epi64(rk, _mm512_mullo_epi64(kv, cv));
                    __mmask8 m = eq_mod12_v(mix64_v(mixed), (u64)(a.sp - 1));
                    while (m) { int i = __builtin_ctz(m); m &= m - 1; handle(k + i); }
                }
            }
#endif
            for (; k < e; k++) {
                if (mix64(a.rank + C * k) % 12 != (u64)(a.sp - 1)) continue;   // dac biet ky d1
                handle(k);
            }
        }
        cand += lc; surv += ls; rej += lrej; std::lock_guard<std::mutex> g(mu); for (auto& p : lh) hist[p.first] += p.second;
    };
    std::vector<std::thread> th; for (int i = 0; i < nt; i++) th.emplace_back(work); for (auto& t : th) t.join();
    double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    printf("k=[%llu,%llu) | ung vien trung d1: %llu | song sot (trung ca d1,d2): %llu | loai (co hit truoc d1 / giua d1,d2): %llu | %.1fs (%.1f trieu k/s)\n",
           (unsigned long long)kb, (unsigned long long)ke, (unsigned long long)cand.load(), (unsigned long long)surv.load(), (unsigned long long)rej.load(), sec, (ke - kb) / sec / 1e6);
    printf("Phan bo so hit (tren %zu ky) cua cac seed hop le (d1 dau, d2 thu 2):", draws.size()); for (auto& p : hist) printf(" %d:%llu", p.first, (unsigned long long)p.second); printf("\n");
    return 0;
}
