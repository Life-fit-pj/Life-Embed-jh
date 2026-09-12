# DOCKER.md

`Life-Embed-jh`·`Life-Web` 두 저장소를 컨테이너화하는 작업 목록이다.
`DEPLOY.md` Phase 2(담당: Docker) 에 해당한다 — Phase 1(Vercel/Render native),
Phase 3(Supabase/ORM)과 병행하며, 합류 지점은 `render.yaml` 의 `env: python -> docker`
필드 교체 하나다.

작성일 2026-09-08. 티켓 번호는 Jira 발급 후 채운다.

## 지금 착수해도 되는가 — 팀원 작업과의 관계

아래 17개 중 **대기가 필요한 항목은 이제 없다.** 4·5번을 붙잡고 있던 KAN-84·KAN-86 이
`origin/dev-deploy` 에 머지되면서 두 항목은 폐기됐다(2026-09-08 확인). 8번만 임시 확정
상태로 진행한다.

### 이미 갖춰진 선행 조건 (KAN-65 "구조 리팩토링" 에픽 완료분)

Docker화의 최대 전제였던 **두 저장소 분리가 이미 끝나 있다.**

- KAN-69 로 `Life-Web/services/engine.py` 가 `sys.path` 직접 import 대신 `EMBED_API_BASE`
  환경변수 + `httpx` 호출로 바뀌었다 → 두 저장소를 **컨테이너 2개로 나누는 구조가 코드
  차원에서 이미 성립**한다. 사이드바이사이드 폴더 제약이 사라진 상태다.
- KAN-67 / KAN-90 으로 엔트리포인트가 확정됐다 (`app.main:app`, `main:app`).
- DB 는 아직 SQLite 파일 하나라 볼륨 마운트로 충분하다.

httpx 전환 전이었다면 두 저장소를 한 이미지에 합쳐야 했다. 그 고비는 넘어갔다.

### 해소된 대기 항목 — KAN-84 / KAN-86 **완료** (2026-09-08 확인)

두 티켓 모두 `origin/dev-deploy` 에 머지돼 있다.

- `4853aad` "랭체인 벗기고 청킹, 마스킹을 ai폴더로 이사" → KAN-84
- `e75897d` "임베딩 OpenAI 교체 + 재임베딩" → KAN-86

`app/llm.py` 는 사라지고 `app/ai/llm.py`(anthropic SDK)와 `app/ai/embedder.py`(OpenAI
`text-embedding-3-small`)로 갈라졌다. `requirements.txt` 에서 `langchain-anthropic`·
`langchain-huggingface`·`sentence-transformers` 세 줄이 빠지면서 **`torch` 와 CUDA 스택이
의존성 그래프에서 통째로 사라졌다.** 남은 무거운 패키지는 `numpy` 하나뿐이다.

따라서 **4·5번은 폐기한다.** 남은 대기 항목은 8번 하나이고 그것도 임시 확정 후 진행이다.

| 팀원 작업 | 영향받는 항목 | 어떻게 |
|---|---|---|
| ~~**KAN-84** LangChain 의존성 제거~~<br>~~**KAN-86** 임베더를 OpenAI SDK 로 교체~~ | ~~4(CPU 전용 휠), 5(모델 가중치 캐시)~~ | **완료 → 두 항목 폐기** |
| **KAN-79 에픽** Supabase + ORM 전환 | 8(`life.db` 주입 방식) | 볼륨 마운트로 **임시 확정 후 진행.** Phase 3 에서 `DATABASE_URL` 로 교체 |

**보류가 풀린 대신 새로 생긴 일 셋.**

1. **`OPENAI_API_KEY` 가 필수 환경변수로 늘었다.** `app/core/config.py` 가 `ANTHROPIC_API_KEY`
   와 똑같이 **import 시점에 없으면 RuntimeError** 를 낸다 → 9번에 반영.
2. **2번의 파이썬 버전 검증을 새 `requirements.txt` 로 다시 돌려야 한다.** 지금 통과 기록은
   `sentence-transformers` 가 있던 목록 기준이다. 무거운 쪽이 빠졌으니 통과가 더 쉬워지는
   방향이지만 확정 근거는 갱신해 둔다.
3. **`dev_docker` 의 `requirements.txt` 손질이 `dev-deploy` 쪽엔 없다.** 아래 1번 참고 —
   머지할 때 챙기지 않으면 `pydantic` 핀과 `requirements-dev.txt` 분리가 그대로 날아간다.

### 영향이 없는 항목

KAN-87(`app/ai/vector_store.py`), KAN-88(`app/rag/retriever.py`), KAN-89(`app/services/`
재배치)는 전부 `app/` **내부** 모듈 이동이다. Dockerfile 은 `COPY app/` 하고 `app.main:app`
을 띄울 뿐이라 **한 줄도 안 바뀐다.** 이것들 때문에 기다릴 이유는 없다.

