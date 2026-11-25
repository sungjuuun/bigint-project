"""기존 실험의 마지막 재검증: 역전의 비단조성, K 삽입의 실제 손익, 개선 정책 독립 평가."""
import argparse, csv, hashlib, platform, random, statistics as st, subprocess, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASES=('immediate','deferred')
def cfg(a,b,k=32,t=128): return a,b,k,t,0
def run(e,*args, data=None): return subprocess.check_output([str(e),*map(str,args)],input=data,text=True).splitlines()
def exe(p):
    p=Path(p).resolve()
    if not p.is_file():p=p.with_suffix('.exe')
    if not p.is_file():raise FileNotFoundError(p)
    return p
def stats(x):
    q=st.quantiles(x,n=4,method='inclusive') if len(x)>1 else [x[0]]*3
    return st.median(x),q[0],q[2]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--quick',action='store_true');p.add_argument('--inputs',type=int,default=7);p.add_argument('--rounds',type=int,default=3);p.add_argument('--reps',type=int,default=7);p.add_argument('--seed',type=int,default=97000);p.add_argument('--output',default='results/local-followup');p.add_argument('--build',default='build');a=p.parse_args()
    if a.quick:a.inputs,a.rounds,a.reps=2,1,2
    if min(a.inputs,a.rounds,a.reps)<1:p.error('양수 필요')
    e,c,f=(exe(Path(a.build)/x) for x in ('bigint','bigint_profile','bigint_phases'))
    out=Path(a.output+('-quick' if a.quick else ''))
    if out.exists():out=out.with_name(out.name+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir(parents=True); rng=random.Random(a.seed+8); raw=[]; ratios=[]; counts=[]; phases=[]; leaves=[]; log=[]; details=[]
    def say(s):print(s,flush=True);log.append(s)
    def measure(stage,n,configs,seeds):
        configs=list(dict.fromkeys(configs)); rr={}
        for seed in seeds:
            for r in range(a.rounds):
                order=configs.copy();rng.shuffle(order);groups=defaultdict(list)
                for line in run(e,'grid','school','immediate',32,128,n,seed,a.reps,100000 if a.quick else 2000000,data=''.join(' '.join(map(str,v))+'\n' for v in order)):
                    alg,b,k,t,o,j,batch,ns=line.split(',');key=(alg,b,int(k),int(t),int(o));j,batch,ns=int(j),int(batch),float(ns)
                    if key not in order or batch<1 or ns<=0:raise RuntimeError('측정값 오류')
                    groups[key].append((j,ns/batch));raw.append((stage,n,seed,r,order.index(key),*key,j,batch,ns,ns/batch))
                if set(groups)!=set(configs) or any(sorted(j for j,_ in v)!=list(range(a.reps)) for v in groups.values()):raise RuntimeError('측정 누락')
                rr[seed,r]={k:st.median(v for _,v in x) for k,x in groups.items()}
        return rr
    def compare(stage,n,ref,test,rr,seeds):
        v=[st.median(rr[s,r][ref]/rr[s,r][test] for r in range(a.rounds)) for s in seeds];med,q1,q3=stats(v)
        ratios.append((stage,n,*ref,*test,med,q1,q3,min(v),max(v),sum(x>1 for x in v),len(v)))
        return med,q1,q3
    def profile(stage,n,key,seed):
        alg,b,k,t,o=key
        vals=list(map(int,run(c,'bench',alg,b,k,t,n,seed,1)[0].split(',')))
        if len(vals)!=12:raise RuntimeError('계측 열 오류')
        counts.append((stage,n,seed,*key,*vals));sizes=[]
        for line in run(c,'leaves',alg,b,k,t,n,seed,1):
            x,y,v=map(int,line.split(','));sizes.append((x,y,v));leaves.append((stage,n,seed,*key,x,y,v))
        if sum(v for x,y,v in sizes)!=vals[8] or sum(x*y*v for x,y,v in sizes)!=vals[0]:raise RuntimeError('말단 집계 불일치')
        totals={};base=defaultdict(float)
        for line in run(f,'phases',alg,b,k,t,n,seed,a.reps):
            typ,j,d,m,q,v,ns=line.split(',');j,d,m,q,v,ns=int(j),int(d),int(m),int(q),int(v),float(ns)
            phases.append((stage,n,seed,*key,typ,j,d,m,q,v,ns))
            if typ=='total':totals[j]=ns
            elif q==0:base[j]+=ns
        if len(totals)!=a.reps:raise RuntimeError('구간 측정 누락')
        return vals,sizes,st.median(base[j] for j in totals),st.median(totals[j]-base[j] for j in totals)
    def fmt(v):return f'{v[0]:.3f}[{v[1]:.3f},{v[2]:.3f}]'
    say('=== 기존 실험의 최종 재검증: 별도 시드, 쌍별 비교 ===')
    say(f'입력 {a.inputs}개 × {a.rounds}라운드 × {a.reps}묶음. IQR은 신뢰구간이 아님.')
    say('\n1. Karatsuba 단일 분할: 128 부근 비단조성 재검증')
    say('limbs A 가속률[Q1,Q3] B 가속률[Q1,Q3]')
    for n in ((124,128,132) if a.quick else (64,80,96,112,120,124,128,132,136,144,160,176,192,208)):
        # 원래 v0.4와 동일한 단일 분할 설정으로 시간을 측정한다.
        keys=[key for b in BASES for key in (cfg('school',b),('kara',b,8,8,1))];seeds=[a.seed+100+i for i in range(a.inputs)]
        rr=measure('cross',n,keys,seeds);v=[]
        for b in BASES:
            ref,test=cfg('school',b),('kara',b,8,8,1);v.append(compare('cross',n,ref,test,rr,seeds))
            if n in (124,128,132):
                for seed in seeds:
                    # 계측 실행 파일은 one_level 옵션이 없으므로 동등한 n-1 임계값을 사용한다.
                    z=profile('cross_equivalent',n,cfg('kara',b,n-1,128),seed)
                    if z[0][9]!=1 or z[0][10]!=0:raise RuntimeError('단일 분할 실패')
        say(f'{n:5d} {fmt(v[0])} {fmt(v[1])}')
    say('\n2. K 삽입 통제: 동일 TT, 말단 크기와 기초/비기초 비용 차이')
    say('limbs base KT/TT K호출 곱셈절감% 기존/개선 가속률 기초절감/추가비용(us, 쌍별 중앙값)')
    cases=[(512,'immediate',64,128),(2048,'immediate',64,128),(4096,'immediate',64,128),(4096,'immediate',128,512),(4096,'deferred',256,512)]
    for n,b,k,t in (cases[:2] if a.quick else cases):
        ref=cfg('hybrid',b,t,t);old=cfg('hybrid',b,k,t);opt=cfg('hybrid_kopt',b,k,t);seeds=[a.seed+200+i for i in range(a.inputs)];rr=measure('policy',n,[ref,old,opt],seeds)
        v=compare('policy',n,ref,old,rr,seeds);w=compare('policy',n,ref,opt,rr,seeds);nodes=[];saved=[];ds=[[],[]];do=[[],[]]
        for seed in seeds:
            rr0,rr1,rr2=[profile('policy',n,x,seed) for x in (ref,old,opt)]
            if rr0[0][9]!=0 or rr1[0][0]!=rr2[0][0] or rr1[0][9]!=rr2[0][9]:raise RuntimeError('통제 실패')
            nodes.append(rr1[0][9]);saved.append(100*(1-rr1[0][0]/rr0[0][0]))
            for i,x in enumerate((rr1,rr2)):
                ds[i].append((rr0[2]-x[2])/1000);do[i].append((x[3]-rr0[3])/1000)
                details.append((n,b,k,t,seed,i,rr0[2],x[2],rr0[3],x[3],ds[i][-1],do[i][-1]))
        say(f'{n:5d} {b:9s} {k}/{t} {st.median(nodes):.0f} {st.median(saved):.2f} {fmt(v)} {fmt(w)} {st.median(ds[0]):.1f}/{st.median(do[0]):.1f} {st.median(ds[1]):.1f}/{st.median(do[1]):.1f}')
    say('\n3. 개선 정책 독립 평가: v0.4 원본에서 고른 후보를 새로운 시드로 검증')
    say('limbs base 기존 H 대비 개선 후보 가속률[Q1,Q3] / 같은 TT의 K 없는 정책 대비')
    for n in ((512,2048) if a.quick else (256,512,1024,2048,4096,8192)):
        for b in BASES:
            old=cfg('hybrid',b,128,128) if b=='immediate' else cfg('hybrid',b,256,512)
            choices=[(128,512),(128,256)] if b=='immediate' else [(256,512)]
            keys=[old,cfg('school',b)]
            for k,t in choices:keys.extend([cfg('hybrid_kopt',b,k,t),cfg('hybrid',b,t,t)])
            seeds=[a.seed+300+i for i in range(a.inputs)];rr=measure('hold',n,keys,seeds)
            for k,t in choices:
                test=cfg('hybrid_kopt',b,k,t);v=compare('hold',n,old,test,rr,seeds);w=compare('hold',n,cfg('hybrid',b,t,t),test,rr,seeds);s=compare('hold',n,cfg('school',b),test,rr,seeds)
                say(f'{n:5d} {b:9s} {k}/{t} {fmt(v)} / {fmt(w)} / S대비 {fmt(s)}')
    def write(name,fields,rows):
        with (out/name).open('w',newline='',encoding='utf-8') as f0: w=csv.writer(f0);w.writerow(fields.split());w.writerows(rows)
    key='algorithm basecase kt tt one_level';rk=' '.join('ref_'+s for s in key.split());tk=' '.join('test_'+s for s in key.split())
    write('raw.csv','stage limbs seed round order '+key+' repeat batch elapsed_ns ns_per_call',raw);write('ratios.csv','stage limbs '+rk+' '+tk+' median q1 q3 min max inputs_faster inputs_total',ratios)
    write('counts.csv','stage limbs seed '+key+' mul accum carry add sub smallmul smalldiv calls school kara toom depth',counts);write('leaves.csv','stage limbs seed '+key+' n m count',leaves);write('phases.csv','stage limbs seed '+key+' type repeat depth mode phase visits ns',phases);write('policy_differences.csv','limbs basecase kt tt seed optimized ref_base_ns test_base_ns ref_nonbase_ns test_nonbase_ns saved_us extra_us',details)
    say('주의: 별도 계측 실행은 일반 실행과 다르며, 차이의 중앙값은 전체 시간 중앙값의 차이와 같지 않을 수 있음.');say(f'저장: {out}')
    (out/'console.txt').write_text('\n'.join(log)+'\n',encoding='utf-8')
    def cmd(*x):
        try:return subprocess.check_output(x,text=True,stderr=subprocess.STDOUT).strip()
        except (OSError,subprocess.CalledProcessError):return '확인 불가'
    meta=[str(a),platform.platform(),platform.processor(),sys.version,cmd('git','rev-parse','HEAD'),cmd('git','status','--short'),cmd('g++','--version')]+[str(x.name)+' '+hashlib.sha256(x.read_bytes()).hexdigest() for x in (e,c,f)]
    cache=Path(a.build)/'CMakeCache.txt'
    if cache.exists():meta.extend(x for x in cache.read_text(encoding='utf-8',errors='replace').splitlines() if x.startswith(('CMAKE_CXX_COMPILER:','CMAKE_BUILD_TYPE:','CMAKE_CXX_FLAGS_RELEASE:')))
    (out/'environment.txt').write_text('\n'.join(meta)+'\n',encoding='utf-8')
if __name__=='__main__':main()
