"""초기 탐색: 고정 임계값에서 시간 및 연산량 수집 (최종 튜닝 결과 아님)."""
import argparse, csv, random, subprocess, statistics, platform, sys
from pathlib import Path

COLS='mul accum carry add sub smallmul smalldiv calls school kara toom depth'.split()
CONFIGS=[(a,b,32,128) for a in ('school','kara','toom','hybrid') for b in ('immediate','deferred')]
SIZES=[8,16,32,64,128,256,512,1024,2048,4096]

def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',default='build/bigint');p.add_argument('--profile',default='build/bigint_profile');p.add_argument('--output',default='results/pilot');p.add_argument('--inputs',type=int,default=3);p.add_argument('--reps',type=int,default=5);p.add_argument('--max-limbs',type=int,default=4096);args=p.parse_args()
    dest=Path(args.output);dest.mkdir(parents=True,exist_ok=True)
    exe=str(Path(args.exe).resolve());prof=str(Path(args.profile).resolve());rng=random.Random(725)
    fields=['limbs','seed','algorithm','basecase','kt','tt'];alltimes=[]
    with (dest/'times.csv').open('w',newline='',encoding='utf-8') as f,(dest/'counts.csv').open('w',newline='',encoding='utf-8') as g:
        tw=csv.writer(f);cw=csv.writer(g);tw.writerow(fields+['repeat','ns']);cw.writerow(fields+COLS)
        for n in SIZES:
            if n>args.max_limbs:continue
            for i in range(args.inputs):
                seed=2026112500+i;configs=CONFIGS.copy();rng.shuffle(configs)
                for a,b,kt,tt in configs:
                    row=[n,seed,a,b,kt,tt];argv=['bench',a,b,str(kt),str(tt),str(n),str(seed)]
                    times=list(map(float,subprocess.check_output([exe,*argv,str(args.reps)],text=True).splitlines()))
                    if len(times)!=args.reps:raise RuntimeError('time rows')
                    for j,t in enumerate(times):tw.writerow(row+[j,t]);alltimes.append(row+[j,t])
                    counts=list(map(int,subprocess.check_output([prof,*argv,'1'],text=True).strip().split(',')))
                    if len(counts)!=len(COLS):raise RuntimeError('counter columns')
                    cw.writerow(row+counts)
                    if a=='school':
                        assert counts[0]==n*n and counts[1]==n*n and counts[2]==(n*n if b=='immediate' else 2*n)
            print(f'완료: {n} limbs',flush=True)
    groups={}
    for n,seed,a,b,kt,tt,j,t in alltimes:groups.setdefault((n,a,b,kt,tt),[]).append(t)
    with (dest/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['limbs','algorithm','basecase','kt','tt','median_ns','mean_ns','stdev_ns','samples'])
        for key,ts in sorted(groups.items()):w.writerow([*key,statistics.median(ts),statistics.mean(ts),statistics.stdev(ts) if len(ts)>1 else 0,len(ts)])
    (dest/'environment.txt').write_text(f'platform={platform.platform()}\npython={sys.version}\ninputs={args.inputs}\nreps={args.reps}\nmax_limbs={args.max_limbs}\n',encoding='utf-8')
if __name__=='__main__':main()