## 작업 목록

| # | 제목 | 저장소 | 상태 | 선행 |
|---|---|---|---|---|
| 1 | `requirements.txt` 정리 — 주석 문법 오류 / `pydantic` 핀 / dev 목록 분리 | Embed | **완료 (머지 시 재확인)** | — |
| 2 | 베이스 이미지·파이썬 버전 확정 (`python:3.12-slim` 기준 검증) | 공통 | **완료** | 1 |
| 3 | `Life-Embed-jh/Dockerfile` 작성 — `uvicorn app.main:app --port 8000` | Embed | **완료** | 2, 7 |
| 4 | ~~torch/sentence-transformers 를 CPU 전용 휠로 설치해 이미지 경량화~~ | Embed | **폐기 (KAN-86 완료)** | — |
| 5 | ~~임베딩 모델(e5-small) 가중치를 빌드 단계에 캐시~~ | Embed | **폐기 (KAN-86 완료)** | — |
| 6 | `Life-Web/Dockerfile` 작성 — `uvicorn main:app --port 5000` + 정적 프론트 | Web | **완료 (2026-09-09)** | 2, 7 |
| 7 | 두 저장소에 `.dockerignore` 추가 (빌드 컨텍스트 축소) | 공통 | **완료 (양쪽)** | — (3·6보다 **먼저**) |
| 8 | `data/life.db` 주입 방식 결정 — 이미지 포함 vs 볼륨 마운트 | Embed | 임시 확정 후 진행 | 3 |
| 9 | 환경변수 주입 체계 정리 — `.env` 복사 금지, `env_file`/시크릿 사용 | 공통 | 착수 가능 | 3, 6 |
| 10 | `HEALTHCHECK` 연결 (엔진은 `/admin/health` 가 **이미 있음**) | 공통 | 착수 가능 | 3, 6 |
| 11 | `docker-compose.yml` 작성 — 서비스 2개 + 내부 네트워크 + `EMBED_API_BASE` | 공통 | 착수 가능 | 3, 6, 9 |
| 12 | 개발용 compose override — 소스 bind mount + `--reload` | 공통 | 착수 가능 | 11 |
| 13 | 비루트 사용자 실행 등 컨테이너 보안 기본값 적용 | 공통 | 착수 가능 | 3, 6 |
| 14 | 로그를 stdout 으로 내보내기 (`logs/` 볼륨 정책 확정) | 공통 | 착수 가능 | 11 |
| 15 | UTF-8 로케일 및 한글 경로(`data/LH평면도`) 동작 검증 | Web | **완료 (6번과 함께 검증)** | 6 |
| 16 | `render.yaml` 의 `env: docker` 전환 규격에 맞추기 | 공통 | 착수 가능 | 3, 6 |
| 17 | 이미지 빌드·기동 스모크 테스트 + 실행 문서 작성 | 공통 | 착수 가능 | 11 |

## 각 항목 상세

### 1. `requirements.txt` 정리 — **완료, 단 머지 시 재확인 필요**
`Life-Embed-jh/requirements.txt` 마지막 두 줄이 버전 뒤에 공백+한글 설명을 그대로 달고 있었다.

    anthropic==0.75.0        4단계 — Claude 를 SDK 로 직접
    openai==3.8.0            6단계 — 임베딩

`#` 이 없어 pip 가 요구사항 문자열로 파싱하려다 실패한다. **Docker 빌드가 첫 `pip install`
에서 바로 죽는 지점**이라 가장 먼저 고친다.

`dev_docker` 에서는 두 줄에 `#` 을 **줄 맨 앞에** 붙여 주석으로만 남겨 뒀었다 — 그때는
`app/llm.py` 가 아직 langchain 경유였고, 설치되면 이미지만 커지는 패키지였기 때문이다.
**KAN-84·KAN-86 이 끝나면서 그 임시 조치는 수명을 다했다.** `origin/dev-deploy` 의
`requirements.txt` 는 이미 이렇게 돼 있다 —

    anthropic==1.4.0     # 주석 해제 + 버전 재확정
    openai==3.8.0        # 주석 해제
    (langchain-anthropic / langchain-huggingface / sentence-transformers 세 줄 삭제)

"그 시점에 버전을 다시 정해야 한다"고 적어 뒀던 `anthropic` 은 **`0.75.0` 도, langchain 이
끌고 오던 `0.125.0` 도 아닌 `1.4.0` 으로 확정됐다**(수업 저장소 기준). 이 판단은 끝난
것이니 다시 꺼내지 않는다.

