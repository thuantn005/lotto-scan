// scan_j1.cpp v2 — dung LUT (lookup table) rank->mask, nhanh hon 80x so voi tinh dong.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <chrono>
#include <algorithm>

using u64 = uint64_t;
using i64 = int64_t;

constexpr u64 M1 = 0x9E3779B97F4A7C15ULL;
constexpr u64 M2 = 0xD1B54A32D192ED03ULL;
constexpr u64 M3 = 0xBF58476D1CE4E5B9ULL;
constexpr u64 M4 = 0x94D049BB133111EBULL;
constexpr i64 C  = 324632;

static i64 BINOM[36][6];
static std::vector<i64> RANK_TO_MASK;  // LUT

void build_binom() {
    for (int n = 0; n <= 35; n++)
        for (int k = 0; k <= 5; k++) {
            if (k == 0) { BINOM[n][k] = 1; continue; }
            if (k > n) { BINOM[n][k] = 0; continue; }
            i64 num = 1, den = 1;
            for (int i = 0; i < k; i++) { num *= (n - i); den *= (i + 1); }
            BINOM[n][k] = num / den;
        }
}

inline i64 rank_mask_calc(i64 r) {
    i64 mask = 0, rem = r;
    for (int k = 5; k >= 1; k--) {
        int x = k - 1;
        while (BINOM[x + 1][k] <= rem) x++;
        mask |= (1LL << x);
        rem -= BINOM[x][k];
    }
    return mask;
}

void build_lut() {
    RANK_TO_MASK.resize(C);
    for (i64 r = 0; r < C; r++) RANK_TO_MASK[r] = rank_mask_calc(r);
}

inline u64 mix64(u64 x) {
    x ^= x >> 30; x *= M3;
    x ^= x >> 27; x *= M4;
    x ^= x >> 31;
    return x;
}

inline int popcount64(i64 x) { return __builtin_popcountll((u64)x); }

struct Draw { u64 draw_id; i64 mask; int special; };

