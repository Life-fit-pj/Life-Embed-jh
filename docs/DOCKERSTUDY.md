# DOCKERSTUDY.md

`Life-Embed-jh`(추천 엔진) 하나를 컨테이너에 올리기까지 **실제로 밟은 순서**를 정리한
학습 기록이다. 기준일 2026-09-09, 브랜치 `dev_docker`.

`DOCKER.md` 와 역할이 다르다 — 그쪽은 **17개 항목의 작업 대장**(무엇을 왜 하기로 했는가,
팀원 작업과의 관계)이고, 이 문서는 그중 **끝난 것만 골라 순서대로 다시 읽는 문서**다.
폐기된 항목(4번 CPU 전용 휠, 5번 모델 가중치 캐시 — KAN-86 으로 사라졌다)은 넣지 않았다.

## 큰 그림 — 세 단계

컨테이너화는 결국 **설계도를 쓰고 → 그걸로 이미지를 굽고 → 이미지를 띄우는** 세 걸음이다.

```
  [준비]            [1단계]              [2단계]                [3단계]
  파이썬 버전   →   Dockerfile      →   docker build      →   docker run
  확정              (설계도 작성)        (이미지 생성)          (컨테이너 실행)

                    requirements.txt ┐
                    app/             ┼─→ 이미지 386MB ─→ 컨테이너 :8010
                    .dockerignore    ┘        ↑                ↑
                                          빌드 때 굽는다    실행 때 주입한다
                                                            .env(키), data/(볼륨)
```

**세 단어의 차이가 이 문서의 전부다** —
`Dockerfile` 은 **레시피**(글자), `이미지` 는 그 레시피대로 만들어 둔 **완제품 스냅샷**(정지),
`컨테이너` 는 그 이미지를 **실제로 돌리고 있는 프로세스**(운동). 이미지 하나로 컨테이너를
몇 개든 띄울 수 있고, 컨테이너를 지워도 이미지는 남는다.

---

## 0단계 (준비) — 무엇 위에 올릴지부터 정했다

Dockerfile 첫 줄 `FROM` 에 뭘 쓸지가 정해지지 않으면 나머지를 쓸 수 없다. 로컬은 파이썬
3.14 지만 **패키지 휠(wheel) 제공 범위**를 보고 `python:3.12-slim` 을 후보로 잡아 실제로
돌려봤다.

```bash
docker run --rm -v <repo>/requirements.txt:/tmp/req.txt:ro python:3.12-slim \
  sh -c "pip install --dry-run --only-binary=:all: -r /tmp/req.txt"
# -> exit 0
```

`--only-binary=:all:` 은 **"소스 배포판은 쓰지 마라"** 는 뜻이다. 이걸 걸고도 통과했다는 건
25개 패키지가 전부 cp312 미리 컴파일된 휠로 설치된다는 뜻이고, 곧 **이미지 안에서 컴파일이
한 번도 안 일어난다**는 뜻이다.

### 이 검사는 왜 하고, 언제 다시 도나

이건 **버그를 찾는 도구가 아니라 결정의 근거를 확인하는 검사**다. 확인하려는 결정은 둘이다 —
`python:3.12-slim` 을 쓴다, 그리고 **빌더 스테이지 없이 단일 스테이지로 짠다.**

```
검사 실패 -> cp312 휠이 없는 패키지가 있다 -> 이미지 안에서 소스 컴파일이 일어난다
         -> gcc·빌드 도구를 이미지에 넣어야 한다 -> "단일 스테이지" 가 거짓이 된다
```

즉 실패는 "고장났다"가 아니라 **"결정이 뒤집혔다"** 는 신호이고, 그때는 1단계 Dockerfile 을
멀티스테이지로 다시 짜야 한다. **`requirements.txt` 나 `FROM` 이 바뀔 때만 돌리면 되고**
코드 수정과는 무관하다. 고친 것과 짝이 되는 검사를 돌린다고 외워 두면 된다 —

| 무엇을 고쳤나 | 짝이 되는 검사 |
|---|---|
| `app/**.py` | `py -m pytest tests -q` + AGENTS.md 의 계층 grep 세 줄 |
| `requirements.txt` / `FROM` | 위 휠 가용성 dry-run |

alpine 은 검토하지 않았다 — musl libc 기반이라 numpy 휠이 안 맞아 소스 빌드로 떨어진다.