**머지할 때 챙길 것 — 아래 두 가지가 `dev-deploy` 의 `requirements.txt` 에는 없다.**
`dev_docker` 를 합칠 때 되살리지 않으면 조용히 사라진다.

- **`pydantic==2.13.4` 추가.** `app/schemas/` 9개 파일이 직접 import 하는데 명세에 없었다.
  `fastapi` 가 전이 의존성으로 끌고 오지만, 직접 쓰는 패키지를 그렇게 두면 fastapi 버전이
  바뀔 때 조용히 깨진다. `Life-Web` 도 같은 버전으로 핀하고 있어 두 컨테이너가 일치한다.
- **`pytest==9.1.1` 은 `requirements-dev.txt` 로 분리.** 런타임 이미지에 테스트 러너가
  들어갈 이유가 없고(13번 보안 기본값), 2번 멀티스테이지에서 builder 스테이지만 dev 목록을
  설치해 pytest 를 **빌드 게이트**로 쓸 수 있다(테스트 실패 시 이미지가 안 만들어진다).
  새 패키지를 어디에 넣을지는 — `app/` 이 import 하면 `requirements.txt`,
  `tests/` 만 import 하면 `requirements-dev.txt`.

### 2. 베이스 이미지·파이썬 버전 확정 — **검증 완료 (2026-09-08)**
로컬은 3.14 이지만 `numpy==2.5.1`, `sentence-transformers` 등 휠 제공 범위를 고려해
`python:3.12-slim` 을 후보로 잡고 실제로 돌려봤다.

    docker run --rm -v <repo>/requirements.txt:/tmp/req.txt:ro python:3.12-slim \
      sh -c "pip install --dry-run --only-binary=:all: -r /tmp/req.txt"
    -> exit 0

`--only-binary=:all:` 로 소스 배포를 금지했는데도 통과했다 = **모든 패키지가 cp312 휠로
설치된다.** 컴파일이 한 번도 안 일어나므로 **빌더 스테이지가 필요 없고 단일 스테이지로
충분하다.** `python:3.12-slim` 으로 확정한다.

alpine 은 검토하지 않는다 — musl 기반이라 numpy 휠이 안 맞아 소스 빌드로 떨어진다.
`docker desktop` 설치(powershell) : winget install -e --id Docker.DockerDesktop

#### 재검증 완료 (2026-09-08, KAN-86 반영 후)

위 통과 기록은 `sentence-transformers` 가 들어 있던 목록 기준이었다. `dev-deploy` 머지로
`langchain-*` 3종이 빠지고 `anthropic`·`openai` 가 들어오면서 목록이 실제로 바뀌었으므로
같은 명령을 새 `requirements.txt` 로 다시 돌렸다 — **exit 0**.

    Would install (25개, 전부 휠)
      직접 명시 8    numpy 2.5.1        python-dotenv 1.2.2  SQLAlchemy 2.0.52
                     pydantic 2.13.4    fastapi 0.121.2      uvicorn 0.38.0
                     anthropic 1.4.0    openai 3.8.0
      전이 의존성 17  annotated-doc annotated-types anyio click docstring_parser
                     greenlet h11 httpcore2 httpx2 idna jiter pydantic_core
                     sniffio starlette truststore typing-inspection typing_extensions

`greenlet`·`jiter`·`pydantic_core`·`numpy` 처럼 C 확장이 있는 것들도 전부 cp312 manylinux
휠로 잡혔고, 나머지는 py3-none-any 다. **`torch`·CUDA 계열은 한 개도 안 딸려온다**(4번).
**결론 유지 — `python:3.12-slim`, 단일 스테이지.**

#### 이 검사의 성격 — 진단 도구가 아니라 결정의 근거다

`--only-binary=:all:` dry-run 은 오류를 찾는 도구가 아니라 위 두 결정(`python:3.12-slim`,
단일 스테이지)의 **근거를 재확인하는 검사**다. 실패는 "무언가 고장났다"가 아니라
**"결정이 뒤집혔다"**는 뜻이고, 그때는 3번 Dockerfile 을 멀티스테이지로 다시 짜야 한다.

    검사 실패 -> cp312 휠이 없는 패키지가 있다 -> 이미지 안에서 소스 컴파일이 일어난다
             -> gcc·빌드 도구를 이미지에 넣어야 한다 -> 단일 스테이지가 거짓이 된다

**언제 도나 — `requirements.txt` 또는 `FROM` 이 바뀔 때만.** 코드 수정과는 무관하다.
고친 것과 짝이 되는 검사를 돌린다고 외워 두면 기억할 게 없다 —

| 무엇을 고쳤나 | 짝이 되는 검사 |
|---|---|
| `app/**.py` | `py -m pytest tests -q` + AGENTS.md 의 계층 grep 세 줄 |
| `requirements.txt` / `FROM` | 위 휠 가용성 dry-run |

