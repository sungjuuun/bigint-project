"""한 단계 분할 모드의 독립 정답 검증."""
import argparse, subprocess, sys
from pathlib import Path
from verify import cases
if hasattr(sys,'set_int_max_str_digits'): sys.set_int_max_str_digits(0)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',default='build/bigint');a=p.parse_args();exe=Path(a.exe).resolve()
if not exe.is_file(): exe=exe.with_suffix('.exe')
pairs=cases();data=''.join(f'{x} {y}\n' for x,y in pairs);expected=[str(int(x)*int(y)) for x,y in pairs]
for base in ('immediate','deferred'):
    for algo in ('kara','toom'):
        got=subprocess.check_output([str(exe),'batchone',algo,base,'8','8'],input=data,text=True).splitlines()
        if got!=expected: raise AssertionError((algo,base,'불일치'))
        print(f'PASS one-level {algo} {base}: {len(pairs)} cases')
print(f'PASS one-level total={4*len(pairs)}')
