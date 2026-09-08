# DOCKER.md

`Life-Embed-jh`·`Life-Web` 두 저장소를 컨테이너화하는 작업 목록이다.
`DEPLOY.md` Phase 2(담당: Docker) 에 해당한다 — Phase 1(Vercel/Render native),
Phase 3(Supabase/ORM)과 병행하며, 합류 지점은 `render.yaml` 의 `env: python -> docker`
필드 교체 하나다.

작성일 2026-09-08. 티켓 번호는 Jira 발급 후 채운다.

## 지금 착수해도 되는가 — 팀원 작업과의 관계

아래 17개 중 13개는 지금 바로 진행할 수 있고, 대기가 필요한 건 2개뿐이다.

### 이미 갖춰진 선행 조건 (KAN-65 "구조 리팩토링" 에픽 완료분)

Docker화의 최대 전제였던 **두 저장소 분리가 이미 끝나 있다.**

- KAN-69 로 `Life-Web/services/engine.py` 가 `sys.path` 직접 import 대신 `EMBED_API_BASE`
  환경변수 + `httpx` 호출로 바뀌었다 → 두 저장소를 **컨테이너 2개로 나누는 구조가 코드
  차원에서 이미 성립**한다. 사이드바이사이드 폴더 제약이 사라진 상태다.
- KAN-67 / KAN-90 으로 엔트리포인트가 확정됐다 (`app.main:app`, `main:app`).
- DB 는 아직 SQLite 파일 하나라 볼륨 마운트로 충분하다.

httpx 전환 전이었다면 두 저장소를 한 이미지에 합쳐야 했다. 그 고비는 넘어갔다.

### 대기가 필요한 항목

| 팀원 작업 | 영향받는 항목 | 어떻게 |
|---|---|---|
| **KAN-84** LangChain 의존성 제거<br>**KAN-86** 임베더를 OpenAI SDK 로 교체 | 4(CPU 전용 휠), 5(모델 가중치 캐시) | **보류.** 끝나면 두 티켓이 **사라진다** |
| **KAN-79 에픽** Supabase + ORM 전환 | 8(`life.db` 주입 방식) | 볼륨 마운트로 **임시 확정 후 진행.** Phase 3 에서 `DATABASE_URL` 로 교체 |

`app/llm.py` 는 아직 `langchain_anthropic` + `HuggingFaceEmbeddings` 를 쓴다. 즉 지금
빌드하면 `sentence-transformers` → `torch` 가 딸려와 이미지가 2~3GB 대가 된다. 그런데
KAN-86 이 끝나 임베딩이 OpenAI API 호출로 바뀌면 **torch 가 통째로 빠져 수백 MB 로 줄고**,
4·5 번은 필요 자체가 없어진다. **이 두 항목에 지금 공들이지 않는다.**

### 영향이 없는 항목

KAN-87(`app/ai/vector_store.py`), KAN-88(`app/rag/retriever.py`), KAN-89(`app/services/`
재배치)는 전부 `app/` **내부** 모듈 이동이다. Dockerfile 은 `COPY app/` 하고 `app.main:app`
을 띄울 뿐이라 **한 줄도 안 바뀐다.** 이것들 때문에 기다릴 이유는 없다.

## 작업 목록