3번이 끝나 Dockerfile 이 생기면 평소에는 `docker build` 만 돌리면 된다. 다만 일반 빌드는
휠이 없으면 **소스에서 컴파일해서라도 성공시켜 버리므로** 이 검사를 완전히 대체하지는
못한다 — 빌드가 갑자기 몇 분씩 느려지면 소스 컴파일이 끼어들었다는 신호이니 그때 이
명령으로 범인을 찾는다.

### 3. `Life-Embed-jh/Dockerfile` — **작성·검증 완료 (2026-09-09)**
- 엔트리포인트는 `app.main:app`, 포트 8000. **저장소 루트를 WORKDIR 로 둬야 한다** —
  `app/` 이 `__init__.py` 없는 네임스페이스 패키지라 루트가 sys.path 에 있어야 `app.*` 가 resolve 된다.
  디렉터리 이름은 `/code` 로 뒀다. `/app` 으로 두면 패키지 이름 `app` 과 겹쳐 읽기 어려워진다.
- `requirements.txt` 만 먼저 COPY → `pip install` → 그 다음 소스 COPY 로 레이어 캐시를 살린다.
- `pipeline/`·`tests/`·`data/`·`.env` 는 COPY 하지 않는다(각각 AGENTS.md, 13번, 8번, 9번).
- `COPY app/` 단위로 담으므로 KAN-87~89 의 내부 모듈 재배치가 끝나도 이 파일은 안 바뀐다.
- `RUN pip install --only-binary=:all:` — 2번의 "단일 스테이지" 결정을 **빌드가 스스로 지키게
  만드는 장치**다. 휠 없는 패키지가 새로 들어오면 몇 분씩 조용히 컴파일하는 대신 즉시 실패한다.

**빌드 실측 (2026-09-09)**

    docker build -t life-embed:dev .
    -> exit 0, 16.9초
       DISK USAGE 386MB / CONTENT SIZE 84.1MB

설치된 25개 패키지에 `torch`·CUDA 계열은 하나도 없다 — KAN-86 의 효과가 그대로 드러난다.
보류했다 폐기한 4번(CPU 전용 휠)이 목표로 하던 1.5GB 보다도 훨씬 작다.

**기동 검증 (2026-09-09)**

    docker run -d -p 8010:8000 --env-file .env -v <repo>/data:/code/data life-embed:dev

    uvicorn 기동          Application startup complete
    GET /openapi.json     200 (라우터 29개 전부 노출)
    GET /admin/health     200 {"ok":true,"regions":427,"members":100}
    GET /regions/../facilities  200 (실제 시설 데이터 반환)

`regions:427` 이 나왔다는 것은 **8번의 볼륨 마운트 방식이 실제로 동작한다**는 뜻이다
(마운트가 실패했다면 빈 DB 로 돌아 `regions:0` 이 나왔을 것이다).

### 4. ~~CPU 전용 휠로 이미지 경량화~~ — **폐기 (KAN-86 완료, 2026-09-08)**
**할 일이 남아 있지 않다.** KAN-86 이 임베딩을 OpenAI API 호출로 바꾸면서
`sentence-transformers` → `torch` 의존 사슬 자체가 `requirements.txt` 에서 사라졌다.
CPU 전용 인덱스에서 받아올 `torch` 가 이제 없다.

기록으로 남기는 당시 실측(2026-09-08, **교체 전** 목록 기준) —

    기본 설치     nvidia-cublas / cudnn-cu13 / nccl-cu13 / cufft / cusolver /
                  cusparse / curand / cuda-runtime / nvshmem-cu13 /
                  cuda-toolkit / cuda-bindings / triton(248MB) ... 전부 딸려옴

    CPU 전용 휠   pip install --index-url https://download.pytorch.org/whl/cpu
                             --extra-index-url https://pypi.org/simple -r requirements.txt

                  site-packages 합계 1.5G (nvidia*/cuda*/triton 잔존 0개)
                  torch 769M / transformers 113M / scipy 109M /
                  sympy 74M / sklearn 49M / numpy 43M

CPU 전용으로 깎아도 1.5GB, 최종 이미지 1.8GB 안팎이라 **Render 저가 티어 적재가 어려운
크기**였다. 이 측정을 "KAN-86 의 우선순위를 올릴 근거로 쓴다"고 적어 뒀는데 실제로 그
방향으로 정리됐다. 지금 남은 무거운 패키지는 `numpy` 하나뿐이고 이미지는 수백 MB 급이 된다.

로컬 임베딩으로 되돌리는 결정이 나오지 않는 한 이 항목은 다시 열지 않는다.

