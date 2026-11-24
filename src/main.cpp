#include <algorithm>
#include <array>
#include <map>
#include <utility>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
using U = uint32_t;
using W = uint64_t;
constexpr W BASE = 10000;
struct Counts {
    W mul=0, accum=0, carry=0, add=0, sub=0, smallmul=0, smalldiv=0,
      calls=0, school=0, kara=0, toom=0, depth=0;
} cnt;
#ifdef PROFILE
#define COUNT(k,n) (cnt.k += (n))
#else
#define COUNT(k,n) ((void)0)
#endif
struct Big {
    std::vector<U> d;
    int sign=0;
    Big()=default;
    explicit Big(std::vector<U> v,int s=1):d(std::move(v)),sign(s){norm();}
    void norm(){while(!d.empty() && !d.back()) d.pop_back(); if(d.empty()) sign=0;}
    size_t size() const{return d.size();}
    U at(size_t i) const{return i<size()?d[i]:0;}
    static Big parse(const std::string& s){
        if(s.empty() || s.find_first_not_of("0123456789")!=std::string::npos) throw std::invalid_argument("비음수 십진수 필요");
        std::vector<U> v; for(size_t e=s.size();e;){size_t b=e>4?e-4:0; v.push_back(static_cast<U>(std::stoul(s.substr(b,e-b))));e=b;} return Big(std::move(v));
    }
    std::string str() const {if(!sign)return "0"; std::string s=(sign<0?"-":"")+std::to_string(d.back()); for(size_t i=size()-1;i>0;--i){auto t=std::to_string(d[i-1]);s+=std::string(4-t.size(),'0')+t;} return s;}
    Big part(size_t off,size_t len)const{if(off>=size())return {};size_t end=off+std::min(len,size()-off);return Big(std::vector<U>(d.begin()+off,d.begin()+end),sign);}
    Big shift(size_t n)const{if(!sign)return {};std::vector<U> v(n,0);v.insert(v.end(),d.begin(),d.end());return Big(std::move(v),sign);}
};
int cmp(const Big&a,const Big&b){if(a.size()!=b.size())return a.size()<b.size()?-1:1;for(size_t i=a.size();i>0;--i)if(a.d[i-1]!=b.d[i-1])return a.d[i-1]<b.d[i-1]?-1:1;return 0;}
Big absadd(const Big&a,const Big&b,int s){size_t n=std::max(a.size(),b.size());std::vector<U> v(n+1);W c=0;for(size_t i=0;i<n;++i){W t=W(a.at(i))+b.at(i)+c;v[i]=U(t%BASE);c=t/BASE;COUNT(add,1);}v[n]=U(c);return Big(std::move(v),s);}
Big abssub(const Big&a,const Big&b,int s){std::vector<U> v(a.size());int64_t c=0;for(size_t i=0;i<a.size();++i){int64_t t=int64_t(a.d[i])-b.at(i)-c;c=t<0;v[i]=U(t+(c?BASE:0));COUNT(sub,1);}if(c)throw std::logic_error("negative magnitude");return Big(std::move(v),s);}
Big operator+(const Big&a,const Big&b){if(!a.sign)return b;if(!b.sign)return a;if(a.sign==b.sign)return absadd(a,b,a.sign);int k=cmp(a,b);if(!k)return {};return k>0?abssub(a,b,a.sign):abssub(b,a,b.sign);}
Big operator-(const Big&a,Big b){b.sign=-b.sign;return a+b;}
Big scale(const Big&a,U k){if(!a.sign||!k)return {};std::vector<U> v(a.size());W c=0;for(size_t i=0;i<a.size();++i){W t=W(a.d[i])*k+c;v[i]=U(t%BASE);c=t/BASE;COUNT(smallmul,1);}while(c){v.push_back(U(c%BASE));c/=BASE;}return Big(std::move(v),a.sign);}
Big exactdiv(const Big&a,U k){if(!k)throw std::logic_error("division by zero");if(!a.sign)return {};std::vector<U> v(a.size());W r=0;for(size_t i=a.size();i>0;--i){W t=r*BASE+a.d[i-1];v[i-1]=U(t/k);r=t%k;COUNT(smalldiv,1);}if(r)throw std::logic_error("non-exact interpolation division");return Big(std::move(v),a.sign);}
enum class Algo{S,K,T,H};
struct Config{Algo algo=Algo::S;bool deferred=false;size_t kt=32,tt=128;bool one_level=false;bool fast_split=false, fast_join=false, fast_interp=false;};
Big school(const Big&a,const Big&b,bool deferred){
    if(!a.sign||!b.sign)return {};size_t n=a.size(),m=b.size();std::vector<U> out(n+m);int s=a.sign*b.sign;
    if(!deferred){
        for(size_t i=0;i<n;++i){W c=0;for(size_t j=0;j<m;++j){W t=W(a.d[i])*b.d[j]+out[i+j]+c;out[i+j]=U(t%BASE);c=t/BASE;COUNT(mul,1);COUNT(accum,1);COUNT(carry,1);}out[i+m]=U(c);}
    }else{
        // 각 계수의 곱 누산 + 앞 계수의 carry까지 안전한 보수적 상한.
        if(std::min(n,m)>std::numeric_limits<W>::max()/(BASE*(BASE-1)))throw std::overflow_error("deferred accumulator bound");
        std::vector<W> acc(n+m,0);for(size_t i=0;i<n;++i)for(size_t j=0;j<m;++j){acc[i+j]+=W(a.d[i])*b.d[j];COUNT(mul,1);COUNT(accum,1);}
        W c=0;for(size_t i=0;i<n+m;++i){W t=acc[i]+c;out[i]=U(t%BASE);c=t/BASE;COUNT(carry,1);}if(c)throw std::logic_error("carry overflow");
    }return Big(std::move(out),s);
}
// 전체 입력 복사를 생략하고 필요한 부분만 양수로 추출한다.
Big positive_part(const Big& a,size_t off,size_t len){Big r=a.part(off,len);if(r.sign)r.sign=1;return r;}
// 양수 계수를 한 결과 배열에 직접 누산한다. t <= 2*(BASE-1)+1.
Big join_positive(const Big& c0,const Big& c1,const Big& c2,size_t h){
    const std::array<const Big*,3> cs{&c0,&c1,&c2};
    size_t n=0;for(size_t j=0;j<3;++j)n=std::max(n,j*h+cs[j]->size());
    std::vector<U> out(n+1,0);
    for(size_t j=0;j<3;++j){const Big& c=*cs[j];if(c.sign<0)throw std::logic_error("negative coefficient in join");
        W carry=0;size_t i=0,off=j*h;
        for(;i<c.size();++i){W t=W(out[off+i])+c.d[i]+carry;out[off+i]=U(t%BASE);carry=t/BASE;}
        while(carry){if(off+i>=out.size())throw std::logic_error("join overflow");W t=W(out[off+i])+carry;out[off+i]=U(t%BASE);carry=t/BASE;++i;}
    }return Big(std::move(out));
}
// 시간 계측은 별도 실행 파일에서만 활성화한다. 각 구간은 재귀 호출을 포함하지 않는다.
enum Phase { BASECASE, SPLIT, EVALUATE, INTERPOLATE, RECOMBINE, PHASES };
#ifdef PHASE_PROFILE
struct PhaseCell { W visits=0; double ns=0; };
std::array<std::array<std::array<PhaseCell,PHASES>,3>,128> phase_data{};
#endif
#ifdef PROFILE
bool collect_leaves=false;
std::map<std::pair<size_t,size_t>,W> leaf_sizes;
#endif
template<class F> auto phase(Phase p, Algo mode, size_t depth, F&& fn){
#ifdef PHASE_PROFILE
    const auto start=std::chrono::steady_clock::now();
    auto result=fn();
    const auto stop=std::chrono::steady_clock::now();
    auto& cell=phase_data.at(depth-1).at(static_cast<size_t>(mode)).at(p);
    ++cell.visits; cell.ns+=std::chrono::duration<double,std::nano>(stop-start).count();
    return result;
#else
    (void)p; (void)mode; (void)depth;
    return fn();
#endif
}
Big multiply(const Big&a,const Big&b,const Config& cfg,size_t depth=1){
    COUNT(calls,1);
#ifdef PROFILE
    cnt.depth=std::max(cnt.depth,W(depth));
#endif
    if(!a.sign||!b.sign)return {};
    size_t n=std::max(a.size(),b.size());Algo mode=cfg.algo;
    if(mode==Algo::K && n<=cfg.kt)mode=Algo::S;
    if(mode==Algo::T && n<=cfg.tt)mode=Algo::S;
    if(mode==Algo::H)mode=n<=cfg.kt?Algo::S:n<=cfg.tt?Algo::K:Algo::T;
    if(cfg.one_level && depth>1)mode=Algo::S;
    if(mode==Algo::S){COUNT(school,1);
#ifdef PROFILE
        if(collect_leaves)++leaf_sizes[{a.size(),b.size()}];
#endif
        return phase(BASECASE,mode,depth,[&]{return school(a,b,cfg.deferred);});
    }
    // 분할 및 부호 제거: 원본의 복사 비용도 분할 구간에 포함한다.
    int s=a.sign*b.sign;
    auto rec=[&](const Big&u,const Big&v){return multiply(u,v,cfg,depth+1);};
    Big result;
    if(mode==Algo::K){COUNT(kara,1);size_t h=(n+1)/2;
        auto parts=phase(SPLIT,mode,depth,[&]{if(cfg.fast_split)return std::array<Big,4>{positive_part(a,0,h),positive_part(a,h,h),positive_part(b,0,h),positive_part(b,h,h)};Big x=a,y=b;x.sign=y.sign=1;return std::array<Big,4>{x.part(0,h),x.part(h,h),y.part(0,h),y.part(h,h)};});
        const auto& [a0,a1,b0,b1]=parts;
        Big z0=rec(a0,b0),z2=rec(a1,b1);
        auto eval=phase(EVALUATE,mode,depth,[&]{return std::array<Big,2>{a0+a1,b0+b1};});
        Big v=rec(eval[0],eval[1]);
        Big z1=phase(INTERPOLATE,mode,depth,[&]{return v-z0-z2;});
        result=phase(RECOMBINE,mode,depth,[&]{if(cfg.fast_join)return join_positive(z0,z1,z2,h);return z0+z1.shift(h)+z2.shift(2*h);});
    }else{COUNT(toom,1);size_t h=(n+2)/3;
        auto parts=phase(SPLIT,mode,depth,[&]{Big x=a,y=b;x.sign=y.sign=1;return std::array<Big,6>{x.part(0,h),x.part(h,h),x.part(2*h,h),y.part(0,h),y.part(h,h),y.part(2*h,h)};});
        const auto& [a0,a1,a2,b0,b1,b2]=parts;
        Big c0=rec(a0,b0),c4=rec(a2,b2);
        auto e1=phase(EVALUATE,mode,depth,[&]{return std::array<Big,2>{a0+a1+a2,b0+b1+b2};});
        Big v1=rec(e1[0],e1[1]);
        auto em=phase(EVALUATE,mode,depth,[&]{return std::array<Big,2>{a0-a1+a2,b0-b1+b2};});
        Big vm1=rec(em[0],em[1]);
        auto e2=phase(EVALUATE,mode,depth,[&]{return std::array<Big,2>{a0+scale(a1,2)+scale(a2,4),b0+scale(b1,2)+scale(b2,4)};});
        Big v2=rec(e2[0],e2[1]);
        auto coeff=phase(INTERPOLATE,mode,depth,[&]{
            Big c2,odd;
            if(cfg.fast_interp){
                // v1=c0+c2+c4+odd. 이미 필요한 odd를 재사용해 /2 한 번을 제거한다.
                odd=exactdiv(v1-vm1,2);c2=v1-odd-c0-c4;
            }else{c2=exactdiv(v1+vm1,2)-c0-c4;odd=exactdiv(v1-vm1,2);}
            Big c3=exactdiv(v2-c0-scale(c2,4)-scale(c4,16)-scale(odd,2),6);
            Big c1=odd-c3;
            if(c1.sign<0||c2.sign<0||c3.sign<0)throw std::logic_error("negative coefficient");
            return std::array<Big,3>{std::move(c1),std::move(c2),std::move(c3)};
        });
        const auto& [c1,c2,c3]=coeff;
        result=phase(RECOMBINE,mode,depth,[&]{return c0+c1.shift(h)+c2.shift(2*h)+c3.shift(3*h)+c4.shift(4*h);});
    }
    if(result.sign)result.sign=s;return result;
}
Config config(const std::string& a,const std::string& base,size_t kt,size_t tt){Config c;
    if(a=="school")c.algo=Algo::S;else if(a=="kara")c.algo=Algo::K;else if(a=="toom")c.algo=Algo::T;else if(a=="hybrid")c.algo=Algo::H;
    else if(a=="kara_split"||a=="kara_join"||a=="kara_opt"){
        c.algo=Algo::K;c.fast_split=a!="kara_join";c.fast_join=a!="kara_split";
    }else if(a=="toom_interp"){c.algo=Algo::T;c.fast_interp=true;}
    else if(a=="hybrid_kopt"){c.algo=Algo::H;c.fast_split=c.fast_join=true;}
    else throw std::invalid_argument("algorithm");
    if(base!="immediate"&&base!="deferred")throw std::invalid_argument("basecase");c.deferred=base=="deferred";c.kt=kt;c.tt=tt;if(kt<8||tt<8||(c.algo==Algo::H&&kt>tt))throw std::invalid_argument("threshold >= 8, hybrid kt <= tt");return c;}