| # | 제목 | 저장소 | 상태 | 선행 |
|---|---|---|---|---|
| 1 | `requirements.txt` 의 인라인 주석 문법 오류 수정 (pip 파싱 실패) | Embed | 착수 가능 | — |
| 2 | 베이스 이미지·파이썬 버전 확정 (`python:3.12-slim` 기준 검증) | 공통 | **완료** | 1 |
| 3 | `Life-Embed-jh/Dockerfile` 작성 — `uvicorn app.main:app --port 8000` | Embed | 착수 가능 | 2 |
| 4 | torch/sentence-transformers 를 CPU 전용 휠로 설치해 이미지 경량화 | Embed | **보류 (KAN-86)** | 3 |
| 5 | 임베딩 모델(e5-small) 가중치를 빌드 단계에 캐시 (런타임 다운로드 제거) | Embed | **보류 (KAN-86)** | 3 |
| 6 | `Life-Web/Dockerfile` 작성 — `uvicorn main:app --port 5000` + 정적 프론트 | Web | 착수 가능 | 2 |
| 7 | 두 저장소에 `.dockerignore` 추가 (빌드 컨텍스트 축소) | 공통 | 착수 가능 | 3, 6 |
| 8 | `data/life.db` 주입 방식 결정 — 이미지 포함 vs 볼륨 마운트 | Embed | 임시 확정 후 진행 | 3 |
| 9 | 환경변수 주입 체계 정리 — `.env` 복사 금지, `env_file`/시크릿 사용 | 공통 | 착수 가능 | 3, 6 |
| 10 | `/health` 엔드포인트 신설 + Dockerfile `HEALTHCHECK` 연결 | 공통 | 착수 가능 | 3, 6 |
| 11 | `docker-compose.yml` 작성 — 서비스 2개 + 내부 네트워크 + `EMBED_API_BASE` | 공통 | 착수 가능 | 3, 6, 9 |
| 12 | 개발용 compose override — 소스 bind mount + `--reload` | 공통 | 착수 가능 | 11 |
| 13 | 비루트 사용자 실행 등 컨테이너 보안 기본값 적용 | 공통 | 착수 가능 | 3, 6 |
| 14 | 로그를 stdout 으로 내보내기 (`logs/` 볼륨 정책 확정) | 공통 | 착수 가능 | 11 |
| 15 | UTF-8 로케일 및 한글 경로(`data/LH평면도`) 동작 검증 | Web | 착수 가능 | 6 |
| 16 | `render.yaml` 의 `env: docker` 전환 규격에 맞추기 | 공통 | 착수 가능 | 3, 6 |
| 17 | 이미지 빌드·기동 스모크 테스트 + 실행 문서 작성 | 공통 | 착수 가능 | 11 |

## 각 항목 상세

### 1. `requirements.txt` 인라인 주석 문법 오류 수정
`Life-Embed-jh/requirements.txt` 마지막 두 줄이 버전 뒤에 공백+한글 설명을 그대로 달고 있다.

    anthropic==0.75.0        4단계 — Claude 를 SDK 로 직접
    openai==3.8.0            6단계 — 임베딩

`#` 이 없어 pip 가 요구사항 문자열로 파싱하려다 실패한다. **Docker 빌드가 첫 `pip install`
에서 바로 죽는 지점**이라 가장 먼저 고친다.

두 줄은 KAN-84·KAN-86 준비로 미리 넣어둔 것이므로 **지우지 말고 `#` 만 붙여 주석으로
남긴다** — 아직 `app/llm.py` 가 쓰지 않는 패키지라 설치되면 이미지만 커진다. 두 티켓이
끝나면 주석을 풀고, 그때 `langchain-anthropic`·`langchain-huggingface`·
`sentence-transformers` 를 대신 걷어낸다.

**주의 — 주석 처리해도 `anthropic` 은 설치된다.** `langchain-anthropic` 이 의존성으로
끌고 오기 때문인데, 그것도 고정하려던 `0.75.0` 이 아니라 **`0.125.0`** 이 들어온다
(2번 검증에서 확인). 지금은 코드가 langchain 경유로만 부르니 문제가 없지만, KAN-84 에서
langchain 을 걷어내며 주석을 풀 때 **`0.75.0` 을 그대로 되살리면 그 사이 바뀐 SDK API 와
어긋날 수 있다** — 그 시점에 버전을 다시 정해야 한다.

`#` 는 **줄 맨 앞**에 붙여야 한다. `anthropic==0.75.0        # 4단계` 처럼 버전 뒤에 붙이면
pip 가 인라인 주석으로 읽어 **패키지는 그대로 설치된다** — 파싱 오류만 사라지고 이미지가
커지는 건 그대로다.

같이 정리한 것 두 가지.

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

alpine 은 검토하지 않는다 — musl 기반이라 numpy·torch 휠이 안 맞아 소스 빌드로 떨어진다.
`docker desktop` 설치(powershell) : winget install -e --id Docker.DockerDesktop

### 3. `Life-Embed-jh/Dockerfile`
- 엔트리포인트는 `app.main:app`, 포트 8000. **저장소 루트를 WORKDIR 로 둬야 한다** —
  `app/` 이 `__init__.py` 없는 네임스페이스 패키지라 루트가 sys.path 에 있어야 `app.*` 가 resolve 된다.
