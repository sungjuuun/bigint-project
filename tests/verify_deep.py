"""심화 실험용 분할/재조합/보간 개선의 독립 정답 검증."""
import argparse, subprocess, sys
from pathlib import Path
from verify import cases
if hasattr(sys,'set_int_max_str_digits'): sys.set_int_max_str_digits(0)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',default='build/bigint');a=p.parse_args();exe=Path(a.exe).resolve()
if not exe.is_file(): exe=exe.with_suffix('.exe')
pairs=cases();data=''.join(f'{x} {y}\n' for x,y in pairs);expected=[str(int(x)*int(y)) for x,y in pairs]
total=0
for base in ('immediate','deferred'):
    for algo in ('kara_split','kara_join','kara_opt','toom_interp','hybrid_kopt'):
        for action,k,t in [('batch',8,24),('batch',32,128),('batchone',8,8)]:
            got=subprocess.check_output([str(exe),action,algo,base,str(k),str(t)],input=data,text=True).splitlines()
            if got!=expected: raise AssertionError((algo,base,action,k,t,'불일치'))
            total+=len(pairs)
        print(f'PASS {algo:12s} {base}: {3*len(pairs)} cases')
print(f'PASS deep total={total}')
