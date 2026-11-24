"""Python 정수 곱셈을 이용한 독립 검증. Python 3.10 이상 권장."""
import argparse
import random
import subprocess
import sys
from pathlib import Path

if hasattr(sys, 'set_int_max_str_digits'):
    sys.set_int_max_str_digits(0)

def cases():
    r = random.Random(20261124)
    pairs = [('0','0'),('0','9999'),('1','99999999'),('0000123','00000456'),('9999','9999'),('10000','10000')]
    def num(n):
        return str(r.randrange(1,10)) + ''.join(str(r.randrange(10)) for _ in range(n-1))
    for n in [1,2,7,8,9,15,16,17,23,24,25,31,32,33,63,64,65,127,128,129,255,256,257,513]:
        pairs.extend([('9'*(4*n),'9'*(4*n)), ('1'+'0'*(4*n-1),num(4*n)), (num(4*n),num(4*n)),(num(4*n),num(max(1,2*n-1)))])
    # x=-1 에서 한쪽 평가값만 음수인 사례 (3블록 분할을 강제).
    h=5; B=10**(4*h)
    pairs.extend([(str(B*(B-1)+1),str((B-1)*B**2+1)),(str((B-1)*B**2+1),str(B*(B-1)+1))])
    for _ in range(240):
        a=r.randint(1,850);b=r.randint(1,850);pairs.append((num(a),num(b)))
    return pairs

def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',default='build/bigint');args=p.parse_args()
    exe=str(Path(args.exe).resolve());pairs=cases();data=''.join(f'{a} {b}\n' for a,b in pairs);expected=[str(int(a)*int(b)) for a,b in pairs]
    total=0
    for base in ('immediate','deferred'):
        for algo,kt,tt in [('school',8,8),('kara',8,8),('kara',32,128),('toom',8,8),('toom',32,128),('hybrid',8,24),('hybrid',32,128)]:
            cmd=[exe,'batch',algo,base,str(kt),str(tt)]
            out=subprocess.run(cmd,input=data,text=True,capture_output=True,check=True).stdout.splitlines()
            if len(out)!=len(expected):raise AssertionError((cmd,len(out),len(expected)))
            for i,(got,want) in enumerate(zip(out,expected)):
                if got!=want:raise AssertionError((cmd,i,pairs[i],got,want))
            total+=len(pairs);print(f'PASS {algo:6} {base:9} {kt:3}/{tt:3}: {len(pairs)} cases')
    print(f'PASS total={total}')
if __name__=='__main__':main()
