# 큰 정수 곱셈에서 연산 절감과 오버헤드의 상충 관계

Schoolbook, Karatsuba, Toom-3를 동일한 큰 정수 표현으로 구현하고, 기본 곱셈의 자리올림 처리 변경과 하이브리드 전략의 성능을 연구한다. 현재 v0.4는 기존 실험 1~6과 후속 통제 실험을 재현할 수 있다. 저장된 초기 탐색 수치와 각 컴퓨터의 최종 측정값은 구분한다.

## 채점자용 실행 순서 (처음 내려받은 경우)

아래 준비 및 빌드 절차를 한 번 수행한 뒤 저장소 루트(README.md와 CMakeLists.txt가 보이는 폴더)에서 실행한다. `build` 폴더는 생성물이며 제출용 소스에 포함할 필요가 없다. PowerShell 명령 예시:

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
py tests/verify.py --exe build/bigint.exe
py tests/verify_one_level.py --exe build/bigint.exe
py tests/verify_deep.py --exe build/bigint.exe
```

마지막 세 줄의 통과 건수는 각각 4816, 1376, 10320이다. 실행 파일은 `bigint.exe`(일반 시간), `bigint_profile.exe`(논리 연산), `bigint_phases.exe`(구간 시간) 세 개가 생성된다. 프로그램 동작만 빠르게 확인하려면 `py benchmark/deep_analysis.py --quick`을 실행한다. 점검 모드 결과는 보고서 정규 실험과 섞지 않는다.

정규 실험 재현은 아래 명령으로 가능하다. 이미 보관된 측정 파일을 덮어쓰지 않도록 각 출력 경로를 새 이름으로 지정한다.

```powershell
py benchmark/cost_analysis.py --inputs 5 --reps 15 --leaf-reps 31 --output results/reproduce-cost
py benchmark/threshold_analysis.py --output results/reproduce-threshold
py benchmark/deep_analysis.py --output results/reproduce-deep
```

- 첫 명령: 실험 3~4의 구간 비용, 말단 분포, 암달 모델 (v0.4에서는 말단 시간을 묶음 측정).
- 두 번째: 실험 4~6의 단일 분할과 후보 임계값 탐색 및 독립 평가. 원래 v0.3 탐색 조건을 보존한다.
- 세 번째: 실험 2~6의 반복 강화 및 후속 통제 실험. v0.3 사용자 PC에서 선택한 임계값도 별도 시드로 재검증한다. 후보를 다시 선택하지 않는다.

각 결과 폴더의 `console.txt`가 터미널 요약이며 상세 열과 실험 조건은 아래에 설명한다. Python 외 추가 패키지는 필요 없다. 실행 시간이 기기별로 달라질 수 있으므로 백그라운드 작업을 줄이고 전원 및 성능 모드를 일정하게 유지한다. 동일 시드에서 정답과 논리적 작업량은 동일해야 하며, 시간 자체는 완전히 일치하지 않는다. 반복 분포와 관측 경향을 비교한다. 명령이 인식되지 않으면 VS Code를 재시작하고 PATH와 `g++ --version`, `py --version`을 확인한다. CMake가 다른 컴파일러를 캐시한 경우 새 빌드 폴더를 만들어 동일 명령의 `-B build`를 변경하고 스크립트 실행 파일 인수도 변경한다.

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

정확성 검증이 끝나면 `PASS total=4816`이 출력되어야 한다. v0.1~v0.3의 Windows 설치와 실행은 학생이 완료하였다. v0.4는 새 변경 적용 후 다시 검증한다. 첫 단계에서는 성능 실험을 실행할 필요가 없다.

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

위 수치는 소스 수준의 논리적 작업량이며 기계 명령어 수나 각 연산의 실행 시간 비중은 아니다. 현재 실제 메모리 할당 및 복사량 자체는 별도로 계측하지 않는다. v0.4에서는 복사 제거와 재조합 변경을 통제 변수로 삼는다. 직접 누산 재조합의 반복은 기존 공통 add 계수에 포함하지 않으므로 개선 전후 add를 총 덧셈량으로 비교하지 않는다.

## 정확성

`tests/verify.py`는 Python 내장 정수 곱을 독립 기준으로 사용한다. 0, 1, 연속된 9, 홀수 길이, 불균등 길이, 음수 평가값, 무작위 입력 등을 검증한다. Python의 곱셈은 성능 비교 대상이 아니다.

## 초기 버전의 한계 및 다음 단계

초기 임계값 KT=32, TT=128은 튜닝되지 않은 예시다. 작은 입력에서는 타이머 및 시스템 잡음 영향이 크다. 최종 실험은 임계값 탐색, 독립 평가 시드, 더 세밀한 크기 간격, 메모리 계측 및 필요 시 복사 최적화를 추가한다. 개발 환경 측정값을 사용자 PC의 측정값과 섞지 않는다.

AI 도움을 받은 구현과 연구 과정은 `docs/ai_usage.md`에 기록한다.

## 실험 3: 재귀 비용 분해 (v0.2)

기존 시간 측정(`bigint`) 및 논리적 연산량 계측(`bigint_profile`)과 별도로 `bigint_phases`를 빌드한다. Windows PowerShell에서 프로젝트 최상위 폴더를 열고 다음 명령을 실행한다.

```powershell
cmake --build build
py tests/verify.py --exe build/bigint.exe
py tests/verify.py --exe build/bigint_phases.exe
py benchmark/cost_analysis.py
```

Linux에서는 `py` 대신 `python3`를 사용하고 실행 파일 경로의 `.exe`를 제거한다. 스크립트는 확장자 유무를 자동으로 처리한다. 추가 Python 패키지는 필요 없다. 기본 출력 폴더는 `results/local-cost`이다. 터미널에 나타나는 세 표를 보고서용으로 실제 캡처하고, `console.txt`와 CSV도 보존한다. 표가 너무 넓으면 터미널을 최대화한다. 최종 시간 비교는 이 버전에서 동일 환경으로 다시 측정하며 v0.1 초기 수치와 섞지 않는다.

- `base`: Schoolbook 본체(출력 배열 및 누산 배열 생성 포함).
- `split`: 입력 복사, 부호 제거, 분할.
- `evaluate`: Karatsuba의 합 및 Toom-3 평가점 계산. Toom-3의 0과 무한대는 분할값을 직접 사용한다.
- `interpolate`: 중간 계수 복원(덧셈, 뺄셈, 작은 상수 곱셈·나눗셈 포함).
- `recombine`: 블록 이동 및 합산.
- `residual`: 계측 실행의 총 시간에서 위 구간 시간을 뺀 값. 재귀 호출 관리, 분기, 일부 임시 객체 파괴, 타이머 및 집계 비용 등이 섞여 있으므로 특정 원인 하나의 비용이라고 단정하지 않는다.

각 구간의 시간은 하위 재귀 호출을 포함하지 않아 중복 합산하지 않는다. 일반 실행과 구간 계측 실행을 각각 실행하며, 계측 시간/일반 시간 비율도 제시한다. 타이머 삽입으로 인한 캐시·컴파일 최적화·실행 시간 변화 때문에 계측 비율은 근사값이다. 구간을 분리하기 위해 임시 객체의 생존 범위를 변경했으므로 v0.1과 v0.2의 시간 차이를 계측 효과로만 해석해서는 안 된다. 모든 v0.2 비교는 동일한 새 구현을 사용한다.

말단 길이 분포는 별도 연산량 계측 실행에서 수집한다. 크기가 같은 말단의 호출 수로 독립 Schoolbook 미세 벤치마크의 중앙값을 가중합한다. A/B의 말단 분포와 블록 곱셈 총량이 일치하는지 검사한다. 독립 측정은 실제 재귀 내부의 캐시·부호·메모리 상태를 완전히 재현하지 않는다. 가중 가속률과 계측한 개선 전 기초 비용 비율로 암달 모델의 예측을 계산하고, 일반 실행의 실측 가속률과 비교한다. 모델 오차를 없애기 위한 사후 보정은 하지 않는다.

기본 실험 조건: 재귀 입력 512, 2048, 4096 limb, 입력별 9회 시간/구간 측정, 독립 입력 3쌍, 말단 미세 벤치마크 31회, KT=32, TT=128. 입력 생성 및 출력은 타이머 밖이다. 입력·설정별 중앙값을 먼저 계산하며 구간 비중은 반복별 비중의 평균이다. 일반 시간 및 가속률 요약은 입력별 값의 중앙값이다. `--sizes`, `--inputs`, `--reps`, `--leaf-reps`, `--output`으로 변경 가능하다.

원본: `times.csv`, `phases.csv`, `leaves.csv`, `counts.csv`, `micro.csv`. 핵심 요약: `summary.csv`(비율 열은 %), `model.csv`(base_fraction은 0~1, 나머지는 배율), `console.txt`. `phases.csv`의 mode_id: 0 Schoolbook, 1 Karatsuba, 2 Toom-3. phase_id: 0 기초, 1 분할, 2 평가, 3 보간, 4 재조합. `total` 행의 -1은 구간 없음. `visits`는 구간 실행 횟수이다(Toom-3 평가 구간은 한 노드에서 최대 3회). `environment.txt`에는 실행 설정과 환경을 기록한다. `g++ --version`은 PATH의 컴파일러 정보이며 CMake가 실제 사용한 컴파일러는 `build/CMakeCache.txt`의 `CMAKE_CXX_COMPILER` 항목으로 확인한다.

## 실험 4~6: 단일 분할의 손익 및 전환 임계값 (v0.3)

Windows PowerShell에서 프로젝트 최상위 폴더를 열고 다음 명령을 실행한다.

```powershell
cmake --build build
py tests/verify.py --exe build/bigint.exe
py tests/verify_one_level.py --exe build/bigint.exe
py benchmark/threshold_analysis.py
```

기존 검증 4,816건 및 단일 분할 검증 1,376건을 확인한다. Linux에서는 `python3`를 사용하고 `.exe`를 생략한다. 기존 `results/local-cost`는 덮어쓰지 않는다. 새로운 결과는 `results/local-threshold`에 저장한다. `--quick`은 기능 점검 전용이며 최종 데이터로 사용하지 않는다.

- **단일 분할:** 루트에서 Karatsuba 또는 Toom-3를 정확히 한 번 적용하고 모든 자식은 Schoolbook으로 계산한다(루트 크기 8 초과). 두 베이스에서 각각 같은 베이스의 Schoolbook과 비교한다. 16~4096 limb의 17개 크기, 입력 시드 52001~52003. 가속률 중앙값이 1.05 이상인 관측 크기가 두 개 연속인 첫 구간을 표시한다. 이는 잡음에 민감한 단일 교차점을 피하기 위한 운영상 기준이며 통계적 유의성 또는 수학적 교차점을 보장하지 않는다.
- **임계값 튜닝:** 8,16,32,64,128,256,512,1024,2048 후보. Karatsuba는 KT만, Toom-3는 TT만, Hybrid는 KT≤TT인 모든 후보 쌍을 탐색한다. 256,1024,4096 limb, 시드 53001~53002에서 동일 베이스 Schoolbook 대비 상대 시간의 기하평균을 최소화한다. 입력 크기와 시드에 동일 가중치를 부여한다. 선택 결과는 후보 범위/목적 함수에 종속된다. 경계 후보가 선택되면 범위 확장이 필요할 수 있다.
- **독립 평가:** 128~8192 limb의 7개 크기와 시드 54001~54003으로 고정 KT=32,TT=128 및 튜닝 결과를 비교한다. 입력별 반복 중앙값을 얻고 동일 입력의 시간 비율을 계산한 뒤 입력 간 중앙값을 보고한다. Hybrid는 각 튜닝된 Karatsuba/Toom-3 및 가장 빠른 비혼합 전략과 직접 비교한다. KT=TT인 Hybrid는 중간 Karatsuba 구간이 없는 정책이다. 순수 Karatsuba의 TT와 순수 Toom-3의 KT는 사용되지 않는다.
- **묶음 시간 측정:** `grid` 명령은 같은 프로세스에서 입력을 한 번 생성하고 설정 순서를 고정 시드로 섞는다. 설정별 워밍업 후 묶음 시간을 약 1ms 이상으로 늘리도록 반복 수를 2배씩 조정(최대 32768회)한다. 7개 묶음의 시간/반복 수를 기록한다. 입력 생성과 워밍업, 출력은 제외하지만 결과 객체 파괴와 반복문의 비용은 포함한다. v0.2의 단일 호출 타이밍과 측정 경계가 다르므로 시간 숫자를 그대로 혼합하지 않는다. 동일 묶음에서 같은 입력을 반복 사용하므로 warm-cache 성격을 갖는다.

핵심 파일: `console.txt`(실제 화면과 같은 요약), `one_level.csv`(분할 손익), `tuning.csv`(모든 후보의 상대 시간), `holdout.csv`(독립 평가), `hybrid.csv`(혼합 직접 비교). `raw.csv`는 원본이고 `environment.txt`는 환경과 실행 인자 기록이다. 실행 화면에서 1번 역전 구간, 2번 임계값 선택, 4~5번 독립 평가 요약을 캡처한다. 표 3은 필요할 때 CSV로 확인한다.


## v0.4: 학생 제안에 따른 심화 실험 및 반복 측정

### 실행

```powershell
cmake --build build
py tests/verify_deep.py --exe build/bigint.exe
py benchmark/cost_analysis.py --inputs 5 --reps 15 --leaf-reps 31 --output results/local-cost-v04
py benchmark/deep_analysis.py
```

기존 결과 폴더를 지우지 않는다. `deep_analysis.py`는 기본 `results/local-deep`에 기록하며 기존 파일이 있으면 시간 접미사를 붙여 새 폴더를 만든다. `--inputs`, `--rounds`, `--reps`, `--target-ns`, `--seed`, `--output`으로 변경할 수 있다. 기본은 독립 입력 5개 × 실행 순서 재배치 3라운드 × 7묶음(크기·설정별 총 105묶음, 입력당 21묶음), 묶음 목표 1ms이다. 매 라운드 설정 순서를 고정 시드 난수로 다시 섞는다. 각 묶음의 총 시간/반복 수를 기록하고 동일 입력·라운드의 중앙값으로 비율을 구한 뒤 입력별 중앙값, 입력 간 중앙값 및 Q1/Q3를 산출한다. 사분위 범위는 입력별 변동성의 기술 통계이지 신뢰구간이 아니다. 같은 입력 반복은 독립 입력 105개를 의미하지 않는다. 이상치는 임의 제거하지 않는다. `cost_analysis.py`의 말단 미세 측정은 이제 `rectgrid`로 불균등 길이도 묶어서 측정한다. v0.2의 단일 호출 측정과 시간 경계가 다르다. `micro.csv`는 묶음 횟수 및 총 시간도 보관한다.

### 측정 순서와 해석

0. Schoolbook A/B 크기별 묶음 비교: 타이머 해상도의 영향을 줄인다.
1. 역전 경계: 96~512 limb 세밀 격자. 가속률 중앙값이 1.05 이상인 두 관측 크기가 연속되는 첫 구간 및 Q1이 1.05 이상인 두 크기의 첫 구간을 표시한다. 하한 미확인/미관측은 그대로 둔다. 기준은 탐색 규칙이며 통계적 유의성 검정이 아니다.
2. 병목 통제: 같은 KT=32, TT=128에서 K 분할만(`kara_split`), 재조합만(`kara_join`), 둘 다(`kara_opt`), T 보간만(`toom_interp`) 비교한다. 재귀 호출 수와 기본 블록 곱셈 수가 같은지 검사한다. 구간별 절대 시간은 별도 계측 실행에서 얻으며 타이머 삽입 비용을 포함한다.
3. 혼합 통제: TT=128,256,512 각각에서 KT=TT(K 없음), TT/2, TT/4를 비교하고 K를 개선한 `hybrid_kopt`도 같은 KT/TT에서 측정한다. K가 없는 대조군의 논리 계수가 같은 TT의 순수 T와 동일한지 검사한다. 실제 K 호출 수가 0이면 설정상 K가 있어도 그 입력의 재귀 트리는 K를 사용하지 않는다. 주요 조건의 512,4096 limb에서 별도 구간 계측으로 기초비용 절감과 비기초비용 증가를 비교한다. 다른 조건은 CSV에 기록한다.
4. 독립 재검증: 128~8192 limb, 사용자 v0.3에서 선택된 A의 K=256/T=256/H=(128,128), B의 K=512/T=512/H=(256,512)와 고정 KT=32/TT=128을 새로운 입력에서 비교한다. 이는 이전 후보 선택의 재검증이지 전역 최적값을 새로 찾는 실험은 아니다.

### 개선의 수학적 근거

K 분할: 기존에는 전체 입력 두 개를 복사한 후 부분 배열을 만들었다. 변경은 필요한 부분 배열만 만들어 부호를 정리한다. K 재조합: z0 + z1*B^h + z2*B^(2h)를 shift 객체와 일반 덧셈 대신 한 결과 배열의 오프셋에 누산한다. z1=a0*b1+a1*b0≥0이며 다른 계수도 비음수다. 각 누산에서 최대값은 2(B-1)+1이고 carry≤1이다. 두 변경 모두 하위 곱셈 횟수/점근 복잡도는 바꾸지 않는다.

T 보간: C(x)=c0+c1*x+c2*x²+c3*x³+c4*x⁴. odd=(C(1)-C(-1))/2=c1+c3. 따라서 c2=C(1)-odd-c0-c4이고 기존 c2=(C(1)+C(-1))/2-c0-c4와 동일하다. 이미 필요한 odd를 재사용하여 정확한 큰 정수 /2를 한 번 줄이고 덧셈/뺄셈 조합을 바꾼다. 실제 시간 개선은 측정 대상이다.

K 삽입의 손익: P0=B0+O0(K 없는 정책), P1=B1+O1(K 삽입 정책)로 두면 P1<P0 iff B0-B1>O1-O0. B는 말단 곱셈 총 시간, O는 나머지 비용이다. 계측된 시간으로 차이를 추정하고 일반 실행 가속률과 대조한다. 분할·재조합 개선이 O1을 줄여 K 삽입의 가치가 달라지는지 검증한다. 기초 곱셈 시간과 비기초 시간 각각의 중앙값 차이는 기술적 근사이며 독립 측정의 절대 시간과 동일하지 않다.

### 출력 파일 읽는 법

`console.txt`만 먼저 읽으면 된다. `comparisons.csv`: ref/test 시간 비율(1보다 크면 변경 방식 우세), 입력별 중앙값의 중앙값/Q1/Q3/min/max, test가 우세했던 입력 수. `times_summary.csv`: 설정별 호출 시간 ns의 기술 통계. `policy.csv`: K 삽입 전후 비율, 개선 K 비율, 실제 K 호출 중앙값과 블록 곱셈 감소율. `policy_phases.csv`: 지정 주요 조건의 계측 기초/비기초 시간 및 손익. `phase_summary.csv`: 병목별 구간 시간과 계측 총 시간/비기초 시간. 각 열을 독립 중앙값으로 요약하므로 합이 총 시간과 정확히 같지 않을 수 있다. `holdout.csv`: 기존 선택 전략의 독립 평가 ms와 가속률. `raw.csv`, `counts.csv`, `phases.csv`는 원본. `environment.txt`: 실행 인자, Git 상태/해시, 컴파일러, 바이너리 SHA256 및 CMake 설정. 실제 측정 화면은 표 0~4의 핵심 결과를 캡처하여 보고서에 삽입한다. `--quick` 결과는 실행 검증에만 사용한다.