- `requirements.txt` 만 먼저 COPY → `pip install` → 그 다음 소스 COPY 로 레이어 캐시를 살린다.
- `pipeline/` 은 배포에 따라가지 않는다(AGENTS.md) — 런타임 스테이지에서 제외할지 7번과 함께 정한다.
- `COPY app/` 단위로 담으므로 KAN-87~89 의 내부 모듈 재배치가 끝나도 이 파일은 안 바뀐다.

### 4. CPU 전용 휠로 이미지 경량화 — 보류 (KAN-86 대기) / **측정은 완료**
기본 설치로는 `sentence-transformers` → `torch 2.14.0` 이 **NVIDIA CUDA 스택을 통째로**
끌고 온다. GPU 가 없는 서버에 올릴 건데도 아래가 전부 들어온다 —

    nvidia-cublas, nvidia-cudnn-cu13, nvidia-nccl-cu13, nvidia-cufft,
    nvidia-cusolver, nvidia-cusparse, nvidia-curand, nvidia-cuda-runtime,
    nvidia-nvshmem-cu13, cuda-toolkit, cuda-bindings, triton(248MB) ...

torch 를 CPU 전용 인덱스에서 받으면 이게 전부 사라진다. **실측(2026-09-08)** —

    pip install --index-url https://download.pytorch.org/whl/cpu \
                --extra-index-url https://pypi.org/simple -r requirements.txt

    site-packages 합계   1.5G   (nvidia*/cuda*/triton 잔존 0개)
    torch                769M
    transformers         113M
    scipy                109M
    sympy                 74M
    sklearn               49M
    numpy                 43M

CPU 전용으로도 **1.5GB** 다. 베이스 이미지와 레이어를 더하면 최종 이미지는 1.8GB 안팎이
된다. 기본 설치본은 측정하지 않았지만 위 CUDA 패키지 목록으로 보아 그 3배 이상이다.
DEPLOY.md 가 "이미지가 커질 수 있다"고 지목한 수준을 넘어 **Render 저가 티어 적재가
어려운 크기**다.

다만 **KAN-86(임베더를 OpenAI SDK 기반으로 교체)이 끝나면 torch·transformers·
sentence-transformers 가 의존성에서 통째로 빠지므로 이 티켓은 폐기된다.** 위 목록에서
그 셋과 부속(sympy, networkx, safetensors, tokenizers)을 걷어내면 남는 건 numpy·scipy
정도이고 이미지는 수백 MB 급이 된다.

**따라서 이 티켓은 KAN-86 의 우선순위를 올릴 근거로 쓴다.** KAN-86 이 크게 지연되거나
로컬 임베딩을 유지하는 쪽으로 결정이 뒤집힐 때만 착수한다 — 그때는 위 명령 두 줄을
Dockerfile 에 옮기면 끝이라 작업량 자체는 작다.

### 5. 모델 가중치 빌드 시점 캐시 — **보류 (KAN-86 대기)**
`intfloat/multilingual-e5-small` 을 런타임에 처음 임베딩할 때 HuggingFace 에서 내려받으면
컨테이너 첫 요청이 느려지고, 네트워크가 막힌 환경에서는 아예 실패한다.
빌드 단계에서 모델을 한 번 로드해 캐시를 이미지에 굽고 `HF_HOME` 을 그 경로로 고정한다.

4번과 같은 이유로 보류한다 — 임베딩이 API 호출로 바뀌면 이미지에 구울 가중치가 없고,
대신 **임베딩 API 키가 9번(환경변수 주입) 대상에 추가**된다.
**저장 시와 검색 시 모델이 같아야 한다**는 도메인 규칙(AGENTS.md)상 KAN-86 은
`kb_chunk`·`member_chunk` 전체 재임베딩을 수반한다 — 이 작업이 컨테이너 안에서 도는지
(`pipeline/` 을 런타임 이미지에서 뺄지, 3번과 연결) 팀원 B 와 확인한다.

### 6. `Life-Web/Dockerfile`
- 엔트리포인트는 `main:app`, 포트 5000. `frontend/` 정적 파일과 `data/LH평면도` 가
  이미지 안에 있어야 `main.py` 의 `app.mount` 두 줄이 뜬다.