int main() {
    build_binom();
    build_lut();

    auto getenv_str = [](const char* name, const char* def) -> std::string {
        const char* v = std::getenv(name);
        return v ? std::string(v) : std::string(def);
    };
    auto getenv_i64 = [&](const char* name, i64 def) -> i64 {
        std::string s = getenv_str(name, "");
        return s.empty() ? def : std::stoll(s);
    };

    std::string csv_path = getenv_str("CSV_PATH", "data/all.csv");
    std::string out_path = getenv_str("OUT_PATH", "results/chunk.json");
    i64 start = getenv_i64("SCAN_START", 1);
    i64 end   = getenv_i64("SCAN_END", 500000000);
    i64 min_log = getenv_i64("MIN_LOG", 2);

    std::vector<Draw> draws;
    {
        std::ifstream f(csv_path);
        if (!f) { fprintf(stderr, "Khong mo duoc %s\n", csv_path.c_str()); return 1; }
        std::string line;
        std::getline(f, line);
        while (std::getline(f, line)) {
            std::vector<std::string> fields;
            std::string cur;
            bool in_quotes = false;
            for (size_t i = 0; i < line.size(); i++) {
                char c = line[i];
                if (c == '"') {
                    if (in_quotes && i+1 < line.size() && line[i+1] == '"') { cur += '"'; i++; }
                    else in_quotes = !in_quotes;
                } else if (c == ',' && !in_quotes) { fields.push_back(cur); cur.clear(); }
                else cur += c;
            }
            fields.push_back(cur);
            if (fields.size() < 5) continue;

            i64 draw_id;
            try { draw_id = std::stoll(fields[1]); } catch (...) { continue; }
            std::string rj = fields[4];

            auto extract_nums = [](const std::string& s, const std::string& key) -> std::vector<int> {
                std::vector<int> out;
                size_t p = s.find(key);
                if (p == std::string::npos) return out;
                p = s.find('[', p);
                size_t q = s.find(']', p);
                if (p == std::string::npos || q == std::string::npos) return out;
                std::string inner = s.substr(p+1, q-p-1);
                std::stringstream ss(inner);
                std::string tok;
                while (std::getline(ss, tok, ',')) { try { out.push_back(std::stoi(tok)); } catch (...) {} }
                return out;
            };

            std::vector<int> nums = extract_nums(rj, "\"numbers\"");
            std::vector<int> spv  = extract_nums(rj, "\"special_numbers\"");
            if (nums.size() != 5 || spv.empty()) continue;

            i64 mask = 0;
            for (int n : nums) mask |= (1LL << (n - 1));
            draws.push_back({(u64)draw_id, mask, spv[0]});
        }
    }
    std::sort(draws.begin(), draws.end(), [](const Draw& a, const Draw& b) { return a.draw_id < b.draw_id; });

    int n = draws.size();
    fprintf(stderr, "Loaded %d ky. Quet seed %lld -> %lld, MIN_LOG=%lld\n", n, (long long)start, (long long)end, (long long)min_log);

    if (start > end) {
        FILE* f = fopen(out_path.c_str(), "w");
        fprintf(f, "{\"status\":\"empty\",\"scan_start\":%lld,\"scan_end\":%lld,\"scanned\":0,\"completed\":true}", (long long)start, (long long)end);
        fclose(f);
        return 0;
    }

    std::vector<u64> draw_ids(n);
    std::vector<i64> masks(n);
    std::vector<int> specials(n);
    for (int i = 0; i < n; i++) { draw_ids[i] = draws[i].draw_id; masks[i] = draws[i].mask; specials[i] = draws[i].special; }

    auto t0 = std::chrono::steady_clock::now();

    struct Hit { u64 seed; int j1; };
    std::vector<Hit> found_j1;
    struct TopEntry { u64 seed; int count; };
    std::vector<TopEntry> top_main5, top_main4, top_special;

    i64 checked = 0;
    auto last_log = t0;

    for (u64 seed = (u64)start; seed <= (u64)end; seed++) {
        int c_j1 = 0, c_m5 = 0, c_m4 = 0, c_sp = 0;
        for (int j = 0; j < n; j++) {
            u64 combined = seed * M1 + draw_ids[j] * M2;
            u64 mixed = mix64(combined);
            i64 rank = (i64)(mixed % (u64)C);
            i64 mask = RANK_TO_MASK[rank];  // LUT thay vi tinh dong

            u64 mixed2 = mix64(mixed);
            int sp = (int)(mixed2 % 12) + 1;

            i64 overlap = mask & masks[j];
            int n_match = popcount64(overlap);
            bool sp_match = (sp == specials[j]);

            if (n_match == 5) { c_m5++; if (sp_match) c_j1++; }
            else if (n_match == 4) c_m4++;
            if (sp_match) c_sp++;
        }

        if (c_j1 >= min_log) {
            found_j1.push_back({seed, c_j1});
            fprintf(stderr, "HIT J1 seed=%llu J1=%dx\n", (unsigned long long)seed, c_j1);
        }
        if (c_m5 > 0) top_main5.push_back({seed, c_m5});
        if (c_m4 > 0) top_main4.push_back({seed, c_m4});
        if (c_sp > 0) top_special.push_back({seed, c_sp});

        checked++;
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_log).count() >= 15.0) {
            double elapsed_total = std::chrono::duration<double>(now - t0).count();
            fprintf(stderr, "  scanned=%lld/%lld (%.0f/s)\n", (long long)checked, (long long)(end-start+1), checked/elapsed_total);
            last_log = now;
        }
    }

    std::sort(top_main5.begin(), top_main5.end(), [](auto&a, auto&b){return a.count>b.count;});
    std::sort(top_main4.begin(), top_main4.end(), [](auto&a, auto&b){return a.count>b.count;});
    std::sort(top_special.begin(), top_special.end(), [](auto&a, auto&b){return a.count>b.count;});
    if ((int)top_main5.size() > 500) top_main5.resize(500);
    if ((int)top_main4.size() > 500) top_main4.resize(500);
    if ((int)top_special.size() > 500) top_special.resize(500);

    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();
    fprintf(stderr, "\nXong: %lld seed / %.0fs (%.0f/s). J1_found=%zu\n", (long long)checked, elapsed, checked/elapsed, found_j1.size());

    FILE* f = fopen(out_path.c_str(), "w");
    fprintf(f, "{\"status\":\"completed\",\"scan_start\":%lld,\"scan_end\":%lld,\"scanned\":%lld,\"completed\":true,\"found_j1\":%zu,\"rate\":%.0f}",
            (long long)start, (long long)end, (long long)checked, found_j1.size(), checked/elapsed);
    fclose(f);
    return 0;
}