### 5. ~~모델 가중치 빌드 시점 캐시~~ — **폐기 (KAN-86 완료, 2026-09-08)**
**이미지에 구울 가중치가 없다.** `intfloat/multilingual-e5-small`(384차원, `passage:`/`query:`
접두사)이 `text-embedding-3-small`(1536차원, 접두사 없음)로 교체되면서 계산이 OpenAI 쪽에서
돈다. `HF_HOME` 고정도, 런타임 모델 다운로드도 없다.

**대신 넘어간 일 둘.**

- **`OPENAI_API_KEY` 가 9번(환경변수 주입) 대상에 추가된다.** 없으면 `config.py` 가 import
  시점에 RuntimeError 다 — `ANTHROPIC_API_KEY` 와 완전히 같은 취급이다.
- **첫 요청 지연이 사라진 대신 매 임베딩이 외부 API 왕복이 됐다.** 과금·지연 때문에 10번
  헬스체크를 OpenAI 호출까지 확장하지는 않는다. 컨테이너 아웃바운드 네트워크가 막히면
  검색이 죽는다는 점만 17번 스모크 테스트에서 확인한다.

**저장 시와 검색 시 모델이 같아야 한다**는 도메인 규칙(AGENTS.md)상 필요한 전체 재임베딩
(`kb_chunk`·`member_chunk` → 1536차원)은 KAN-86 커밋 `e75897d` 에 `data/life.db` 변경으로
이미 포함돼 있다. 컨테이너 안에서 파이프라인을 돌릴 필요가 없으므로 **`pipeline/` 을 런타임
이미지에서 빼도 된다**(3·7번). 팀원 B 와 확인할 항목이었는데 그대로 해소됐다.

### 6. `Life-Web/Dockerfile` — **작성·검증 완료 (2026-09-09)**
- 엔트리포인트는 `main:app`, 포트 5000. `frontend/` 정적 파일과 `data/LH평면도` 가
  이미지 안에 있어야 `main.py` 의 `app.mount` 두 줄이 뜬다.
- 휠 가용성 dry-run 을 이 저장소 `requirements.txt` 로도 따로 돌렸다 — `pandas 3.0.5`·
  `cryptography 50.0.1` 포함 **26개 전부 cp312 휠, exit 0**. 엔진과 같이 **단일 스테이지**로 간다.
- 정적 파일 COPY 를 `frontend/`·`data/` 두 줄로 한 블록에 모아 뒀다. Phase 1 에서 프론트가
  Vercel 로 빠지면 그 블록만 지운다.
- `PYTHONIOENCODING=utf-8` 을 넣었다 — `main.py` 가 `sys.stdout.encoding.lower()` 를 부르는데
  값이 `None` 이면 그 줄에서 죽는다(15번).

**착수 전에 나온 문제 하나 — 웹도 `life.db` 를 파일로 직접 읽는다.**

KAN-69 로 `services/engine.py` 의 `sys.path` import 는 사라졌지만, **1차 유형(비회원) 경로는
아직 엔진 API 를 거치지 않는다.** `services/typespot.py` 가 `master_dataset_v3` 를 직접 읽는다 —

    DB_PATH = os.environ.get("LIFE_DB_PATH") or _find("life.db")
    # _find 는 형제 폴더 Life-Embed*/data 를 뒤진다. 컨테이너 안에는 형제 폴더가 없다

**`LIFE_DB_PATH` 가 최우선이라 코드 수정 없이 마운트로 해결된다.** 엔진의 `data/` 를 읽기
전용으로 붙이고 그 값을 준다(8번과 같은 임시 확정). 마운트 위치는 **`/code/data` 가 아니어야
한다** — 거기에 붙이면 이미지에 구운 `LH평면도` 가 가려진다. `/engine/data` 로 뒀다.

주의 — `typespot.py` 는 DB 를 못 찾아도 죽지 않고 **빈 결과를 돌려준다**(하드코딩 금지 정책).
8번의 "마운트 실패가 조용히 넘어간다" 와 같은 함정이 여기도 있다. 응답의 `dataStatus` 가
`dbFound`·`regions` 를 실어 주므로 그것으로 확인한다.

> 근본 해결은 1차 유형 채점도 엔진 API 로 돌리는 것이다(웹은 DB 를 모르게). 두 저장소 코드가
> 바뀌므로 Docker 범위 밖이고, **별도 티켓**으로 남긴다. KAN-79(Supabase) 때 같이 정리된다.

