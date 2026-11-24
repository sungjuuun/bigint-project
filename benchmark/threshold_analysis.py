"""실험 4~6: 단일 분할의 손익, 임계값 탐색, 독립 입력으로 혼합 전략 검증."""
import argparse, math, platform, random, statistics as st, subprocess, sys
from collections import defaultdict
from pathlib import Path
from cost_analysis import exe_path, write_csv

BASES = ('immediate', 'deferred')
ALGOS = ('school', 'kara', 'toom', 'hybrid')
CUTS = (8, 16, 32, 64, 128, 256, 512, 1024, 2048)
SIZES = (16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048, 3072, 4096)

def cfg(a,b,k=32,t=128,one=0): return a,b,k,t,one
def geom(xs): return math.exp(st.mean(math.log(x) for x in xs))
def baseline(b): return cfg('school',b)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',default='build/bigint');p.add_argument('--output',default='results/local-threshold')
    p.add_argument('--reps',type=int,default=7);p.add_argument('--target-ns',type=int,default=1000000)
    p.add_argument('--quick',action='store_true',help='점검용; 최종 분석에 사용하지 않음')
    args=p.parse_args()
    if args.reps<3 or args.target_ns<10000: p.error('반복 3 이상, 목표 묶음 시간 10000ns 이상 필요')
    dest=Path('results/local-threshold-quick' if args.quick and args.output=='results/local-threshold' else args.output);dest.mkdir(parents=True,exist_ok=True)
    exe=exe_path(args.exe);rng=random.Random(20261125);raw=[];log=[]
    def say(s): print(s,flush=True);log.append(s)
    def measure(stage,n,seed,configs):
        order=sorted(set(configs));rng.shuffle(order)
        data=''.join(' '.join(map(str,c))+'\n' for c in order)
        lines=subprocess.check_output([exe,'grid','school','immediate','32','128',str(n),str(seed),str(args.reps),str(args.target_ns)],input=data,text=True).splitlines()
        found=defaultdict(list)
        for line in lines:
            a,b,k,t,one,j,batch,elapsed=line.split(',');c=(a,b,int(k),int(t),int(one));j,batch,elapsed=int(j),int(batch),float(elapsed)
            if c not in order or batch<1 or elapsed<=0: raise RuntimeError('측정 데이터 오류')
            ns=elapsed/batch;found[c].append((j,ns));raw.append((stage,n,seed,*c,j,batch,elapsed,ns))
        if set(found)!=set(order) or any(sorted(j for j,_ in ts)!=list(range(args.reps)) for ts in found.values()): raise RuntimeError('측정 설정 또는 반복 누락')
        return {c:st.median(t for _,t in ts) for c,ts in found.items()}
    sizes=(16,64,256) if args.quick else SIZES
    train_sizes=(64,256) if args.quick else (256,1024,4096)
    hold_sizes=(32,128,512) if args.quick else (128,256,512,1024,2048,4096,8192)
    cuts=(8,32,128) if args.quick else CUTS
    split_seeds=(52001,) if args.quick else (52001,52002,52003)
    train_seeds=(53001,) if args.quick else (53001,53002)
    hold_seeds=(54001,) if args.quick else (54001,54002,54003)
    say('=== 단일 분할 및 임계값 실험 (묶음 시간 측정) ===');say('점검 모드' if args.quick else '정규 측정: 단일 분할 / 튜닝 / 독립 평가 시드 분리')
    say('\n1. 한 단계 분할의 Schoolbook 대비 가속률');say('limbs     K-A     K-B     T-A     T-B')
    split_rows=[];one_configs=[baseline(b) for b in BASES]+[cfg(a,b,8,8,1) for a in ('kara','toom') for b in BASES]
    for n in sizes:
        records=[measure('one_level',n,s,one_configs) for s in split_seeds];vals=[]
        for a in ('kara','toom'):
            for b in BASES:
                c=cfg(a,b,8,8,1);ratios=[r[baseline(b)]/r[c] for r in records];v=st.median(ratios);vals.append(v)
                split_rows.append((n,a,b,st.median(r[baseline(b)] for r in records),st.median(r[c] for r in records),v,min(ratios),max(ratios)))
        say(f'{n:5d} '+' '.join(f'{v:7.2f}' for v in vals))
    say('단일 분할 역전 관측: 가속률 1.05 이상인 크기 2개 연속일 때 최초 구간 표시')
    for a in ('kara','toom'):
        for b in BASES:
            rr=[r for r in split_rows if r[1:3]==(a,b)];hit=next((i for i in range(len(rr)-1) if rr[i][5]>=1.05 and rr[i+1][5]>=1.05),None)
            label='관측 범위에서 미확인' if hit is None else (f'{rr[0][0]} 이하 가능(하한 미측정)' if hit==0 else f'{rr[hit-1][0]}~{rr[hit][0]} 부근(관측 격자)')
            say(f'{a:6s} {b:9s}: {label}')
    candidates=[baseline(b) for b in BASES]
    for b in BASES:
        candidates += [cfg('kara',b,k,128) for k in cuts]+[cfg('toom',b,32,t) for t in cuts]+[cfg('hybrid',b,k,t) for k in cuts for t in cuts if k<=t]
    train=defaultdict(list);say('\n2. 임계값 탐색: 훈련 입력에서만 설정 선택')
    for n in train_sizes:
        for seed in train_seeds:
            r=measure('tune',n,seed,candidates)
            for c,t in r.items(): train[c].append(t/r[baseline(c[1])])
        say(f'튜닝 측정 완료: {n} limbs')
    ranked={c:geom(v) for c,v in train.items()};selected={}
    for b in BASES:
        for a in ALGOS[1:]:
            c=min((c for c in ranked if c[:2]==(a,b)),key=lambda c:(ranked[c],c));selected[a,b]=c
            say(f'{a:6s} {b:9s} KT={c[2]:4d} TT={c[3]:4d} 상대시간={ranked[c]:.3f}')
    tune_rows=[(*c,score,int(c in selected.values())) for c,score in sorted(ranked.items())]
    hold_configs=[baseline(b) for b in BASES]+list(selected.values())+[cfg(a,b) for a in ALGOS[1:] for b in BASES]
    hold_rows=[];hybrid_rows=[];say('\n3. 독립 평가: 고정 대비 / Schoolbook 대비 튜닝 가속률');say('limbs  algo    base       fixed/tuned  school/tuned')
    for n in hold_sizes:
        records=[measure('holdout',n,s,hold_configs) for s in hold_seeds]
        for b in BASES:
            h=selected['hybrid',b]; k=selected['kara',b]; t=selected['toom',b]
            hybrid_rows.append((n,b,st.median(r[k]/r[h] for r in records),st.median(r[t]/r[h] for r in records),st.median(min(r[k],r[t],r[baseline(b)])/r[h] for r in records)))
            for a in ALGOS[1:]:
                c=selected[a,b];fixed=cfg(a,b);f=st.median(r[fixed]/r[c] for r in records);z=st.median(r[baseline(b)]/r[c] for r in records)
                hold_rows.append((n,a,b,c[2],c[3],st.median(r[baseline(b)] for r in records),st.median(r[fixed] for r in records),st.median(r[c] for r in records),f,z))
                say(f'{n:5d}  {a:6s}  {b:9s} {f:11.2f} {z:13.2f}')
    say('\n4. 독립 평가 요약: 크기별 가속률 기하평균')
    for b in BASES:
        for a in ALGOS[1:]:
            rr=[r for r in hold_rows if r[1:3]==(a,b)]
            say(f'{a:6s} {b:9s} 기존대비={geom(r[8] for r in rr):.3f} Schoolbook대비={geom(r[9] for r in rr):.3f}')
    say('\n5. 혼합 전략 직접 비교: 1보다 크면 Hybrid 우세');say('limbs base       K/H     T/H   best/H')
    for n,b,k,t,best in hybrid_rows: say(f'{n:5d} {b:9s} {k:7.2f} {t:7.2f} {best:8.2f}')
    say('best/H: 입력별 Schoolbook, Karatsuba, Toom-3 중 가장 빠른 시간 / Hybrid 시간')
    say('주의: 관측 격자와 후보 범위 내 결과이며 전역 최적값 또는 보편적 역전점이 아님.');say(f'원본 및 요약 저장: {dest}')
    write_csv(dest/'raw.csv',['stage','limbs','seed','algorithm','basecase','kt','tt','one_level','repeat','batch','elapsed_ns','ns_per_call'],raw)
    write_csv(dest/'one_level.csv',['limbs','algorithm','basecase','school_ns','one_level_ns','median_speedup','min_speedup','max_speedup'],split_rows)
    write_csv(dest/'tuning.csv',['algorithm','basecase','kt','tt','one_level','relative_time','selected'],tune_rows)
    write_csv(dest/'holdout.csv',['limbs','algorithm','basecase','kt','tt','school_ns','fixed_ns','tuned_ns','fixed_over_tuned','school_over_tuned'],hold_rows)
    write_csv(dest/'hybrid.csv',['limbs','basecase','kara_over_hybrid','toom_over_hybrid','best_nonhybrid_over_hybrid'],hybrid_rows)
    (dest/'console.txt').write_text('\n'.join(log)+'\n',encoding='utf-8')
    def command(*cmd):
        try: return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT).strip()
        except (OSError,subprocess.CalledProcessError): return '확인 불가'
    (dest/'environment.txt').write_text(f'platform={platform.platform()}\nprocessor={platform.processor()}\npython={sys.version}\nargs={args}\ncompiler={command("g++","--version")}\ngit={command("git","rev-parse","HEAD")}\ngit_status={command("git","status","--short")}\n',encoding='utf-8')

if __name__=='__main__': main()