Big random_big(size_t n,std::mt19937_64&r){std::vector<U> v(n);for(auto&x:v)x=U(r()%BASE);v.back()=1+U(r()%(BASE-1));return Big(std::move(v));}
volatile W sink=0;
int main(int argc,char**argv){try{
    if(argc<6)throw std::invalid_argument("usage: bigint batch|bench ALGO BASECASE KT TT [N SEED REPS]");
    std::string action=argv[1];Config cfg=config(argv[2],argv[3],std::stoull(argv[4]),std::stoull(argv[5]));
    if(action=="batch" || action=="batchone"){cfg.one_level=(action=="batchone");std::string a,b;while(std::cin>>a>>b)std::cout<<multiply(Big::parse(a),Big::parse(b),cfg).str()<<'\n';}
    // 동일한 입력으로 여러 설정을 비교하고 작은 연산은 묶어서 측정한다.
    else if((action=="grid" && argc==10)||(action=="rectgrid"&&argc==11)){
#if !defined(PROFILE) && !defined(PHASE_PROFILE)
        size_t n=std::stoull(argv[6]);int off=action=="rectgrid"?1:0;size_t m=off?std::stoull(argv[7]):n;
        W seed=std::stoull(argv[7+off]);size_t reps=std::stoull(argv[8+off]);double target=std::stod(argv[9+off]);
        if(!n||!m||!reps||target<=0)throw std::invalid_argument("invalid grid parameters");
        std::mt19937_64 r(seed);Big a=random_big(n,r),b=random_big(m,r);
        std::string algo,base;size_t kt,tt;int one;
        while(std::cin>>algo>>base>>kt>>tt>>one){
            Config c=config(algo,base,kt,tt);c.one_level=(one!=0);
            auto warm=multiply(a,b,c);sink=warm.at(0);
            // 묶음 측정에는 결과 객체의 파괴도 포함된다. 모든 설정에 동일 적용.
            auto batch=[&](size_t k){auto start=std::chrono::steady_clock::now();for(size_t i=0;i<k;++i){auto z=multiply(a,b,c);sink=z.at(0);}return std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count();};
            size_t k=1;while(k<32768 && batch(k)<target)k*=2;
            for(size_t j=0;j<reps;++j){double elapsed=batch(k);std::cout<<algo<<','<<base<<','<<kt<<','<<tt<<','<<one<<','<<j<<','<<k<<','<<std::setprecision(17)<<elapsed<<'\n';}
        }
#else
        throw std::invalid_argument("grid requires bigint");
#endif
    }
    else if(action=="phases" && argc==9){
#ifdef PHASE_PROFILE
        size_t n=std::stoull(argv[6]);W seed=std::stoull(argv[7]);size_t reps=std::stoull(argv[8]);
        if(!n||!reps)throw std::invalid_argument("n/reps > 0");
        std::mt19937_64 r(seed);Big a=random_big(n,r),b=random_big(n,r);auto warm=multiply(a,b,cfg);sink=warm.at(0);
        for(size_t i=0;i<reps;++i){phase_data={};auto start=std::chrono::steady_clock::now();auto z=multiply(a,b,cfg);auto stop=std::chrono::steady_clock::now();sink=z.at(0);
            double total=std::chrono::duration<double,std::nano>(stop-start).count();
            std::cout<<std::setprecision(17)<<"total,"<<i<<",0,-1,-1,1,"<<total<<'\n';
            for(size_t d=0;d<phase_data.size();++d)for(size_t m=0;m<3;++m)for(size_t p=0;p<PHASES;++p){const auto& c=phase_data[d][m][p];if(c.visits)std::cout<<"phase,"<<i<<','<<d+1<<','<<m<<','<<p<<','<<c.visits<<','<<c.ns<<'\n';}
        }
#else
        throw std::invalid_argument("phases requires bigint_phases");
#endif
    }
    else if(action=="leaves" && argc==9){
#ifdef PROFILE
        size_t n=std::stoull(argv[6]);W seed=std::stoull(argv[7]);if(!n||std::stoull(argv[8])!=1)throw std::invalid_argument("n > 0, reps=1");
        std::mt19937_64 r(seed);Big a=random_big(n,r),b=random_big(n,r);collect_leaves=true;auto z=multiply(a,b,cfg);sink=z.at(0);
        for(const auto& [sizes,count]:leaf_sizes)std::cout<<sizes.first<<','<<sizes.second<<','<<count<<'\n';
#else
        throw std::invalid_argument("leaves requires bigint_profile");
#endif
    }
    else if(action=="benchrect" && argc==10){
#if !defined(PROFILE) && !defined(PHASE_PROFILE)
        size_t n=std::stoull(argv[6]),m=std::stoull(argv[7]);W seed=std::stoull(argv[8]);size_t reps=std::stoull(argv[9]);
        if(!n||!m||!reps||cfg.algo!=Algo::S)throw std::invalid_argument("school only, n/m/reps > 0");
        std::mt19937_64 r(seed);Big a=random_big(n,r),b=random_big(m,r);auto warm=multiply(a,b,cfg);sink=warm.at(0);
        std::vector<double> times;times.reserve(reps);
        for(size_t i=0;i<reps;++i){auto start=std::chrono::steady_clock::now();auto z=multiply(a,b,cfg);auto stop=std::chrono::steady_clock::now();sink=z.at(0);times.push_back(std::chrono::duration<double,std::nano>(stop-start).count());}
        for(double t:times)std::cout<<t<<'\n';
#else
        throw std::invalid_argument("benchrect requires bigint");
#endif
    }
    else if(action=="bench" && argc==9){size_t n=std::stoull(argv[6]);W seed=std::stoull(argv[7]);size_t reps=std::stoull(argv[8]);if(!n||!reps)throw std::invalid_argument("n/reps > 0");std::mt19937_64 r(seed);Big a=random_big(n,r),b=random_big(n,r);
#ifdef PROFILE
        if(reps!=1)throw std::invalid_argument("profile reps=1");cnt={};auto z=multiply(a,b,cfg);sink=z.at(0);std::cout<<cnt.mul<<','<<cnt.accum<<','<<cnt.carry<<','<<cnt.add<<','<<cnt.sub<<','<<cnt.smallmul<<','<<cnt.smalldiv<<','<<cnt.calls<<','<<cnt.school<<','<<cnt.kara<<','<<cnt.toom<<','<<cnt.depth<<'\n';
#else
        auto warm=multiply(a,b,cfg);sink=warm.at(0);std::vector<double> times;times.reserve(reps);for(size_t i=0;i<reps;++i){auto start=std::chrono::steady_clock::now();auto z=multiply(a,b,cfg);auto stop=std::chrono::steady_clock::now();sink=z.at(0);times.push_back(std::chrono::duration<double,std::nano>(stop-start).count());}for(double t:times)std::cout<<t<<'\n';
#endif
    }else throw std::invalid_argument("invalid action");
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;} }