**빌드·기동 실측 (2026-09-09)**

    docker build -t life-web:dev .        -> exit 0, 64초
       DISK USAGE 1.29GB / CONTENT SIZE 520MB   (레이어: data 430MB + 의존성 193MB + 베이스)

    docker run -d -p 5010:5000 --env-file .env       -e LIFE_DB_PATH=/engine/data/life.db -v <Life-Embed-jh>/data:/engine/data:ro life-web:dev

    기동 로그        동_좌표.csv 427개 / LH 평면도 281행 로드, Application startup complete
    GET /                        200 (14KB, index.html)
    GET /api/lifetype/keywords   200
    POST /api/lifetype           200, dataStatus {dbFound:true, regions:427, priceLoaded:427}
                                 spots 2곳 반환 (양천구 신정4동 / 중구 신당제5동)
    GET /LH평면도/<한글경로>.png  200 image/png 365,943 bytes
    메모리 (docker stats)        73.99MiB

`regions:427` 이 나왔다는 것이 **엔진 data/ 마운트가 실제로 붙었다는 증거**다(실패했다면 0).

**이미지 크기에 대한 판단.** `CONTENT SIZE 520MB` 중 430MB 가 `data/LH평면도`(262개 PNG)다.
**구동에는 영향이 없다** — 정적 파일은 요청 때 디스크에서 스트리밍되므로 메모리에 안 올라가고,
실제 사용량은 74MB 였다. 비용은 전부 배포 쪽이다(레지스트리 push/pull, 플랫폼 디스크, 콜드
스타트 시 pull 시간). 그래서 **굽는 쪽으로 확정**하되 `COPY data ./data` 한 줄만 지우면 볼륨으로
돌릴 수 있게 뒀다. Render 저가 티어의 이미지·디스크 상한은 16번에서 확인한다.

**아직 안 한 것** — `/api/predict`(2차, 엔진 왕복)는 엔진 컨테이너와 같이 띄워야 해서
11번 compose 이후 17번에서 확인한다. `docker run` 을 Git Bash 에서 칠 때는 `MSYS_NO_PATHCONV=1`
을 앞에 붙여야 한다. 안 붙이면 `-e LIFE_DB_PATH=/engine/data/life.db` 의 값이
`C:/Program Files/Git/engine/data/life.db` 로 바뀌어 마운트를 못 찾는다(실제로 겪었다).

### 7. `.dockerignore` — **양쪽 완료 (2026-09-09)**

**선행 관계를 바로잡는다 — 이 항목은 3·6번보다 먼저 해야 한다.** 원래 "3, 6 이 끝난 뒤"로
적어 뒀는데, 실제로 3번을 빌드해보니 순서가 반대였다.

`.dockerignore` 가 없으면 Docker 는 **저장소 폴더 전체를 데몬으로 전송**한 뒤에야 빌드를
시작한다. Dockerfile 이 `requirements.txt` 와 `app/` 만 COPY 하므로 **이미지 내용물은
같지만**, 전송량이 다르다 —

    .git    3.4GB   (data/ 의 대용량 파일이 Git LFS 로 들어 있다)
    data/   1.0GB   (nemotron.csv 439M, life.db 332M, seoul_persona_full.csv.gz 225M)
    ----------------
    합계    4.4GB   매 빌드마다

개발 중에는 Dockerfile 을 고쳐가며 여러 번 빌드하게 되는데, 매번 4.4GB 를 넘기면 그
자체로 작업이 막힌다. 실제로 `.dockerignore` 를 먼저 넣은 뒤 빌드는 **16.9초**에 끝났다.

제외 대상은 세 갈래다 — **버전 관리**(`.git`), **런타임에 안 쓰는 것**(`data/`, `pipeline/`,
`tests/`, `eval/`, `tools/`, 문서), **비밀**(`.env`). `data/` 는 통째로 제외한다.
`life.db` 는 볼륨으로 마운트하고(8번) 원본 CSV 는 적재 전용이라 런타임과 무관하다.

**`Life-Web` 쪽도 완료했다 (2026-09-09).** 그쪽은 `frontend/` 와 `data/` 가 **이미지에
들어가야 하므로** 제외 목록이 정반대다 — 그대로 복사하면 안 된다. 제외한 것은 `.git`
(**719MB**, 262개 PNG 가 LFS 없이 그대로 tracked 돼 있다), `.env`, 문서, 캐시, 에디터 설정뿐이다.
남긴 것 때문에 빌드 컨텍스트가 여전히 412MB 라 첫 빌드가 64초 걸렸지만, `.git` 719MB 를 뺀
덕에 반복 빌드는 캐시로 넘어간다.

### 8. `data/life.db` 주입 방식 결정 — 임시 확정 후 진행
Git LFS 로 관리되는 42MB(체크아웃에 따라 최대 216MB) 파일이다. 선택지 세 가지 —
(a) 이미지에 COPY, (b) 볼륨/Render Persistent Disk 마운트, (c) 기동 시 다운로드.

