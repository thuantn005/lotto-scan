// scan_j1.cpp — Ban C++ toi uu, tuong thich day du voi workflow 6-file
// (j1_2plus, j1_3plus, j1_4plus, top_main5, top_main4, top_special)
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
static std::vector<i64> RANK_TO_MASK;

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
        mask |= (1LL << x); rem -= BINOM[x][k];
    }
    return mask;
}
void build_lut() { RANK_TO_MASK.resize(C); for (i64 r=0;r<C;r++) RANK_TO_MASK[r]=rank_mask_calc(r); }

inline u64 mix64(u64 x) {
    x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31;
    return x;
}
inline int popcount64(i64 x) { return __builtin_popcountll((u64)x); }

struct Draw { u64 draw_id; i64 mask; int special; std::string date; std::vector<int> numbers; };

std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) { if (c=='"'||c=='\\') out+='\\'; out+=c; }
    return out;
}

int main() {
    build_binom(); build_lut();

    auto getenv_str = [](const char* name, const char* def) -> std::string {
        const char* v = std::getenv(name); return v ? std::string(v) : std::string(def);
    };
    auto getenv_i64 = [&](const char* name, i64 def) -> i64 {
        std::string s = getenv_str(name, ""); return s.empty() ? def : std::stoll(s);
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
            std::string cur; bool in_quotes = false;
            for (size_t i = 0; i < line.size(); i++) {
                char c = line[i];
                if (c == '"') { if (in_quotes && i+1<line.size() && line[i+1]=='"') { cur+='"'; i++; } else in_quotes=!in_quotes; }
                else if (c == ',' && !in_quotes) { fields.push_back(cur); cur.clear(); }
                else cur += c;
            }
            fields.push_back(cur);
            if (fields.size() < 5) continue;
            i64 draw_id;
            try { draw_id = std::stoll(fields[1]); } catch (...) { continue; }
            std::string draw_date = fields.size() > 2 ? fields[2] : "";
            std::string rj = fields[4];
            auto extract_nums = [](const std::string& s, const std::string& key) -> std::vector<int> {
                std::vector<int> out;
                size_t p = s.find(key); if (p==std::string::npos) return out;
                p = s.find('[', p); size_t q = s.find(']', p);
                if (p==std::string::npos || q==std::string::npos) return out;
                std::string inner = s.substr(p+1, q-p-1);
                std::stringstream ss(inner); std::string tok;
                while (std::getline(ss, tok, ',')) { try { out.push_back(std::stoi(tok)); } catch (...) {} }
                return out;
            };
            std::vector<int> nums = extract_nums(rj, "\"numbers\"");
            std::vector<int> spv  = extract_nums(rj, "\"special_numbers\"");
            if (nums.size() != 5 || spv.empty()) continue;
            i64 mask = 0; for (int nm : nums) mask |= (1LL << (nm - 1));
            std::sort(nums.begin(), nums.end());
            draws.push_back({(u64)draw_id, mask, spv[0], draw_date, nums});
        }
    }
    std::sort(draws.begin(), draws.end(), [](const Draw& a, const Draw& b) { return a.draw_id < b.draw_id; });

    int n = draws.size();
    fprintf(stderr, "Loaded %d ky. Quet seed %lld -> %lld, MIN_LOG=%lld\n", n, (long long)start, (long long)end, (long long)min_log);

    // Tach thu muc va stem cho 7 file output
    size_t slash = out_path.find_last_of('/');
    std::string out_dir = (slash==std::string::npos) ? "." : out_path.substr(0, slash);
    std::string out_file = (slash==std::string::npos) ? out_path : out_path.substr(slash+1);
    size_t dot = out_file.find_last_of('.');
    std::string out_stem = (dot==std::string::npos) ? out_file : out_file.substr(0, dot);

    auto write_empty_all = [&](const std::string& status) {
        auto wf = [&](const std::string& path, const std::string& extra) {
            FILE* f = fopen(path.c_str(), "w");
            fprintf(f, "{\"status\":\"%s\",\"scan_start\":%lld,\"scan_end\":%lld,\"scanned\":0,\"completed\":true%s}",
                    status.c_str(), (long long)start, (long long)end, extra.c_str());
            fclose(f);
        };
        wf(out_dir+"/"+out_stem+".json", ",\"min_log\":"+std::to_string(min_log)+",\"found_j1_2plus\":0,\"found_j1_3plus\":0,\"found_j1_4plus\":0");
        wf(out_dir+"/"+out_stem+"_j1_2plus.json", ",\"found\":0,\"results\":[]");
        wf(out_dir+"/"+out_stem+"_j1_3plus.json", ",\"found\":0,\"results\":[]");
        wf(out_dir+"/"+out_stem+"_j1_4plus.json", ",\"found\":0,\"results\":[]");
        wf(out_dir+"/"+out_stem+"_top_main5.json", ",\"results\":[]");
        wf(out_dir+"/"+out_stem+"_top_main4.json", ",\"results\":[]");
        wf(out_dir+"/"+out_stem+"_top_special.json", ",\"results\":[]");
    };

    if (start > end) { write_empty_all("empty"); return 0; }

    std::vector<u64> draw_ids(n);
    std::vector<i64> masks(n);
    std::vector<int> specials(n);
    for (int i = 0; i < n; i++) { draw_ids[i]=draws[i].draw_id; masks[i]=draws[i].mask; specials[i]=draws[i].special; }

    auto t0 = std::chrono::steady_clock::now();

    struct Hit { u64 seed; int j1; std::vector<int> hit_draw_idx; };
    std::vector<Hit> found_j1;
    struct TopEntry { u64 seed; int count; };
    std::vector<TopEntry> top_main5, top_main4, top_special;

    i64 checked = 0;
    auto last_log = t0, last_checkpoint = t0;

    auto save_checkpoint = [&](bool done) {
        i64 scanned = checked;
        auto wf_j1 = [&](const std::string& suffix, int min_level) {
            std::string path = out_dir+"/"+out_stem+suffix+".json";
            FILE* f = fopen(path.c_str(), "w");
            fprintf(f, "{\"status\":\"%s\",\"scan_start\":%lld,\"scan_end\":%lld,\"scanned\":%lld,\"completed\":%s,\"found\":",
                    done?"completed":"partial", (long long)start, (long long)end, (long long)scanned, done?"true":"false");
            std::vector<Hit*> filtered;
            for (auto& h : found_j1) if (h.j1 >= min_level) filtered.push_back(&h);
            fprintf(f, "%zu,\"results\":[", filtered.size());
            for (size_t i = 0; i < filtered.size() && i < 200; i++) {
                Hit* h = filtered[i];
                if (i) fprintf(f, ",");
                fprintf(f, "{\"seed\":%llu,\"j1_count\":%d,\"jackpot1_hits\":[", (unsigned long long)h->seed, h->j1);
                for (size_t k = 0; k < h->hit_draw_idx.size(); k++) {
                    int di = h->hit_draw_idx[k];
                    if (k) fprintf(f, ",");
                    fprintf(f, "{\"draw_id\":%llu,\"draw_date\":\"%s\",\"numbers\":[",
                            (unsigned long long)draws[di].draw_id, json_escape(draws[di].date).c_str());
                    for (size_t m = 0; m < draws[di].numbers.size(); m++) { if (m) fprintf(f,","); fprintf(f, "%d", draws[di].numbers[m]); }
                    fprintf(f, "],\"special\":%d}", draws[di].special);
                }
                fprintf(f, "]}");
            }
            fprintf(f, "]}");
            fclose(f);
        };
        wf_j1("_j1_2plus", 2);
        wf_j1("_j1_3plus", 3);
        wf_j1("_j1_4plus", 4);

        auto wf_top = [&](const std::string& suffix, std::vector<TopEntry>& v) {
            std::string path = out_dir+"/"+out_stem+suffix+".json";
            FILE* f = fopen(path.c_str(), "w");
            fprintf(f, "{\"status\":\"%s\",\"scan_start\":%lld,\"scan_end\":%lld,\"scanned\":%lld,\"completed\":%s,\"results\":[",
                    done?"completed":"partial", (long long)start, (long long)end, (long long)scanned, done?"true":"false");
            std::sort(v.begin(), v.end(), [](auto&a, auto&b){return a.count>b.count;});
            if (v.size() > 500) v.resize(500);
            for (size_t i = 0; i < v.size(); i++) { if (i) fprintf(f, ","); fprintf(f, "{\"seed\":%llu,\"count\":%d}", (unsigned long long)v[i].seed, v[i].count); }
            fprintf(f, "]}");
            fclose(f);
        };
        wf_top("_top_main5", top_main5);
        wf_top("_top_main4", top_main4);
        wf_top("_top_special", top_special);

        std::string path = out_dir+"/"+out_stem+".json";
        FILE* f = fopen(path.c_str(), "w");
        fprintf(f, "{\"status\":\"%s\",\"scan_start\":%lld,\"scan_end\":%lld,\"scanned\":%lld,\"completed\":%s,\"min_log\":%lld,\"found_j1_2plus\":%zu,\"found_j1_3plus\":%zu,\"found_j1_4plus\":%zu}",
                done?"completed":"partial", (long long)start, (long long)end, (long long)scanned, done?"true":"false", (long long)min_log,
                found_j1.size(),
                (size_t)std::count_if(found_j1.begin(),found_j1.end(),[](Hit&h){return h.j1>=3;}),
                (size_t)std::count_if(found_j1.begin(),found_j1.end(),[](Hit&h){return h.j1>=4;}));
        fclose(f);
    };

    for (u64 seed = (u64)start; seed <= (u64)end; seed++) {
        int c_j1 = 0, c_m5 = 0, c_m4 = 0, c_sp = 0;
        std::vector<int> hit_idx;
        for (int j = 0; j < n; j++) {
            u64 combined = seed * M1 + draw_ids[j] * M2;
            u64 mixed = mix64(combined);
            i64 rank = (i64)(mixed % (u64)C);
            i64 mask = RANK_TO_MASK[rank];
            u64 mixed2 = mix64(mixed);
            int sp = (int)(mixed2 % 12) + 1;
            i64 overlap = mask & masks[j];
            int nm = popcount64(overlap);
            bool spm = (sp == specials[j]);
            if (nm == 5) { c_m5++; if (spm) { c_j1++; hit_idx.push_back(j); } }
            else if (nm == 4) c_m4++;
            if (spm) c_sp++;
        }

        if (c_j1 >= min_log) found_j1.push_back({seed, c_j1, hit_idx});
        if (c_m5 > 0) top_main5.push_back({seed, c_m5});
        if (c_m4 > 0) top_main4.push_back({seed, c_m4});
        if (c_sp > 0) top_special.push_back({seed, c_sp});

        checked++;
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration<double>(now - last_checkpoint).count() >= 30.0) {
            save_checkpoint(false);
            last_checkpoint = now;
        }
        if (std::chrono::duration<double>(now - last_log).count() >= 15.0) {
            double elapsed_total = std::chrono::duration<double>(now - t0).count();
            fprintf(stderr, "  scanned=%lld/%lld (%.0f/s) f2=%zu f3=%zu f4=%zu\n",
                    (long long)checked, (long long)(end-start+1), checked/elapsed_total,
                    found_j1.size(),
                    (size_t)std::count_if(found_j1.begin(),found_j1.end(),[](Hit&h){return h.j1>=3;}),
                    (size_t)std::count_if(found_j1.begin(),found_j1.end(),[](Hit&h){return h.j1>=4;}));
            last_log = now;
        }
    }

    save_checkpoint(true);

    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();
    fprintf(stderr, "\nXong: %lld seed / %.0fs (%.0f/s). J1found=%zu\n", (long long)checked, elapsed, checked/elapsed, found_j1.size());

    return 0;
}
