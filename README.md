# 큰 정수 곱셈에서 연산 절감과 오버헤드의 상충 관계

Schoolbook, Karatsuba, Toom-3를 동일한 큰 정수 표현으로 구현하고, 기본 곱셈의 자리올림 처리 변경과 하이브리드 전략의 성능을 연구한다. 현재 버전은 **정확성 검증 및 초기 탐색용**이며 최적 임계값이나 최종 실험 결론은 아직 확정하지 않았다.

## 준비 및 빌드 (Windows + VS Code)

1. ZIP을 일반 폴더에 완전히 압축 해제한다. VS Code에서 `파일 > 폴더 열기`로 `bigint-project` 폴더를 열고, 직접 검토한 이 프로젝트의 폴더를 신뢰한다.
2. [Git for Windows](https://git-scm.com/download/win), [Python](https://www.python.org/downloads/windows/), [MSYS2](https://www.msys2.org/)를 설치한다. Python 3.10 이상을 사용한다.
3. MSYS2 UCRT64 터미널에서 아래 명령으로 GCC, CMake, Ninja를 설치한다. 기본 설치 경로라면 Windows 사용자 PATH에 `C:\msys64\ucrt64\bin`을 추가한다. VS Code를 완전히 종료하고 다시 연다.

```bash
pacman -Syu
pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja
```

업데이트 중 터미널을 닫으라고 안내되면 닫은 뒤 UCRT64를 다시 열어 `pacman -Syu`를 재실행한다. 다음 명령들은 VS Code의 PowerShell 터미널에서 저장소 루트를 기준으로 실행한다.

```powershell
git --version
g++ --version
cmake --version
ninja --version
py --version
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
py tests/verify.py --exe build/bigint.exe
```

정확성 검증이 끝나면 `PASS total=4816`이 출력되어야 한다. Windows 설치와 실행은 사용자 컴퓨터에서 별도로 확인해야 한다. 첫 단계에서는 성능 실험을 실행할 필요가 없다.

초기 성능 실험이 필요할 때만 다음 명령을 실행한다.

```powershell
py benchmark/pilot.py --exe build/bigint.exe --profile build/bigint_profile.exe --output results/local-pilot
```

Linux/WSL에서 C++17 컴파일러와 CMake, Python 3.10 이상을 설치한 경우 다음 명령으로 실행한다.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
python3 tests/verify.py
python3 benchmark/pilot.py --output results/local-pilot
```

## 직접 실행 (Linux/WSL 예시)

Windows PowerShell에서는 `./build/bigint.exe`와 `./build/bigint_profile.exe`를 사용하고, 입력 문자열은 큰따옴표로 감싸도 된다.

```bash
echo '123456789 987654321' | ./build/bigint batch kara immediate 32 128
./build/bigint bench toom immediate 32 128 512 2026112500 5
./build/bigint_profile bench toom immediate 32 128 512 2026112500 1
```

- 알고리즘: `school`, `kara`, `toom`, `hybrid`.
- 베이스케이스: `immediate`(매 내부 곱셈에서 자리올림), `deferred`(마지막 일괄 자리올림).
- 인수 `KT`, `TT`: 각각 Karatsuba와 Toom-3의 종료 또는 하이브리드 전환 임계값. 단위는 limb. 최소 8, hybrid에서는 KT ≤ TT.
- `batch`: 공백으로 구분된 비음수 십진 정수 쌍을 표준 입력으로 받아 곱을 한 줄씩 출력한다.
- `bench`: N(각 입력의 limb 수), SEED, REPS 순서. 일반 실행 파일은 반복별 나노초, 계측 파일은 연산량 CSV 한 줄을 반환한다.

## 공통 구현과 공정성

기수 10000, little-endian `uint32_t` 배열과 내부 부호를 사용한다. 기본 곱셈 중간값은 `uint64_t`로 저장한다. Toom-3는 0, 1, -1, 2, 무한대에서 평가하고 정확한 정수 나눗셈으로 보간한다. 모든 전략은 같은 자료구조와 덧셈, 뺄셈, 분할, 이동을 사용한다. `kara`는 Karatsuba→Schoolbook, `toom`은 Toom-3→Schoolbook, `hybrid`는 Toom-3→Karatsuba→Schoolbook이다. 매 호출에서 최대 입력 limb 수로 분기한다.

## 초기 실험 재현

`benchmark/pilot.py`는 8~4096 limb의 2배 간격, 크기별 3개 입력 시드, 입력당 5회 반복, 8개 전략을 비교한다. 전략 실행 순서는 고정 난수 시드로 섞는다. 동일 크기와 시드에서는 동일한 입력을 사용한다. 입력 생성, 워밍업 1회, 결과 출력은 시간 측정에서 제외한다. 결과 객체의 최종 파괴도 타이머 밖이며 내부 임시 객체의 생성/파괴는 포함한다. 계측 실행은 시간 측정과 별도 실행 파일로 분리한다. 초기 탐색은 반복별 데이터를 보존하며 이상치를 제거하지 않는다.

출력: `times.csv`(원본 시간), `counts.csv`(입력별 계측), `summary.csv`(중앙값·평균·표준편차), `environment.txt`(실행 환경 일부). `results/pilot`은 개발 환경에서 얻은 초기 데이터로, 최종 보고서에는 사용자 컴퓨터에서 같은 조건으로 다시 측정한 결과를 사용한다.

### 계측 열 정의

- `mul`: 두 limb의 곱셈 반복 횟수. 작은 상수 곱셈은 제외.
- `accum`: Schoolbook 곱셈 결과 누산 반복 횟수.
- `carry`: Schoolbook 자리올림 계산 반복 횟수 (실제로 0이 아닌 carry의 개수는 아님).
- `add`, `sub`: 공통 큰 정수 덧셈·뺄셈 내부 limb 반복 횟수. 크기 비교, 복사 등은 제외.
- `smallmul`, `smalldiv`: 상수 곱셈, 정확한 나눗셈 내부 limb 반복 횟수. 상수 곱셈의 추가 carry 배출은 제외.
- `calls`: 0 처리 포함 전체 multiply 호출, `school`, `kara`, `toom`: 각 알고리즘 본체 실행 횟수, `depth`: 루트 1 기준 최대 호출 깊이.

위 수치는 소스 수준의 논리적 작업량이며 기계 명령어 수나 각 연산의 실행 시간 비중은 아니다. 현재 메모리 할당 및 복사량은 별도로 계측하지 않는다.

## 정확성

`tests/verify.py`는 Python 내장 정수 곱을 독립 기준으로 사용한다. 0, 1, 연속된 9, 홀수 길이, 불균등 길이, 음수 평가값, 무작위 입력 등을 검증한다. Python의 곱셈은 성능 비교 대상이 아니다.

## 현재 한계 및 다음 단계

초기 임계값 KT=32, TT=128은 튜닝되지 않은 예시다. 작은 입력에서는 타이머 및 시스템 잡음 영향이 크다. 최종 실험은 임계값 탐색, 독립 평가 시드, 더 세밀한 크기 간격, 메모리 계측 및 필요 시 복사 최적화를 추가한다. 개발 환경 측정값을 사용자 PC의 측정값과 섞지 않는다.

AI 도움을 받은 구현과 연구 과정은 `docs/ai_usage.md`에 기록한다.