**(b) 볼륨 마운트로 임시 확정하고 진행한다.** KAN-79 에픽(Supabase 전환)이 끝나면
`DATABASE_URL` 환경변수를 채우고 볼륨을 빼는 것으로 교체되는데, `app/core/config.py` 가
이미 그 값을 받을 자리를 갖고 있어 **지금 (b) 로 짜두는 게 버리는 작업이 아니다.**
(a) 를 골랐다면 그때 이미지 구조를 다시 짜야 한다.

주의 — `app/core/config.py` 는 DB 파일이 없어도 죽지 않고 경고만 찍은 뒤 빈 DB 로 돈다.
**마운트 실패가 조용히 넘어간다**는 뜻이라 10번 헬스체크에서 표 존재 여부까지 봐야 한다.

### 9. 환경변수 주입 체계
- 엔진: `ANTHROPIC_API_KEY`, **`OPENAI_API_KEY`**(KAN-86 으로 추가됐다. **둘 다 없으면**
  `config.py` 가 import 시점에 RuntimeError — 키 하나만 넣으면 컨테이너가 기동조차 못 한다),
  이후 `DATABASE_URL`(KAN-79). `DATABASE_URL` 은 이미 `config.py` 에 자리가 있고 비어 있으면
  `sqlite:///data/life.db` 로 떨어진다.
- 웹: `ADMIN_TOKEN`, `ADMIN_WRITE_ENABLED`, Google OAuth 클라이언트 ID, `EMBED_API_BASE`.
- `.env` 파일을 이미지에 COPY 하지 않는다(보안 규칙 — AGENTS.md). compose 는 `env_file`,
  Render 는 대시보드 환경변수로 주입하고, 저장소에는 `.env.example` 만 둔다.
- 팀원 작업으로 키가 **늘어나는 방향**이다. 키 이름을 Dockerfile 에 하나씩 박지 말고
  `.env.example` + compose `env_file` 로 통째로 넘겨, 키가 추가돼도 이미지를 안 고치게 한다.

### 10. 헬스체크 — **엔진 쪽은 신규 코드가 필요 없다 (2026-09-09 정정)**

"두 서버 모두 헬스 엔드포인트가 없다"고 적어 뒀는데 **틀렸다.** 3번 기동 검증에서
`/openapi.json` 을 열어보니 엔진에 **`GET /admin/health` 가 이미 있다.**

    GET /admin/health -> 200
    {"ok":true,"regions":427,"members":100,"cache_warm":false,"error":null}

우리가 신규로 만들려던 "DB 연결 + 표 존재 확인"을 이미 하고 있다. `regions:427`·
`members:100` 처럼 **행 수까지 돌려주므로 8번에서 걱정한 "마운트 실패가 조용히 넘어가는"
경우도 이걸로 잡힌다**(빈 DB 면 0 이 나온다). 인증 없이 200 이 떠서 `HEALTHCHECK` 에
그대로 쓸 수 있다.

따라서 엔진 쪽 할 일은 **엔드포인트 신설이 아니라 Dockerfile `HEALTHCHECK` 연결뿐**이다.
남은 판단 두 가지 —

- **경로가 `/admin/` 아래인 게 걸린다.** 지금은 인증이 없지만 나중에 관리자 라우터 전체에
  토큰을 걸면 헬스체크가 401 로 죽는다. `/health` 별칭을 열어 두는 편이 안전한지 결정한다.
- `HEALTHCHECK` 는 이미지 안에서 도는 명령이라 **`curl` 이 필요한데 slim 에는 없다.**
  `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/admin/health')"`
  로 파이썬을 쓰면 패키지를 추가하지 않아도 된다.

`Life-Web` 쪽은 확인 전이다 — 자기 자신 + `EMBED_API_BASE` 연결까지 보는 얕은 체크가
필요한지 6번과 함께 본다. 신규로 만든다면 라우터는 `app/api/` 에 두고 로직은 넣지
않는다(계층 규칙).

### 11. `docker-compose.yml`
- 서비스 2개(`embed`, `web`). `web` 의 `EMBED_API_BASE` 를 `http://embed:8000` 으로 준다 —
  컨테이너 DNS 로 붙으므로 `127.0.0.1` 기본값을 덮어써야 한다.
- **파일 위치를 정해야 한다.** 워크스페이스 루트(`lifefit_ds/`)는 git 저장소가 아니라
  compose 파일이 버전 관리에서 빠진다. 두 저장소 중 한쪽(엔진 쪽 권장, DEPLOY.md 선례)에
  두고 상대 경로로 sibling 을 참조할지, 양쪽에 각자 두고 override 로 합칠지 결정한다.
- 프로덕션 Render 는 서비스별 단독 배포라 compose 는 **로컬 개발용**이 주 용도다.