> 이 단계의 선행으로 `requirements.txt` 정리도 끝나 있었다(DOCKER.md 1번). 버전 뒤에 `#`
> 없이 한글 설명이 붙어 있던 두 줄은 **pip 가 파싱에 실패해 빌드가 첫 `pip install` 에서
> 바로 죽는 지점**이었다.

---

## 1단계 — Dockerfile 작성 (설계도)

파일: `Dockerfile` (저장소 루트, 42줄). 지시어별로 하는 일은 이렇다.

| 지시어 | 하는 일 |
|---|---|
| `FROM python:3.12-slim` | 바닥에 깔 이미지. 0단계에서 확정 |
| `ENV PYTHONDONTWRITEBYTECODE / PYTHONUNBUFFERED` | `.pyc` 를 안 남기고, 로그를 버퍼에 가두지 않고 stdout 으로 바로 내보낸다 |
| `WORKDIR /code` | 이후 명령이 실행될 컨테이너 안 디렉터리 |
| `COPY requirements.txt` → `RUN pip install` | 의존성 설치 |
| `COPY app ./app` | 애플리케이션 소스 |
| `VOLUME ["/code/data"]` | `life.db` 가 마운트될 자리 표시 |
| `EXPOSE 8000` | "이 이미지는 8000을 쓴다"는 **문서용 표시** (실제 개방은 3단계 `-p`) |
| `CMD ["uvicorn", "app.main:app", ...]` | 컨테이너가 뜰 때 실행할 명령 |

이 저장소라서 특별히 정한 것이 넷 있다.

**① `WORKDIR` 은 저장소 루트, 이름은 `/code`.**
`app/` 이 `__init__.py` 없는 **네임스페이스 패키지**라서 루트가 `sys.path` 에 있어야 `app.*`
가 resolve 된다(AGENTS.md). 그래서 `app/` 안으로 들어가면 안 되고 루트를 작업 디렉터리로
둔다. 관례적으로 `/app` 을 많이 쓰지만 여기선 **패키지 이름 `app` 과 겹쳐 읽기 나빠져서**
`/code` 로 뒀다.

**② `COPY` 를 두 번에 나눈다.**
`requirements.txt` 만 먼저 넣고 설치한 다음, 그 뒤에 소스를 넣는다. Docker 는 레이어 단위로
캐시하므로 **소스만 고쳤을 때 `pip install` 레이어를 통째로 재사용**한다. 순서를 반대로 하면
주석 한 줄만 고쳐도 매번 25개 패키지를 다시 받는다.

**③ `pip install` 에 `--only-binary=:all:` 을 그대로 남겼다.**
0단계 dry-run 과 같은 옵션이다. 이걸 빌드에 박아두면 **"단일 스테이지" 라는 결정을 빌드가
스스로 지킨다** — 휠 없는 패키지가 새로 들어오는 순간 몇 분씩 조용히 컴파일하는 대신
그 자리에서 실패해서 알려준다.

**④ COPY 범위를 좁게 잡았다.** 런타임에 필요한 건 `app/` 뿐이다.

| 안 넣은 것 | 이유 |
|---|---|
| `pipeline/` | CSV → `life.db` 적재 전용. 배포에 안 따라간다(AGENTS.md) |
| `tests/` | 런타임 이미지에 테스트 러너를 넣지 않는다 |
| `data/` | `life.db` 는 볼륨 마운트, 원본 CSV 는 적재 전용 |
| `.env` | 이미지에 굽지 않는다 — 실행 시 주입한다 |

`pipeline/` 을 뺄 수 있는지는 확인이 필요했다. AGENTS.md 에 `app/engine/resync.py` 가
`pipeline/prep/chunking.py` 를 import 한다는 **계층 예외**가 적혀 있었기 때문이다. 실제로
열어보니 KAN-84 로 `app/ai/chunker.py` 를 쓰도록 바뀌어 있었다 — `app/` 어디에서도
`pipeline/` 을 import 하지 않으므로 빼도 된다. (AGENTS.md 의 그 서술이 낡았다.)

---

## 2단계 — Docker Image 생성 (`docker build`)

### 먼저 `.dockerignore` 를 만들었다

원래 DOCKER.md 에는 `.dockerignore`(7번)가 "3·6번이 끝난 뒤"로 적혀 있었는데 **순서가
반대였다.** 실제로 빌드해보니 이게 없으면 빌드를 시도하는 것 자체가 막힌다.

### `.dockerignore` 는 왜 만드나