- 의존성이 가벼워(`fastapi`, `httpx`, `pandas`) 엔진 쪽과 달리 단일 스테이지로 충분한지 판단한다.
- 프론트를 Vercel 로 옮기는 Phase 1 이 끝나면 정적 서빙이 빠질 수 있으므로,
  정적 파일 COPY 를 한 곳에 모아 나중에 제거하기 쉽게 둔다.

### 7. `.dockerignore`
`.git`(LFS 포함), `__pycache__`, `data/*.csv`, `*.csv.gz`, `.env`, `tests/`, 문서 `.md`,
워크스페이스 루트의 `.mp4`/`.pdf` 를 제외한다. 특히 `data/` 아래 원본 CSV 는
DB 재적재용이라 런타임 이미지에 들어갈 이유가 없다.

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
- 엔진: `ANTHROPIC_API_KEY`(없으면 `config.py` 가 import 시점에 RuntimeError),
  이후 `DATABASE_URL`(KAN-79), 임베딩 API 키(KAN-86).
- 웹: `ADMIN_TOKEN`, `ADMIN_WRITE_ENABLED`, Google OAuth 클라이언트 ID, `EMBED_API_BASE`.
- `.env` 파일을 이미지에 COPY 하지 않는다(보안 규칙 — AGENTS.md). compose 는 `env_file`,
  Render 는 대시보드 환경변수로 주입하고, 저장소에는 `.env.example` 만 둔다.
- 팀원 작업으로 키가 **늘어나는 방향**이다. 키 이름을 Dockerfile 에 하나씩 박지 말고
  `.env.example` + compose `env_file` 로 통째로 넘겨, 키가 추가돼도 이미지를 안 고치게 한다.

### 10. `/health` 엔드포인트 + HEALTHCHECK
지금 두 서버 모두 헬스 엔드포인트가 없다 — 신규 코드가 필요하다. 엔진은 DB 연결과 표 존재까지,
웹은 자기 자신 + `EMBED_API_BASE` 연결까지 확인하는 얕은 체크를 둔다.
compose 의 `depends_on: condition: service_healthy` 와 Render 헬스체크가 이 값을 쓴다.
라우터는 `app/api/` 에 두고 로직은 넣지 않는다(계층 규칙) — KAN-90 으로 이미 자리가 잡혀 있다.

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

### 15. UTF-8 로케일 / 한글 경로 검증
`data/LH평면도` 처럼 한글 디렉터리명이 마운트 경로에 들어간다. slim 이미지 기본 로케일에서
`StaticFiles` 마운트와 파일 응답이 정상인지 확인한다. `main.py` 의 stdout UTF-8 재설정은
Windows 콘솔용이라 리눅스 컨테이너에서는 무해하지만, `sys.stdout.encoding` 이 None 인
환경에서 죽지 않는지만 확인한다.

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
| **KAN-84 / KAN-86** LangChain 제거, OpenAI 임베더 | 1번의 주석 해제 + 구 ML 의존성 삭제 후 재빌드. **4·5번 티켓 폐기.** 임베딩 API 키를 9번에 추가 |
| **KAN-79 에픽** Supabase + ORM | 8번의 볼륨을 걷고 `DATABASE_URL` 주입으로 교체. 10번 헬스체크의 DB 확인 로직을 Postgres 기준으로 수정 |
| **KAN-87 / 88 / 89** 내부 모듈 재배치 | 없음 — `COPY app/` + `app.main:app` 이라 Dockerfile 불변 |
| **Phase 1** Vercel / Render native | 16번 — `render.yaml` 의 `env: python` 을 `docker` 로 교체. Vercel 로 프론트가 빠지면 6번의 정적 파일 COPY 제거 |

정리하면 Docker 쪽이 팀원 작업을 **기다려야 하는 건 4·5번뿐**이고, 나머지는 팀원 작업이
끝난 뒤 **값이나 의존성만 갈아끼우는 형태**로 합류한다. 지금 착수해도 다시 만드는 작업은
생기지 않는다.

미결 사항 — 팀원 B 가 `life.db` 를 통째로 Supabase 로 옮길지, 벡터 표(`kb_chunk`,
`member_chunk`)만 파일로 남길지에 따라 8번의 볼륨이 완전히 사라질지 일부 남을지가 갈린다
(DEPLOY.md "아직 안 정한 것").
