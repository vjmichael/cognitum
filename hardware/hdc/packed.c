/* Research-only host kernel; packed words, LSB first, explicit tail mask. */
#include <stdint.h>
#include <stddef.h>
#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif
/* Baseline is portable SWAR; specialized instructions occur only in targeted
 * functions after runtime CPUID/OS vector-state checks. */
static unsigned pc(uint64_t x) {
 x -= (x>>1)&UINT64_C(0x5555555555555555); x=(x&UINT64_C(0x3333333333333333))+((x>>2)&UINT64_C(0x3333333333333333)); x=(x+(x>>4))&UINT64_C(0x0f0f0f0f0f0f0f0f); return (unsigned)((x*UINT64_C(0x0101010101010101))>>56);
}
#if (defined(__x86_64__) || defined(__i386__)) && (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#define X86_DISPATCH 1
__attribute__((target("popcnt"))) static unsigned h_pop(const uint64_t *q,const uint64_t *p,size_t n,uint64_t mask){
 unsigned h=0;size_t k=0;for(;k+1<n;k++){h+=(unsigned)__builtin_popcountll(q[k]^p[k]);}return h+(unsigned)__builtin_popcountll((q[k]^p[k])&mask);
}
__attribute__((target("avx512f,avx512vpopcntdq,popcnt"))) static unsigned h_vec(const uint64_t *q,const uint64_t *p,size_t n,uint64_t mask){
 __m512i acc=_mm512_setzero_si512();size_t k=0;
 for(;k+8<n;k+=8){__m512i a=_mm512_loadu_si512((const void*)(q+k)),b=_mm512_loadu_si512((const void*)(p+k));acc=_mm512_add_epi64(acc,_mm512_popcnt_epi64(_mm512_xor_si512(a,b)));}
 uint64_t totals[8];_mm512_storeu_si512((void*)totals,acc);unsigned h=0;for(unsigned j=0;j<8;j++)h+=(unsigned)totals[j];
 for(;k+1<n;k++){h+=(unsigned)__builtin_popcountll(q[k]^p[k]);}return h+(unsigned)__builtin_popcountll((q[k]^p[k])&mask);
}
#else
#define X86_DISPATCH 0
#endif
/* mode: 0 reproducible fallback, 1 POPCNT, 2 vector popcount, 3 auto. */
API unsigned hdc_capabilities(void){
 unsigned r=1;
#if X86_DISPATCH
 __builtin_cpu_init();if(__builtin_cpu_supports("popcnt"))r|=2;
 if((r&2)&&__builtin_cpu_supports("avx512f")&&__builtin_cpu_supports("avx512vpopcntdq"))r|=4;
#endif
 return r;
}
API int hdc_dispatch(unsigned d,unsigned mode){
 if(!d||d>65536||mode>3)return -1;
 unsigned caps=hdc_capabilities();if(mode==3)return (caps&4)&&d>=2048?2:(caps&2)?1:0;
 return (caps&(1u<<mode))?(int)mode:-2;
}
static unsigned h_swar(const uint64_t *q,const uint64_t *p,size_t n,uint64_t mask){unsigned h=0;size_t k=0;for(;k+1<n;k++)h+=pc(q[k]^p[k]);return h+pc((q[k]^p[k])&mask);}
API int hdc_scores_mode(const uint64_t *q,const uint64_t *p,int32_t *out,size_t nq,size_t np,unsigned d,unsigned mode){
 if(!q||!p||!out||!nq||!np||!d||d>65536)return -1;
 size_t n=(d+63)/64;if(nq>SIZE_MAX/n||np>SIZE_MAX/n||nq>SIZE_MAX/np)return -1;
 int selected=hdc_dispatch(d,mode);if(selected<0)return selected;
 unsigned (*fn)(const uint64_t*,const uint64_t*,size_t,uint64_t)=h_swar;
#if X86_DISPATCH
 if(selected==1)fn=h_pop;else if(selected==2)fn=h_vec;
#endif
 uint64_t mask=d%64? (UINT64_C(1)<<(d%64))-1:UINT64_MAX;
 for(size_t i=0;i<nq;i++)for(size_t j=0;j<np;j++)out[i*np+j]=(int32_t)d-2*(int32_t)fn(q+i*n,p+j*n,n,mask);
 return 0;
}
API int hdc_scores(const uint64_t *q,const uint64_t *p,int32_t *out,size_t nq,size_t np,unsigned d){return hdc_scores_mode(q,p,out,nq,np,d,3);}
API int hdc_i8dot(const int8_t *a,const int8_t *b,size_t n,int32_t *out){
 if(!a||!b||!out||!n||n>65536)return -1;
 int32_t s=0;for(size_t i=0;i<n;i++)s+=(int32_t)a[i]*(int32_t)b[i];*out=s;return 0;
}
API int hdc_requantize(int32_t acc,int32_t mult,unsigned shift,int8_t *out){
 if(!out||mult<0||shift>62)return -1;
 int64_t x=(int64_t)acc*mult;
 uint64_t a=x<0?(uint64_t)(-x):(uint64_t)x;
 if(shift)a=(a+(UINT64_C(1)<<(shift-1)))>>shift;
 int64_t y=x<0?-(int64_t)a:(int64_t)a;
 *out=(int8_t)(y< -128?-128:y>127?127:y);return 0;
}
API int hdc_bind(const uint64_t *a,const uint64_t *b,uint64_t *out,unsigned d){
 if(!a||!b||!out||!d||d>65536)return -1;
 size_t n=(d+63)/64;for(size_t k=0;k<n;k++)out[k]=a[k]^b[k];if(d%64)out[n-1]&=(UINT64_C(1)<<(d%64))-1;return 0;
}
API int hdc_majority(const uint64_t *a,uint64_t *out,size_t n,unsigned d){
 if(!a||!out||!n||n>65536||!d||d>65536)return -1;
 size_t words=(d+63)/64;for(size_t k=0;k<words;k++){
  unsigned counts[64]={0}; unsigned lim=(k+1==words&&d%64)?d%64:64;uint64_t r=0;
  for(size_t i=0;i<n;i++){uint64_t v=a[i*words+k];for(unsigned j=0;j<lim;j++)counts[j]+=(unsigned)((v>>j)&1);}
  for(unsigned j=0;j<lim;j++){if(counts[j]*2>=n)r|=UINT64_C(1)<<j;}out[k]=r;
 }return 0;
}
