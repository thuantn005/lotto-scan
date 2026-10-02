// scan_mega.cpp - quet seed cho Mega 6/45.
// Cong thuc (giong tinh than project lotto-scan, doi sang C(45,6)):
//   combined = seed*M1 + draw_id*M2 (mod 2^64); mixed = mix64(combined)
//   rank = mixed mod C(45,6)  -> 6 so (colex unrank)
// Seed "trung" ky d neu rank sinh ra == rank cua ket qua that.
// Input : work/draws.txt  (moi dong: draw_id rank)
// Output: cac dong "draw_id seed" ghi ra file --out
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <algorithm>
#include <omp.h>
using u64 = uint64_t;
constexpr u64 M1 = 0x9E3779B97F4A7C15ULL, M2 = 0xD1B54A32D192ED03ULL;
constexpr u64 M3 = 0xBF58476D1CE4E5B9ULL, M4 = 0x94D049BB133111EBULL;
constexpr u64 C = 8145060ULL; // C(45,6)
static inline u64 mix64(u64 x){ x^=x>>30; x*=M3; x^=x>>27; x*=M4; x^=x>>31; return x; }
int main(int argc, char** argv){
    const char* draws_path="work/draws.txt"; const char* out="results/hits.txt";
    u64 start=10000000000ULL, count=100000000ULL;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--draws")&&i+1<argc) draws_path=argv[++i];
        else if(!strcmp(argv[i],"--out")&&i+1<argc) out=argv[++i];
        else if(!strcmp(argv[i],"--seed-start")&&i+1<argc) start=strtoull(argv[++i],0,10);
        else if(!strcmp(argv[i],"--count")&&i+1<argc) count=strtoull(argv[++i],0,10);
    }
    std::vector<u64> ids, ranks, idm;
    FILE* f=fopen(draws_path,"r"); if(!f){fprintf(stderr,"khong mo duoc %s\n",draws_path);return 1;}
    unsigned long long a,b; while(fscanf(f,"%llu %llu",&a,&b)==2){ids.push_back(a);ranks.push_back(b);idm.push_back(a*M2);} fclose(f);
    const int D=ids.size(); if(!D){fprintf(stderr,"khong co ky nao\n");return 1;}
    int T=omp_get_max_threads(); std::vector<std::vector<std::pair<u64,u64>>> loc(T);
    #pragma omp parallel
    {
        auto& L=loc[omp_get_thread_num()];
        #pragma omp for schedule(static)
        for(long long k=0;k<(long long)count;k++){
            u64 seed=start+(u64)k, base=seed*M1;
            for(int j=0;j<D;j++){
                u64 m=mix64(base+idm[j]);
                if(m%C==ranks[j]) L.push_back({ids[j],seed});
            }
        }
    }
    std::vector<std::pair<u64,u64>> all; for(auto&l:loc) all.insert(all.end(),l.begin(),l.end());
    std::sort(all.begin(),all.end());
    FILE* o=fopen(out,"w"); if(!o){fprintf(stderr,"khong ghi duoc %s\n",out);return 1;}
    for(auto&p:all) fprintf(o,"%llu %llu\n",(unsigned long long)p.first,(unsigned long long)p.second);
    fclose(o);
    fprintf(stderr,"quet %llu seed x %d ky -> %zu hit\n",(unsigned long long)count,D,all.size());
    return 0;
}