**이미지 내용물을 바꾸는 파일이 아니라, 빌드가 시작되기 전에 Docker 에게 넘길 짐의 크기를
정하는 파일**이다. 이 저장소에서 만든 이유는 셋이다.

**첫째, 빌드 컨텍스트 전송.** `docker build .` 을 하면 Docker CLI 는 **`.` 폴더 전체를 먼저
데몬으로 통째로 전송**한 뒤에야 Dockerfile 첫 줄을 읽는다. 이 저장소는 그 폴더가 유난히 크다 —

```
.git    3.4GB   (data/ 대용량 파일이 Git LFS 로 들어 있다)
data/   1.0GB   (nemotron.csv 439M, life.db 332M, seoul_persona_full.csv.gz 225M)
------
합계    4.4GB   ← .dockerignore 가 없으면 매 빌드마다
```

우리 Dockerfile 은 `requirements.txt` 와 `app/` 만 COPY 하니 **결과 이미지는 어느 쪽이든
똑같다.** 달라지는 건 전송 시간뿐인데, Windows Docker Desktop 은 그 전송이 VM 경계를 넘어가
특히 느리다. 개발 중엔 Dockerfile 을 고쳐가며 열 번, 스무 번 빌드하게 되므로 매번 4.4GB 를
넘기면 작업 자체가 멈춘다. 실제로 `.dockerignore` 를 먼저 넣은 뒤 빌드는 **16.9초**에 끝났다.

**둘째, 비밀이 실수로 이미지에 구워지는 것을 막는 방어선.** 지금 Dockerfile 은 COPY 범위가
좁아 `.env` 가 들어갈 길이 없다. 하지만 누군가 편의상 `COPY . .` 한 줄로 바꾸는 순간 API 키
두 개가 이미지 레이어에 박힌다. **이미지를 받은 사람은 누구나 그 레이어를 꺼내볼 수 있고,**
뒤에 `.env` 를 지우는 레이어를 추가해도 앞 레이어에 남아 있어 소용없다. `.dockerignore` 에
넣어두면 그 파일은 애초에 데몬까지 가지 않으므로 COPY 를 어떻게 쓰든 구워질 수 없다.
Dockerfile 의 조심성에만 기대지 않고 한 겹 아래에서 막는 것이다.

**셋째, "런타임에 안 쓰는 것" 목록을 이유와 함께 한곳에 남긴다.** Dockerfile 의 COPY 는
"무엇을 넣는가"만 말하고 "왜 저건 뺐는가"는 못 말한다.

**흔한 오해 하나** — "`.dockerignore` 가 빌드 캐시를 살려준다"는 말은 우리 Dockerfile 에는
해당되지 않는다. 캐시 판정은 실제로 `COPY` 하는 경로의 파일 내용으로만 하므로 `.git` 이
바뀌어도 `COPY app ./app` 레이어는 안 깨진다. `COPY . .` 을 쓰는 Dockerfile 이었다면 커밋
한 번에 캐시가 통째로 날아가서 그 말이 맞다.

**주의** — `Life-Web` 쪽 `.dockerignore` 는 이걸 복사하면 안 된다. 그쪽은 `frontend/` 정적
파일과 `data/LH평면도` 이미지가 **이미지 안에 들어가야** `main.py` 의 `app.mount` 두 줄이
뜨기 때문에 `data/` 규칙이 정반대다.

### 빌드

```bash
docker build -t life-embed:dev .
# -> exit 0, 16.9초
#    DISK USAGE 386MB / CONTENT SIZE 84.1MB
```

`-t life-embed:dev` 는 만들어진 이미지에 붙이는 이름표(`이름:태그`)다. 안 주면 해시로만 남아
3단계에서 부르기 불편하다.

설치된 25개 패키지에 **`torch`·CUDA 계열은 하나도 없다.** 폐기된 4번 항목이 목표로 하던
크기(CPU 전용 휠로 깎아도 1.5GB)보다 훨씬 작다 — KAN-86 이 임베딩을 OpenAI API 호출로
바꾸면서 의존 사슬 자체가 사라진 효과가 그대로 숫자로 나왔다.

이 시점에 만들어진 것은 **아직 실행되지 않은 정지 상태의 스냅샷**이다. `docker images` 목록에
보이지만 아무것도 돌고 있지 않다.

---

## 3단계 — Docker Container 실행 (`docker run`)

```bash
docker run -d -p 8010:8000 --env-file .env -v <repo>/data:/code/data life-embed:dev
```