### 12. 개발용 compose override
`docker-compose.override.yml` 로 소스를 bind mount 하고 `uvicorn --reload` 를 켠다.
이미지 재빌드 없이 코드 수정이 반영돼야 팀원들이 실제로 쓴다 — KAN-79 에픽이 `app/` 아래를
계속 고치는 중이라 이 항목의 실효가 특히 크다. 컨테이너로 옮긴 뒤 팀원들의 개발 속도가
느려지지 않게 하는 것이 Docker화가 받아들여지는 조건이다.

### 13. 컨테이너 보안 기본값
비루트 사용자 생성 후 `USER` 로 전환, 불필요한 패키지 미설치, 읽기 전용 파일시스템 가능
여부 검토(`logs/` 쓰기 때문에 예외 경로가 필요할 수 있음).

### 14. 로그 정책
AGENTS.md 는 "로그는 `logs/` 폴더에 적재"라고 정하고 있는데, 컨테이너에서는 파일 로그가
재기동 시 사라진다. stdout 으로 내보내 플랫폼 로그로 수집하는 쪽으로 바꿀지,
`logs/` 를 볼륨으로 유지할지 정하고 결정을 AGENTS.md 에 반영한다.

### 15. UTF-8 로케일 / 한글 경로 검증 — **완료 (2026-09-09, 6번과 함께)**
`data/LH평면도` 처럼 한글 디렉터리명이 경로에 들어가는데, `python:3.12-slim` 기본 로케일에서
문제없이 돌았다.

    GET /LH평면도/부산울산본부_부산기장(뉴스테이)_A-2BL/..._평면_55A-1210.png
    -> 200 image/png 365,943 bytes

`main.py` 의 stdout UTF-8 재설정도 그대로 통과했고(기동 로그의 ✅ 이모지가 깨지지 않았다),
`sys.stdout.encoding` 이 `None` 이 될 여지는 Dockerfile 의 `ENV PYTHONIOENCODING=utf-8` 로
막아 뒀다 — 그 줄은 `.lower()` 를 바로 부르기 때문에 `None` 이면 서버 import 자체가 죽는다.

### 16. `render.yaml` 의 `env: docker` 대응
DEPLOY.md 대로 Phase 1 은 native python 으로 먼저 올라간다. Docker 완성 후 `env` 필드만
교체하면 되도록 Dockerfile 위치(각 저장소 루트)와 노출 포트(`$PORT` 환경변수 존중)를
Render 규격에 맞춘다. `render.yaml` 은 각 저장소가 자기 것만 들고 있는다.

### 17. 스모크 테스트 + 문서화
`docker compose up` 후 — 엔진 `/health` 200, 웹 `/` 200, 실제 추천 1회 왕복(엔진 LLM 호출 포함)
까지 확인한다. 실행 방법은 이 문서 아래에 절을 추가하고, 루트 `CLAUDE.md` 의 "Running the
service" 절에도 컨테이너 실행법을 한 줄 더한다.

## 팀원 작업과 다시 만나는 지점

| 팀원 작업 | 완료 후 Docker 쪽에서 할 일 |
|---|---|
| ~~**KAN-84 / KAN-86**~~ LangChain 제거, OpenAI 임베더 | **완료 (2026-09-08).** `dev-deploy` 에서 주석 해제·구 ML 의존성 삭제가 끝났다 → **4·5번 폐기**, `OPENAI_API_KEY` 를 9번에 추가, 2번 검증을 새 목록으로 재실행. 머지 시 `pydantic` 핀·`requirements-dev.txt` 유실 주의 |
| **KAN-79 에픽** Supabase + ORM | 8번의 볼륨을 걷고 `DATABASE_URL` 주입으로 교체. 10번 헬스체크의 DB 확인 로직을 Postgres 기준으로 수정 |
| **KAN-87 / 88 / 89** 내부 모듈 재배치 | 없음 — `COPY app/` + `app.main:app` 이라 Dockerfile 불변 |
| **Phase 1** Vercel / Render native | 16번 — `render.yaml` 의 `env: python` 을 `docker` 로 교체. Vercel 로 프론트가 빠지면 6번의 정적 파일 COPY 제거 |

정리하면 Docker 쪽이 팀원 작업을 **기다리는 항목은 이제 없다.** 유일한 대기였던 4·5번은
KAN-86 완료로 폐기됐고, 나머지는 팀원 작업이 끝난 뒤 **값이나 의존성만 갈아끼우는
형태**로 합류한다. 3번(엔진 Dockerfile)부터 바로 이어서 진행한다.

미결 사항 — 팀원 B 가 `life.db` 를 통째로 Supabase 로 옮길지, 벡터 표(`kb_chunk`,
`member_chunk`)만 파일로 남길지에 따라 8번의 볼륨이 완전히 사라질지 일부 남을지가 갈린다
(DEPLOY.md "아직 안 정한 것").
