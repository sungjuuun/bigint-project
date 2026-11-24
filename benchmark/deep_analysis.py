"""실험 2~6 심화: 쌍별 반복 측정, 병목 개선, K 삽입 통제, 역전 경계 정밀화."""
import argparse, csv, hashlib, math, platform, random, statistics as st, subprocess, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from cost_analysis import exe_path, write_csv

BASES=('immediate','deferred')
CN=('mul','accum','carry','add','sub','smallmul','smalldiv','calls','school','kara','toom','depth')
PN=('base','split','evaluate','interpolate','recombine','residual','total','nonbase')
def cfg(a,b,k=32,t=128,one=0): return (a,b,k,t,one)
def quant(v):
    if len(v)<2: return v[0],v[0]
    q=st.quantiles(v,n=4,method='inclusive');return q[0],q[2]
def summary(v): return (st.median(v),*quant(v),min(v),max(v))
def gm(v): return math.exp(st.mean(map(math.log,v)))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',default='build/bigint');p.add_argument('--profile',default='build/bigint_profile');p.add_argument('--phases',default='build/bigint_phases')
    p.add_argument('--inputs',type=int,default=5);p.add_argument('--rounds',type=int,default=3);p.add_argument('--reps',type=int,default=7);p.add_argument('--target-ns',type=int,default=1000000);p.add_argument('--seed',type=int,default=65000)
    p.add_argument('--output',default=None);p.add_argument('--quick',action='store_true');a=p.parse_args()
    if a.quick:a.inputs,a.rounds,a.reps,a.target_ns=2,2,3,100000
    if min(a.inputs,a.rounds,a.reps,a.target_ns)<1:p.error('양수 인수 필요')
    dest=Path(a.output or ('results/local-deep-quick' if a.quick else 'results/local-deep'))
    if dest.exists() and any(dest.iterdir()):dest=dest.with_name(dest.name+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    dest.mkdir(parents=True,exist_ok=False) if not dest.exists() else None
    exe,prof,ph=map(exe_path,(a.exe,a.profile,a.phases));rng=random.Random(a.seed+994)
    raw=[];countrows=[];phaserows=[];comparisons=[];timesrows=[];log=[]
    def say(s):print(s,flush=True);log.append(s)
    def run(e,*args):return subprocess.check_output([e,*map(str,args)],text=True).splitlines()
    def measure(stage,n,configs,offset):
        configs=sorted(set(configs));seeds=[a.seed+offset+i for i in range(a.inputs)]
        records={};per_round={}
        for seed in seeds:
            by=defaultdict(list)
            for rnd in range(a.rounds):
                order=configs.copy();rng.shuffle(order)
                data=''.join(' '.join(map(str,c))+'\n' for c in order)
                lines=subprocess.check_output([exe,'grid','school','immediate','32','128',str(n),str(seed),str(a.reps),str(a.target_ns)],input=data,text=True).splitlines();found=defaultdict(list)
                for line in lines:
                    alg,b,k,t,one,j,batch,elapsed=line.split(',');c=(alg,b,int(k),int(t),int(one));j,batch,elapsed=int(j),int(batch),float(elapsed)
                    if c not in order or batch<1 or elapsed<=0:raise RuntimeError('시간 데이터 오류')
                    ns=elapsed/batch;found[c].append((j,ns));raw.append((stage,n,seed,rnd,order.index(c),*c,j,batch,elapsed,ns))
                if set(found)!=set(order) or any(sorted(j for j,_ in v)!=list(range(a.reps)) for v in found.values()):raise RuntimeError('반복 누락')
                for c,v in found.items():
                    m=st.median(t for _,t in v);by[c].append(m);per_round[seed,rnd,c]=m
            records[seed]={c:st.median(v) for c,v in by.items()}
        for c in configs:timesrows.append((stage,n,*c,*summary([r[c] for r in records.values()])))
        return records,per_round
    def compare(stage,n,label,ref,test,records):
        rs,pr=records
        # 동일 입력·동일 라운드의 비율을 먼저 계산한 후 입력별 중앙값, 마지막으로 입력 간 분포.
        vals=[st.median(pr[seed,r,ref]/pr[seed,r,test] for r in range(a.rounds)) for seed in rs]
        v=summary(vals);comparisons.append((stage,n,label,*ref,*test,*v,sum(x>1 for x in vals),len(vals)))
        return v
    def counts(stage,n,c,seeds):
        alg,b,k,t,one=c
        if one:raise ValueError('단일 분할 계수는 이 함수에서 측정하지 않음')
        out=[]
        for seed in seeds:
            lines=run(prof,'bench',alg,b,k,t,n,seed,1);v=list(map(int,lines[0].split(',')))
            if len(lines)!=1 or len(v)!=len(CN):raise RuntimeError('계측 행 오류')
            countrows.append((stage,n,seed,*c,*v));out.append(dict(zip(CN,v)))
        return out
    def phases(stage,n,c,seeds):
        alg,b,k,t,one=c;out=[]
        for seed in seeds:
            totals={};sums=defaultdict(lambda:[0.]*5)
            for line in run(ph,'phases',alg,b,k,t,n,seed,a.reps):
                typ,j,d,m,q,vis,ns=line.split(',');j,d,m,q,vis=int(j),int(d),int(m),int(q),int(vis);ns=float(ns)
                phaserows.append((stage,n,seed,*c,typ,j,d,m,q,vis,ns))
                if typ=='total':totals[j]=ns
                else:sums[j][q]+=ns
            if len(totals)!=a.reps:raise RuntimeError('구간 계측 누락')
            out.append([st.median([sums[j][i] for j in totals]) for i in range(5)]+[st.median([totals[j]-sum(sums[j]) for j in totals]),st.median(totals.values()),st.median([totals[j]-sums[j][0] for j in totals])])
        return [st.median([v[i] for v in out]) for i in range(8)]
    say('=== 심화 실험: 재현성 강화 / 병목 통제 / 혼합 전략 ===')
    say(f'입력 {a.inputs}쌍 × 순서 재배치 {a.rounds}라운드 × {a.reps}묶음, 묶음 목표 {a.target_ns}ns; '+('점검용' if a.quick else '정규 측정'))
    say('표의 가속률은 같은 입력/라운드 비율의 중앙값 [입력별 Q1,Q3]이다. IQR은 신뢰구간이 아니다.')
    say('\n0. Schoolbook 개선 효과: 작은 입력도 묶음 측정')
    say('limbs    A(ns)     B(ns)    A/B[Q1,Q3]')
    for n in ((8,32,512) if a.quick else (8,16,32,64,128,256,512,1024,4096)):
        ca,cb=(cfg('school',b) for b in BASES);rec=measure('school',n,[ca,cb],50)
        v=compare('school',n,'기초 곱셈 개선',ca,cb,rec);ta,tb=(st.median(r[c] for r in rec[0].values()) for c in (ca,cb))
        say(f'{n:5d} {ta:9.1f} {tb:9.1f}  {v[0]:.2f}[{v[1]:.2f},{v[2]:.2f}]')
    sizes=(128,192,384) if a.quick else (96,112,128,144,160,176,192,208,224,240,256,288,320,352,384,416,448,512)
    say('\n1. 단일 분할 역전 경계 정밀 측정 (Schoolbook / 단일 분할)')
    say('limbs     K-A     K-B     T-A     T-B')
    cross=defaultdict(list)
    for n in sizes:
        cs=[cfg('school',b) for b in BASES]+[cfg(alg,b,8,8,1) for alg in ('kara','toom') for b in BASES]
        rec=measure('cross',n,cs,100);vals=[]
        for alg in ('kara','toom'):
            for b in BASES:
                v=compare('cross',n,alg+'-'+b,cfg('school',b),cfg(alg,b,8,8,1),rec);cross[alg,b].append((n,*v));vals.append(v[0])
        say(f'{n:5d} '+' '.join(f'{v:7.2f}' for v in vals))
    for (alg,b),rr in cross.items():
        hit=next((i for i in range(len(rr)-1) if rr[i][1]>=1.05 and rr[i+1][1]>=1.05),None)
        robust=next((i for i in range(len(rr)-1) if rr[i][2]>=1.05 and rr[i+1][2]>=1.05),None)
        def label(i):return '미확인' if i is None else (f'{rr[0][0]} 이하 가능' if i==0 else f'{rr[i-1][0]}~{rr[i][0]}')
        say(f'{alg:5s} {b:9s}: 중앙값 기준 {label(hit)}, Q1 기준 {label(robust)}')
    say('\n2. 병목 개선: 동일 재귀 구조(KT=32, TT=128), 기본 / 변경 가속률')
    say('limbs base       K분할  K재조합  K둘다  T보간   K둘다/Q1~Q3  T보간/Q1~Q3')
    phase_summary=[]
    for n in ((512,) if a.quick else (512,2048,4096)):
        cs=[cfg(alg,b) for b in BASES for alg in ('kara','kara_split','kara_join','kara_opt','toom','toom_interp')]
        rec=measure('opt',n,cs,200)
        for b in BASES:
            vv=[]
            for alg in ('kara_split','kara_join','kara_opt','toom_interp'):
                orig='toom' if alg.startswith('toom') else 'kara';vv.append(compare('opt',n,alg+'-'+b,cfg(orig,b),cfg(alg,b),rec))
            say(f'{n:5d} {b:9s} '+' '.join(f'{v[0]:7.2f}' for v in vv)+f'    [{vv[2][1]:.2f},{vv[2][2]:.2f}]  [{vv[3][1]:.2f},{vv[3][2]:.2f}]')
            seeds=list(rec[0]);cc={};pp={}
            for alg in ('kara','kara_split','kara_join','kara_opt','toom','toom_interp'):
                c=cfg(alg,b);cc[alg]=counts('opt',n,c,seeds)
                pp[alg]=phases('opt',n,c,seeds)
                phase_summary.append((n,*c,*pp[alg]))
            for alg in ('kara_split','kara_join','kara_opt','toom_interp'):
                orig='toom' if alg.startswith('toom') else 'kara'
                for old,new in zip(cc[orig],cc[alg]):
                    if any(old[key]!=new[key] for key in ('mul','calls','school','kara','toom','depth')):raise RuntimeError('통제 실패: 재귀 구조 또는 블록 곱셈 변경')
            if n==4096 or a.quick:
                say(f'  계측 ns: K 분할 {pp["kara"][1]:.0f}→{pp["kara_opt"][1]:.0f}, 재조합 {pp["kara"][4]:.0f}→{pp["kara_opt"][4]:.0f}; T 보간 {pp["toom"][3]:.0f}→{pp["toom_interp"][3]:.0f}')
                say(f'  T 상수나눗셈 limb 반복 중앙값 {st.median(x["smalldiv"] for x in cc["toom"]):.0f}→{st.median(x["smalldiv"] for x in cc["toom_interp"]):.0f}')
    say('\n3. 혼합 전략 통제: 같은 TT에서 K 삽입만 변경')
    say('limbs base       TT  KT  기본비율[Q1,Q3]  K개선비율[Q1,Q3]  K노드  곱셈감소%')
    policy=[];policy_phases=[]
    for n in ((512,) if a.quick else (256,512,1024,2048,4096,8192)):
        ts=(128,512) if a.quick else (128,256,512)
        cs=[cfg(alg,b,k,t) for b in BASES for t in ts for k in (t,t//2,t//4) for alg in (('hybrid',) if k==t else ('hybrid','hybrid_kopt'))]
        rec=measure('policy',n,cs,300);seeds=list(rec[0]);
        for b in BASES:
            for t in ts:
                ref=cfg('hybrid',b,t,t);old=counts('policy',n,ref,seeds)
                # 같은 TT의 순수 Toom-3와 K 없는 Hybrid가 논리적으로 동일한지 검증한다.
                pure=counts('policy',n,cfg('toom',b,32,t),seeds)
                if old!=pure or any(v['kara']!=0 for v in old):raise RuntimeError('K 생략 대조군 오류')
                for k in (t//2,t//4):
                    c=cfg('hybrid',b,k,t);o=cfg('hybrid_kopt',b,k,t);new=counts('policy',n,c,seeds);newopt=counts('policy',n,o,seeds)
                    if any(any(x[key]!=y[key] for key in ('mul','calls','school','kara','toom','depth')) for x,y in zip(new,newopt)):raise RuntimeError('K 개선에서 재귀 구조 변경')
                    v=compare('policy',n,'K삽입',ref,c,rec);w=compare('policy',n,'K개선삽입',ref,o,rec)
                    nodes=st.median(x['kara'] for x in new);saved=st.median(100*(1-y['mul']/x['mul']) for x,y in zip(old,new))
                    policy.append((n,b,k,t,*v,*w,nodes,saved))
                    # 핵심 설정만 화면에 출력, 모든 설정은 CSV에 저장한다.
                    if k==t//2 and t==(128 if b=='immediate' else 512):
                        say(f'{n:5d} {b:9s} {t:3d} {k:3d}  {v[0]:.2f}[{v[1]:.2f},{v[2]:.2f}]  {w[0]:.2f}[{w[1]:.2f},{w[2]:.2f}]  {nodes:6.0f}  {saved:7.2f}')
                        if n in (512,4096):
                            pr=phases('policy',n,ref,seeds);pt=phases('policy',n,c,seeds);po=phases('policy',n,o,seeds)
                            for target,pp in ((c,pt),(o,po)):
                                policy_phases.append((n,b,k,t,target[0],pr[0],pp[0],pr[7],pp[7],pr[6],pp[6],pr[0]-pp[0],pp[7]-pr[7]))
                            say(f'  계측 기초비용 절감/추가 비기초비용(ns): 기존K {pr[0]-pt[0]:.0f}/{pt[7]-pr[7]:.0f}; 개선K {pr[0]-po[0]:.0f}/{po[7]-pr[7]:.0f}')
    say('\n4. 기존 방식과 선택된 임계값 재검증: 별도 시드, 최종 기본 비교')
    say('limbs base       S(ms)     K(ms)     T(ms)     H(ms)   K/S가속 T/S가속 H/S가속')
    # v0.3 사용자 PC에서 선택한 설정을 고정. 이 실험의 결과로 다시 선택하지 않는다.
    hold=[]
    for n in ((128,512) if a.quick else (128,256,512,1024,2048,4096,8192)):
        selected={'immediate':(256,256,128,128),'deferred':(512,512,256,512)}
        cs=[]
        for b,(k,t,hk,ht) in selected.items():cs += [cfg('school',b),cfg('kara',b,k,128),cfg('toom',b,32,t),cfg('hybrid',b,hk,ht)]+[cfg(alg,b) for alg in ('kara','toom','hybrid')]
        rec=measure('hold',n,cs,400)
        for b,(k,t,hk,ht) in selected.items():
            chosen=[cfg('school',b),cfg('kara',b,k,128),cfg('toom',b,32,t),cfg('hybrid',b,hk,ht)]
            ms=[st.median(r[c] for r in rec[0].values())/1e6 for c in chosen];v=[]
            for c in chosen[1:]:
                v.append(compare('hold',n,'Schoolbook 대비',chosen[0],c,rec)[0]);compare('hold',n,'고정 대비',cfg(c[0],b),c,rec)
            hold.append((n,b,*ms,*v));say(f'{n:5d} {b:9s} '+' '.join(f'{m:9.4f}' for m in ms)+'  '+' '.join(f'{x:7.2f}' for x in v))
    say('주의: 1.00 부근 또는 IQR이 1을 포함하는 차이는 우열을 단정하지 않는다. 계측 시간은 별도 실행의 근사값이다.')
    say(f'결과 저장: {dest}')
    cc=['algorithm','basecase','kt','tt','one_level'];ss=['median','q1','q3','min','max']
    write_csv(dest/'raw.csv',['stage','limbs','seed','round','order',*cc,'repeat','batch','elapsed_ns','ns_per_call'],raw)
    write_csv(dest/'times_summary.csv',['stage','limbs',*cc,*[x+'_ns' for x in ss]],timesrows)
    write_csv(dest/'comparisons.csv',['stage','limbs','label',*['ref_'+x for x in cc],*['test_'+x for x in cc],*ss,'inputs_faster','inputs_total'],comparisons)
    write_csv(dest/'counts.csv',['stage','limbs','seed',*cc,*CN],countrows)
    write_csv(dest/'phases.csv',['stage','limbs','seed',*cc,'type','repeat','depth','mode','phase','visits','ns'],phaserows)
    write_csv(dest/'phase_summary.csv',['limbs',*cc,*[x+'_ns' for x in PN]],phase_summary)
    write_csv(dest/'policy.csv',['limbs','basecase','kt','tt',*['old_'+x for x in ss],*['optimized_'+x for x in ss],'kara_nodes_median','mul_reduction_pct_median'],policy)
    write_csv(dest/'policy_phases.csv',['limbs','basecase','kt','tt','algorithm','ref_base_ns','test_base_ns','ref_nonbase_ns','test_nonbase_ns','ref_total_ns','test_total_ns','base_saved_ns','extra_nonbase_ns'],policy_phases)
    write_csv(dest/'holdout.csv',['limbs','basecase','school_ms','kara_ms','toom_ms','hybrid_ms','school_over_kara','school_over_toom','school_over_hybrid'],hold)
    (dest/'console.txt').write_text('\n'.join(log)+'\n',encoding='utf-8')
    def command(*cmd):
        try:return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT).strip()
        except (OSError,subprocess.CalledProcessError):return '확인 불가'
    meta=[f'platform={platform.platform()}',f'processor={platform.processor()}',f'python={sys.version}',f'args={a}',f'git={command("git","rev-parse","HEAD")}',f'git_status={command("git","status","--short")}',f'compiler_on_PATH={command("g++","--version")}']
    for e in (exe,prof,ph):meta.append(f'{Path(e).name}_sha256={hashlib.sha256(Path(e).read_bytes()).hexdigest()}')
    cache=Path(exe).parent/'CMakeCache.txt'
    if cache.exists():meta.extend(x for x in cache.read_text(encoding='utf-8',errors='replace').splitlines() if x.startswith(('CMAKE_CXX_COMPILER:','CMAKE_BUILD_TYPE:','CMAKE_CXX_FLAGS_RELEASE:')))
    (dest/'environment.txt').write_text('\n'.join(meta)+'\n',encoding='utf-8')
if __name__=='__main__':main()