플래그 넷이 각각 2단계에서 **일부러 이미지에 넣지 않은 것들을 실행 시점에 채워 넣는다.**

| 플래그 | 왜 필요한가 |
|---|---|
| `-d` | 백그라운드 실행(detached). 터미널을 붙잡지 않는다 |
| `-p 8010:8000` | **호스트 8010 → 컨테이너 8000.** Dockerfile 의 `EXPOSE` 는 표시일 뿐이라 이게 없으면 밖에서 못 붙는다. 호스트 쪽을 8010 으로 둔 건 로컬에서 직접 띄운 uvicorn 과 포트가 겹치지 않게 하려는 것 |
| `--env-file .env` | `app/core/config.py` 가 `ANTHROPIC_API_KEY`·`OPENAI_API_KEY` 를 **import 시점에** 확인하고 없으면 RuntimeError 다. 하나만 넣어도 기동 못 한다. `.env` 를 이미지에 안 굽기로 했으니(9번) 여기서 넣는다 |
| `-v <repo>/data:/code/data` | 호스트의 `data/` 를 컨테이너 `/code/data` 에 붙인다. `life.db` 를 이미지에 굽지 않고 볼륨으로 주입하기로 한 8번 결정의 실행 |

`CMD` 는 Dockerfile 에 적어뒀으므로 명령을 따로 줄 필요가 없다. 컨테이너 안에서 `uvicorn` 이
`--host 0.0.0.0` 으로 뜨는데, **`127.0.0.1` 로 열면 컨테이너 안에서만 접속 가능**해서 `-p` 를
줘도 밖에서 못 붙는다.

### 검증 — 무엇을 보고 "됐다"고 판단했나

```
uvicorn 기동                 Application startup complete
GET /openapi.json            200 (라우터 29개 전부 노출)
GET /admin/health            200 {"ok":true,"regions":427,"members":100}
GET /regions/../facilities   200 (실제 시설 데이터 반환)
```

**`regions:427` 이 핵심이다.** `app/core/config.py` 는 DB 파일이 없어도 죽지 않고 경고만 찍은
뒤 **빈 DB 로 조용히 돌아간다.** 즉 볼륨 마운트가 실패해도 서버는 200 을 준다. 행 수까지
돌려주는 이 응답이 427 이라는 것이 **마운트가 실제로 붙었다는 증거**다(실패했다면 0).

이 확인 과정에서 DOCKER.md 10번의 전제가 틀렸다는 것도 드러났다. "두 서버 모두 헬스
엔드포인트가 없어 신규 코드가 필요하다"고 적어 뒀는데, `/openapi.json` 을 열어보니 엔진에는
**`GET /admin/health` 가 이미 있었다.** 엔진 쪽 남은 일은 엔드포인트 신설이 아니라
Dockerfile 에 `HEALTHCHECK` 를 연결하는 것뿐이다. (다만 경로가 `/admin/` 아래라 나중에
관리자 라우터에 토큰을 걸면 헬스체크가 401 로 죽는다는 점, 그리고 slim 이미지에는 `curl` 이
없어 `python -c "import urllib.request; ..."` 로 써야 한다는 점이 남아 있다.)

---

## 여기까지의 결과

| 단계 | 산출물 | 상태 |
|---|---|---|
| 0 준비 | `requirements.txt` 정리, `python:3.12-slim` 확정 | 완료 (DOCKER.md 1·2번) |
| 1 Dockerfile | `Life-Embed-jh/Dockerfile` | 완료 (3번) |
| 2 Image | `.dockerignore` + `life-embed:dev` 386MB | 완료 (7번 Embed 분) |
| 3 Container | 기동·헬스체크·볼륨 마운트 검증 | 완료 (8번 볼륨 방식 실증) |

**남은 큰 덩어리** — `Life-Web` 쪽 같은 세 단계(6번, 그리고 규칙이 다른 Web 용
`.dockerignore`), 두 컨테이너를 한 번에 띄우는 `docker-compose.yml`(11번), 비루트 사용자 등
보안 기본값(13번), 그리고 Render 의 `env: python → docker` 교체(16번).

**되짚어 볼 점 하나** — 이번에 순서가 뒤집힌 항목이 둘 있었다. `.dockerignore` 는 3번보다
먼저 필요했고, 헬스 엔드포인트는 이미 있었다. 둘 다 **문서를 다시 읽어서가 아니라 실제로
빌드하고 띄워봐서** 알게 된 것이다.
