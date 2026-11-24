"""실험 3: 구간별 비용 분해, 실제 말단 크기 분포, 독립 Schoolbook 측정."""
import argparse
import csv
import platform
import random
import statistics as st
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

BASES = ('immediate', 'deferred')
ALGOS = ('kara', 'toom', 'hybrid')
PHASES = ('base', 'split', 'evaluate', 'interpolate', 'recombine', 'residual')


def write_csv(path, fields, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(fields)
        w.writerows(rows)


def exe_path(path):
    p = Path(path).resolve()
    if not p.exists() and p.with_suffix('.exe').exists():
        p = p.with_suffix('.exe')
    if not p.is_file():
        raise FileNotFoundError(p)
    return str(p)


def run(exe, *args):
    return subprocess.check_output([exe, *map(str, args)], text=True).splitlines()


def times(exe, *args, reps):
    ts = [float(t) for t in run(exe, *args, reps)]
    if len(ts) != reps or min(ts) < 0:
        raise RuntimeError('시간 측정 행 수 또는 값 오류')
    return ts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe', default='build/bigint')
    p.add_argument('--profile', default='build/bigint_profile')
    p.add_argument('--phases', default='build/bigint_phases')
    p.add_argument('--output', default='results/local-cost')
    p.add_argument('--sizes', type=int, nargs='+', default=[512, 2048, 4096])
    p.add_argument('--inputs', type=int, default=3)
    p.add_argument('--reps', type=int, default=9)
    p.add_argument('--leaf-reps', type=int, default=31)
    p.add_argument('--micro-target-ns',type=int,default=100000,help='작은 말단 곱셈의 묶음 목표 시간')
    args = p.parse_args()
    if min(args.sizes) < 1 or min(args.inputs, args.reps, args.leaf_reps, args.micro_target_ns) < 1:
        p.error('모든 크기와 반복 수는 양수여야 함')
    dest = Path(args.output)
    dest.mkdir(parents=True, exist_ok=True)
    exe, prof, ph = map(exe_path, (args.exe, args.profile, args.phases))
    rng = random.Random(3026)
    raw_time, raw_ph, raw_leaf, raw_micro, records, count_rows = [], [], [], [], [], []
    cache = {}
    log = []
    def say(s):
        print(s, flush=True)
        log.append(s)

    def micro(n, m, seed):
        # 양쪽 구현에서 동일한 입력을 사용하되 재귀 실험과 다른 시드 사용.
        key = (n, m, seed)
        if key not in cache:
            order = list(BASES)
            rng.shuffle(order)
            # 같은 입력을 생성한 한 프로세스에서 A/B를 묶어 측정한다.
            data=''.join(f'school {b} 32 128 0\n' for b in order)
            lines=subprocess.check_output([exe,'rectgrid','school','immediate','32','128',str(n),str(m),str(seed),str(args.leaf_reps),str(args.micro_target_ns)],input=data,text=True).splitlines()
            found=defaultdict(list)
            for line in lines:
                alg,b,k,t,one,j,batch,elapsed=line.split(',');j,batch,elapsed=int(j),int(batch),float(elapsed)
                if alg!='school' or b not in BASES or batch<1 or elapsed<=0:raise RuntimeError('미세 측정 데이터 오류')
                ns=elapsed/batch;found[b].append((j,ns));raw_micro.append((n,m,seed,b,j,batch,elapsed,ns))
            if set(found)!=set(BASES) or any(sorted(j for j,_ in v)!=list(range(args.leaf_reps)) for v in found.values()):raise RuntimeError('미세 측정 반복 누락')
            result={b:st.median(ns for _,ns in v) for b,v in found.items()}
            cache[key] = result
        return cache[key]

    say('=== 실험 3: 비용 구조 분석 (KT=32, TT=128, 탐색용 고정값) ===')
    say('1. Schoolbook 크기별 독립 측정 | 단위: ns')
    say(f'{"limbs":>7} {"Immediate":>12} {"Deferred":>12} {"가속률":>8}')
    for n in [8, 16, 32, 64, 128, 256, 512, 1024, 4096]:
        rr = [micro(n, n, 310000+i) for i in range(args.inputs)]
        a, b = (st.median([x[k] for x in rr]) for k in BASES)
        say(f'{n:7d} {a:12.1f} {b:12.1f} {a/b if b else float("nan"):8.2f}')

    for n in sorted(set(args.sizes)):
        for i in range(args.inputs):
            seed = 2026113000 + i
            configs = [(a, b) for a in ALGOS for b in BASES]
            rng.shuffle(configs)
            for a, b in configs:
                key = (n, seed, a, b)
                common = (a, b, 32, 128, n, seed)
                ts = times(exe, 'bench', *common, reps=args.reps)
                raw_time.extend((*key, j, t) for j, t in enumerate(ts))
                totals, phase_sums = {}, defaultdict(lambda: [0.] * 5)
                for line in run(ph, 'phases', *common, args.reps):
                    kind, j, d, mode, cat, visits, ns = line.split(',')
                    j, d, mode, cat, visits, ns = int(j), int(d), int(mode), int(cat), int(visits), float(ns)
                    raw_ph.append((*key, kind, j, d, mode, cat, visits, ns))
                    if kind == 'total':
                        totals[j] = ns
                    else:
                        phase_sums[j][cat] += ns
                if set(totals) != set(range(args.reps)):
                    raise RuntimeError('구간 시간 반복 누락')
                fractions = []
                for j, total in totals.items():
                    residual = total - sum(phase_sums[j])
                    if residual < -1e-6 or total <= 0:
                        raise RuntimeError('구간 중복 또는 시간 오류')
                    fractions.append([v/total for v in phase_sums[j] + [residual]])
                counts = [int(v) for v in run(prof, 'bench', *common, 1)[0].split(',')]
                count_rows.append((*key, *counts))
                leaves = [tuple(map(int, l.split(','))) for l in run(prof, 'leaves', *common, 1)]
                if sum(c for _, _, c in leaves) != counts[8] or sum(x*y*c for x,y,c in leaves) != counts[0]:
                    raise RuntimeError('말단 분포와 기존 연산 계측 불일치')
                for x,y,c in leaves:
                    raw_leaf.append((*key,x,y,c))
                # 실제 말단 크기와 개수를 가중치로 한 별도 Schoolbook 비용 추정.
                est = dict.fromkeys(BASES, 0.)
                for x,y,c in leaves:
                    v = micro(x,y,410000+i)
                    for k in BASES:
                        est[k] += c*v[k]
                # 평균 비중은 합이 100%가 되도록 동일한 반복 집합에 대해 계산.
                frac = [st.mean(x[k] for x in fractions) for k in range(6)]
                records.append(dict(n=n,seed=seed,algo=a,base=b,normal=st.median(ts),profile=st.median(totals.values()),frac=frac,leaf_a=est[BASES[0]],leaf_b=est[BASES[1]]))
            say(f'재귀 측정 완료: {n} limbs, 입력 {i+1}/{args.inputs}')

    say('\n2. 재귀 비용 구성 | 각 구간은 계측 실행 총 시간 대비 비율(%)')
    say('기초곱셈 / 분할 / 평가 / 보간 / 재조합 / 미분류 / 계측시간÷일반시간')
    say(f'{"limbs":>6} {"algo":>7} {"base":>9} ' + ' '.join(f'{k:>7}' for k in PHASES) + '    ratio')
    summary, model = [], []
    for n in sorted(set(args.sizes)):
        for a in ALGOS:
            group = {b:[r for r in records if (r['n'],r['algo'],r['base']) == (n,a,b)] for b in BASES}
            for b, rows in group.items():
                frac = [100*st.mean(r['frac'][k] for r in rows) for k in range(6)]
                ratio = st.median(r['profile']/r['normal'] for r in rows)
                normal = st.median(r['normal'] for r in rows)
                summary.append((n,a,b,normal,*frac,ratio))
                say(f'{n:6d} {a:>7} {b:>9} ' + ' '.join(f'{v:7.1f}' for v in frac) + f' {ratio:8.2f}')
            for old,new in zip(group[BASES[0]],group[BASES[1]]):
                if old['seed'] != new['seed'] or (old['leaf_a'],old['leaf_b']) != (new['leaf_a'],new['leaf_b']):
                    raise RuntimeError('베이스 변경 시 말단 구조가 달라짐')
                r = old['leaf_a']/old['leaf_b'] if old['leaf_b'] else float('nan')
                p0 = old['frac'][0]
                pred = 1/(1-p0+p0/r)
                observed = old['normal']/new['normal']
                model.append((n,old['seed'],a,p0,r,pred,observed))
    say('\n3. 암달 모델 예측과 실제 가속률 | 말단별 독립 측정 가중치 사용')
    say(f'{"limbs":>6} {"algo":>7} {"leaf r":>9} {"pred":>9} {"actual":>9}')
    for n in sorted(set(args.sizes)):
        for a in ALGOS:
            rr = [r for r in model if (r[0],r[2]) == (n,a)]
            say(f'{n:6d} {a:>7} ' + ' '.join(f'{st.median(r[k] for r in rr):9.2f}' for k in (4,5,6)))
    say('\n주의: 계측 비율은 타이머 삽입 비용을 포함한 근사값이다. 미분류는 호출/분기/파괴/계측 자체 등을 포함한다.')
    say('말단 독립 측정은 실제 재귀의 캐시·메모리 상태를 재현하지 않으므로 예측 오차도 분석 대상이다.')
    say(f'원본 CSV 및 실행 기록 저장: {dest}')
    prefix = ['limbs','seed','algorithm','basecase']
    write_csv(dest/'times.csv', prefix+['repeat','ns'], raw_time)
    write_csv(dest/'phases.csv', prefix+['kind','repeat','depth','mode_id','phase_id','visits','ns'], raw_ph)
    write_csv(dest/'leaves.csv', prefix+['left_limbs','right_limbs','calls'], raw_leaf)
    write_csv(dest/'counts.csv', prefix+'mul accum carry add sub smallmul smalldiv calls school kara toom depth'.split(),count_rows)
    write_csv(dest/'micro.csv',['left_limbs','right_limbs','seed','basecase','repeat','batch','elapsed_ns','ns_per_call'],raw_micro)
    write_csv(dest/'summary.csv',['limbs','algorithm','basecase','normal_median_ns',*PHASES,'instrumentation_ratio'],summary)
    write_csv(dest/'model.csv',['limbs','seed','algorithm','base_fraction','leaf_speedup','predicted','observed'],model)
    (dest/'console.txt').write_text('\n'.join(log)+'\n',encoding='utf-8')
    def command(*cmd):
        try: return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT).strip()
        except (OSError,subprocess.CalledProcessError): return '확인 불가'
    (dest/'environment.txt').write_text(f'platform={platform.platform()}\nprocessor={platform.processor()}\npython={sys.version}\nargs={args}\ncompiler={command("g++","--version")}\ngit={command("git","rev-parse","HEAD")}\ngit_status={command("git","status","--short")}\n',encoding='utf-8')

if __name__ == '__main__':
    main()
