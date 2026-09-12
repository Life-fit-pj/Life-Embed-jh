# LIFE,FIT — 추천 엔진

서울 427개 행정동 중 사용자의 자연어 검색어에 맞는 동네 TOP 5를 고르고,
LLM이 근거를 들어 설명해 주는 파이프라인입니다.

이 저장소는 자체 API 서버(`app/main.py` · `:8000`)를 갖고 있습니다.
화면은 아직 [life-fit-web](https://github.com/easty00/life-fit-web)(`:5000`)에 있고,
**웹이 HTTP로 이 엔진을 부릅니다** — 그래서 서버를 둘 다 띄워야 화면이 돕니다.
DB는 **Supabase PostgreSQL** 하나이고, 둘 다 `.env`의 `DATABASE_URL`로 붙습니다.

---

## 무엇을 하는가

```
"애들 학원 보내기 좋은 곳"
    ↓  weights.py      검색어 → 7개 지표 가중치
       교육 4.6 / 나머지 2.6~3.3
    ↓  (housing.py)    건물유형·거래유형·예산이 검색어에 있으면 그 조건에 맞는 동으로 먼저 추림
    ↓  recommend.py    가중치 → TOP 5
       방이1동 · 중계1동 · 쌍문제4동 · 대치1동 · 염리동
    ↓  explain.py      결과 → 사람이 읽을 설명문 (시세·조건 일치도 포함)
```

기존 서비스가 "3인 가구 40대"처럼 인구통계로 나누는 것과 달리,
**라이프스타일 선호도**로 동네를 고릅니다.

추천을 받은 뒤에는 지도 핀 하나를 설명하거나(`services/region_service.py`),
후속 질문에 답하는(`services/chat_service.py`) 두 가지 창구가 더 있습니다.

---

## 설치

### 1. 패키지

```bash
py -m pip install -r requirements.txt
```

버전이 고정돼 있습니다 — numpy 2.5.1 · python-dotenv 1.2.2 · sqlalchemy 2.0.52 ·
fastapi 0.121.2 · uvicorn 0.38.0 · anthropic 1.4.0 · openai 3.8.0.

LangChain 과 sentence-transformers 는 없습니다 — 2026-09 마이그레이션에서 SDK 를 직접
부르도록 바꾸고, 임베딩을 OpenAI 로 옮기면서 뺐습니다. 되살아나면 `check.sh` ⑤가 잡습니다.

빌드·린트 도구를 정의하는 매니페스트(`pyproject.toml` 등)는 아직 없습니다.
테스트는 `tests/`에 있습니다 — `py -m pytest tests -q` (아래 "확인하는 법" 참고).

### 2. API 키

프로젝트 루트에 `.env` 파일을 만듭니다. **키가 둘입니다.**

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

**둘 중 하나라도 없으면** `app/core/config.py`가 import 시점에 `RuntimeError`를 냅니다.
`.env`는 절대 깃에 올리지 마세요..

쓰는 모델도 `config.py`에 있습니다 — 설명문 LLM은 Claude `claude-haiku-4-5-20251001`(`MODEL`),
임베딩은 OpenAI `text-embedding-3-small`(`EMBED_MODEL`, 1536차원 · `EMBED_DIMENSION`).
2026-09 전까지는 임베딩이 내 컴퓨터에서 도는 `intfloat/multilingual-e5-small`(384차원)이었습니다 —
그때 만든 벡터는 차원부터 달라서 지금 모델과 섞어 쓸 수 없습니다.

> 서버 쪽 관리자 토큰(`ADMIN_TOKEN`, `ADMIN_WRITE_ENABLED`)은 여기가 아니라
> 이웃 저장소 `Life-Web`의 `.env`에 있습니다. 두 파일은 용도가 다릅니다.

### 3. DB 준비

**DB는 Supabase PostgreSQL입니다.** 옛 `data/life.db`(SQLite 파일)는 2026-09-12에 지웠습니다.

`.env`의 `DATABASE_URL`만 채우면 팀이 쓰는 DB에 그대로 붙습니다 — **표를 다시 만들 필요가 없습니다.**
주소는 Supabase 콘솔 → Connect → **Session pooler**에서 가져오고, 반드시
`postgresql+psycopg://`로 시작해야 합니다(`+psycopg`를 빼면 옛 `psycopg2`를 찾다가 죽습니다).

**표를 처음부터 만들어야 할 때만** 아래를 돌립니다. ⚠ **팀이 함께 쓰는 DB의 표를 지웁니다 —
되돌릴 백업 파일이 없으니 미리 알리세요.** Supabase에 `create extension if not exists vector`가
먼저 켜져 있어야 합니다(`chunks.embedding`이 `Vector(1536)`입니다).

```bash
py -m pipeline.schema     # CSV → 표 24개 생성 + 적재 (⚠ 기존 표를 DROP 한다)
py -m pipeline.chunk      # kb_persona.csv · nemotron.csv → chunks 표 9,900줄 (벡터는 아직 빈 칸)
py -m pipeline.embed      # 벡터가 빈 청크만 골라 OpenAI 로 채운다 (100개씩)
```

`data/`에 원본 CSV들이 있어야 합니다. `kb_persona.csv`가 없으면
`py -m pipeline.sample_kb`로 먼저 만듭니다(`seoul_persona_full.csv.gz`에서 구별 40명 층화추출).

`pipeline.embed`는 `embedding IS NULL`인 것만 찾습니다 — **중간에 끊겨도 다시 돌리면
남은 것부터 이어서** 합니다. 반대로 `pipeline.chunk`는 `chunks` 표를 지우고 다시 만드므로
**돌리면 벡터 9,900개가 같이 날아가고**, `pipeline.embed`를 처음부터 다시 돌려야 합니다
(약 0.1달러 · 10분). `pipeline.schema`는 `chunks`를 지우지는 않지만 `customers`를 다시
적재하므로, 돌렸으면 셋을 순서대로 다 돌리는 편이 안전합니다.

---

## 실행 방법

**반드시 프로젝트 루트에서 `-m`으로 실행합니다.**

```bash
py -m uvicorn app.main:app --reload --port 8000    # API 서버. 문서는 /docs
```

한 단계씩 떼어서 확인할 때는 이렇게 부릅니다.

```bash
py -m app.engine.weights            # 검색어 → 가중치
py -m app.engine.recommend          # 가중치 → TOP 5
py -m app.engine.explain            # TOP 5 → 설명문
py -m app.services.search_service   # 전체 흐름 한 번에
py -m app.services.region_service   # 동네 하나 설명 (시설명 근거)
py -m app.rag.retriever kb "조용한 동네에서 아이 키우는 사람"    # 벡터 검색만 (디버깅용)
```

이름이 옮겨 다녔습니다 — 추천 알고리즘은 2026-08~09에 `pipeline/`에서 `app/engine/`으로,
창구는 2026-09에 `app/features/`에서 `app/services/`로 갔습니다.
`pipeline.weights` · `pipeline.recommend` · `pipeline.search_kb` · `pipeline.chunk_kb`는
더 이상 없습니다. `app/features/`에 남은 여덟 파일은 `Life-Web`이 옛 이름으로 부르는
**다리**일 뿐이라 `__main__`이 없습니다 — `py -m app.features.search`는 안 돕니다.

`py pipeline/schema.py`처럼 파일 경로로 실행하면 `ModuleNotFoundError`가 납니다.
`-m` 없이 실행하면 프로젝트 루트가 검색 경로에 안 잡히기 때문입니다.

---

## 확인하는 법

```bash
py -m pytest tests -q       # 테스트 8파일 42개
bash check.sh               # 규칙이 지켜지나 일곱 가지
py -m tools.check_contract  # Life-Web 이 부르는 이름 36개가 살아 있나
```

`check.sh`는 일곱 가지를 셉니다.

| | 무엇 | 통과 기준 |
| --- | --- | --- |
| ① | **`app/`·`pipeline/`에 날 SQL(`text("…")`)이 있나** | 0곳 |
| ② | 함수 안 import 가 있나 | 0곳 |
| ③ | 계층 방향 (`tests/test_layers.py`) | `3 passed 1 failed` — 아래 참고 |
| ④ | 0바이트 `__init__.py` 가 있나 | 0개 |
| ⑤ | LangChain 이 되살아났나 | 0곳 |
| ⑥ | `app` 밖(tests·tools·pipeline)이 다리에 기대나 | 0곳 |
| ⑦ | **SQLite 전용 코드가 되살아났나** | 0곳 |

마지막 확인은 2026-09-12 — 테스트 `40 passed / 2 failed`, ①②④⑤⑥⑦ OK, 계약 36개 전부 생존.

**실패 둘은 DB 작업과 무관합니다.** ③은 `app/api/` 라우터 열이 `app/services/`가 아니라
다리(`app/features/`)를 부르는 것이고(`origin/dev-deploy`에 고쳐져 있음),
`test_supabase_auth`는 한글 가짜 토큰을 HTTP 헤더에 넣어 요청 전에 `UnicodeEncodeError`로
죽습니다(헤더는 latin-1만 담습니다) — 토큰을 ASCII로 바꾸면 통과합니다.

테스트 8파일 — `test_dong`(이름 표기 변형) · `test_masking`(개인정보) ·
`test_percentile`(백분위 동점) · `test_layers`(import 그래프) ·
`test_db`(엔진이 설정한 DB를 보나 · 여러 스레드) · `test_models`(모델 칸이 실제 표와 맞나) ·
`test_golden`(리팩터링 전후가 같나) · `test_supabase_auth`(가짜 토큰 거부).

`tests/golden/` 4장은 **"달라졌나"만** 봅니다 — 추천이 정확한지는 안 봅니다.
다시 찍으려면 파일을 지우고 `py -m tests.make_golden`을 돌립니다.
그중 `embed.json` 한 장은 OpenAI 를 실제로 부릅니다(문장 하나).

`tools/check_contract.py`는 **반드시 `-m`으로** 부릅니다. 파일 경로로 실행하면
(`py tools/check_contract.py`) 저장소 뿌리가 검색 경로에 안 잡혀 36개가 전부
"import 자체가 실패"로 나옵니다 — 코드는 멀쩡한데 계약이 깨진 것처럼 보입니다.

②가 왜 규칙인가 — 함수 안 import 는 순환 참조를 **고치는 게 아니라 눈에 안 보이게
덮습니다.** 파일 맨 위만 봐서는 이 파일이 무엇에 기대는지 알 수 없고, 증상이
"서버는 뜨는데 특정 기능만 죽음"으로 나타납니다. 필요해지면 그건 공통 부분을
아래층으로 내리라는 신호입니다.

> Windows PowerShell 에는 `bash`·`grep` 이 없습니다. Git Bash 터미널에서 돌리거나
> (VSCode 터미널 `∨` → Git Bash), VSCode 전체 검색(`Ctrl+Shift+F`)을 쓰세요.

---

## 폴더 구조

```
Life-Embed-jh/
├── app/          추천 엔진 본체 — 층 열둘. 지도는 바로 아래에 있다
├── pipeline/     한 번만 돌리는 준비 작업 (schema · sample_kb · chunk · embed · io)
├── tests/        DB·서버 없이 도는 것 + 골든 사진 4장
├── tools/        check_contract.py — Life-Web 이 부르는 계약 36개를 센다
├── docs/         REFACTOR.md — 옛 계획 기록
├── check.sh      규칙 일곱 가지를 센다
└── data/         원본 CSV (DB 는 Supabase 에 있다. life.db 는 지웠다)
```

### app/ 지도

**층이 열둘이다. 위층만 아래층을 부른다.** 번호는 `tests/test_layers.py` 의
`LAYER` 표와 같은 번호다 — 폴더를 옮기면 그 표도 같이 고친다.

| 층 | 폴더 | 무엇이 있나 |
| --- | --- | --- |
| 0 | `domain/` | `dong.py` — 행정동 이름 표기 변형. **아무것도 안 부르는 순수 함수** |
| 1 | `schemas/` | 라우터가 주고받는 형식 아홉 — `admin`·`analysis`·`auth`·`chat`·`customers`·`history`·`recommend`·`regions`·`survey`. pydantic 만 안다 |
| 1 | `core/` | `config.py` — `DATABASE_URL`·키·모델명·INDICATORS (`db.py` 는 지웠다) |
| 2 | `models/` | `customer` · `preference` · `chunk` · `history` + `region.py`(sqlacodegen 이 찍은 `Table` 여덟) |
| 2 | `repositories/` | **표를 실제로 읽고 쓰는 곳**(전부 ORM). `chunk_`·`member_`·`history_`·`region_repository` |
| 2 | `repositories/` 다리 | `members`·`chunks`·`history`·`regions` — **옛 이름을 지키는 다리**. `_run()` 이 세션을 연다 |
| 2 | `ai/` | `llm`(Claude) · `embedder`(OpenAI) · `vector_store` · `chunker` · `masking` |
| 3 | `rag/` | `retriever.py` — 검색어로 뜻이 가까운 청크를 찾는다 |
| 4 | `engine/` | 점수 계산 — `weights` · `recommend` · `explain` · `housing` · `resync` |
| 5 | `services/` | 업무 순서를 엮는 창구 여덟 |
| 6 | `features/` | **다리 여덟.** Life-Web 이 옛 이름으로 부르는 자리 — 웹을 합치는 날 폴더째 지운다 |
| 7 | `api/` | 라우터 **아홉** — **여기만 FastAPI 를 안다.** `main.py` 가 전부 `include_router` 한다 |

폴더 밖 파일 둘 —
`db.py`(`Base` · `engine` · `SessionLocal`) · `main.py`(`py -m uvicorn app.main:app`)

## 요청 하나가 흐르는 길

```
POST /recommend  "애들 학원 보내기 좋은 곳"
 └ api/recommend.py                 ← FastAPI 를 아는 유일한 층
    └ schemas/recommend.py            값 검사. 틀리면 여기서 422
    └ services/search_service.py      업무 순서를 엮는다
       ├ engine/weights.py            검색어 → 가중치 7개   (ai/llm.py)
       │  └ rag/retriever.py          비슷한 회원·사례 찾기 (ai/embedder · vector_store)
       ├ engine/housing.py            예산 조건이 있으면 후보를 먼저 추린다
       ├ engine/recommend.py          가중치 → TOP 5
       └ engine/explain.py            TOP 5 → 설명문        (ai/llm.py)
          └ repositories/(다리) → *_repository.py → db.py → Supabase Postgres
```

## 무엇을 고치려면 어디를 여나

| 고치고 싶은 것 | 여는 파일 |
| --- | --- |
| 좋아요를 눌렀을 때 저장되는 것 | `repositories/history_repository.py` `add_like` |
| 검색어에서 가중치 7개를 뽑는 규칙 | `engine/weights.py` (`ask_claude` · `blend`) |
| TOP 5 를 고르는 계산 | `engine/recommend.py` `recommend` |
| 전화번호·이름을 가리는 규칙 | `ai/masking.py` `mask` (DB 이름 물리는 곳은 `services/privacy_service.py`) |
| 관리자가 회원을 고칠 때의 값 검사 | `services/admin_service.py` `_validate` |
| Claude 를 부르는 곳 | `ai/llm.py` `ask` |
| API 키·DB 주소를 읽는 곳 | `core/config.py` (`DATABASE_URL` · `ANTHROPIC_API_KEY` · `OPENAI_API_KEY` · `SUPABASE_*`) |
| 행정동 표를 읽는 곳 | `repositories/region_repository.py` (칸 이름이 실행 중에 정해지면 `.c["이름"]`) |
| CSV 에서 DB 를 만드는 곳 | `../pipeline/schema.py` (⚠ **공유 DB** 의 표를 지우고 다시 만든다) |

## 규칙 넷 — `bash check.sh` 가 센다

1. **날 SQL 을 안 쓴다.** `app/`·`pipeline/` 어디에도 `text("…")` 가 없다 — 전부 ORM 이다
2. **아래층은 위층을 안 부른다.** 위 표의 번호 순서
3. **함수 안에서 import 하지 않는다.** 순환을 고치는 게 아니라 덮는 짓이다
4. **0바이트 `__init__.py` 를 안 둔다.** 그래서 실행은 항상 저장소 뿌리에서 `-m` 으로 한다

## 엔드포인트를 하나 더할 때

```
1. app/schemas/<이름>_schema.py     주고받을 형식
2. app/api/<이름>_router.py         라우터. app.services 를 부른다
3. app/main.py                      include_router 한 줄
4. bash check.sh                    일곱 가지 전부 OK
```

**3번을 빼먹기 쉽다.** 라우터 파일만 만들고 `include_router` 를 안 하면 **웹이 404 를 받는데,
`check_contract` 는 통과한다** — 이름은 살아 있고 경로만 안 열린 것이다. `/docs` 로 확인한다.

**`app.features` 를 부르지 않는다.** 그 폴더는 곧 통째로 사라진다.

파일 이름은 뒤에 역할을 붙인다 —
`…_schema.py` · `…_router.py` · `…_service.py` · `…_repository.py`.
`recommend` 라는 이름이 `engine`·`services`·`api` 세 층에 다 있어서,
안 붙이면 `grep` 이 세 갈래로 갈린다.

## 관리자 창구 (`app/services/admin_service.py`)

`Life-Web`의 관리자 화면이 부르는 함수들입니다. 조회는 화이트리스트로 칸을 제한하고,
수정은 값 범위를 검사한 뒤(`_validate`) 저장합니다.

| 하는 일 | 함수 |
|---|---|
| 조회 | `list_members` · `get_member` · `list_regions` · `get_region` (지표 12개 + 427동 백분위) |
| 수정 | `update_member` · `update_region` |
| 참고 | `preview_member`(희망조건으로 TOP 5 미리보기) · `similar_members`(페르소나가 비슷한 회원) |
| 점검 | `health`(DB·캐시 상태) · `dashboard`(연령·성별·7지표 평균·청크 분포) · `recent_logs` |
| 개인정보 | `privacy_preview`(원본 ↔ 가린 것 나란히, `changed`가 0이면 아무것도 안 가려진 것) |
| 캐시 | `clear_caches` |

**회원을 고칠 때는 세 곳이 항상 같이 움직여야 합니다.**
① DB 값 → ② 페르소나를 고쳤다면 벡터 재생성(`resync_member`) → ③ 캐시 비우기(`_clear_caches`).
하나라도 빠지면 "화면엔 새 값인데 추천은 옛날 것"이 됩니다. 수정 이력은 `admin_log` 표에
남습니다(`write_admin_log`, 표가 없으면 `ensure_admin_log`가 만듭니다).

### 개인정보 마스킹

내보내기 전에 페르소나 문장에서 전화번호·이메일·회원 이름·자치구/행정동 주소를 가리고,
연락 수단이 적힌 문장("카톡 아이디 abc123으로 주세요")은 문장째 걷어냅니다.

- `app/ai/masking.py` — 규칙만 있는 순수 함수. DB를 모르고, 이름 목록을 밖에서 받습니다.
- `app/services/privacy_service.py` — DB에서 이름·지역명을 읽어 그 규칙에 물려 주는 얇은 층.
  앱은 `mask_text()` 하나만 부릅니다. 회원 이름이 바뀌면 `privacy_service.reset()`으로 캐시를
  버립니다 (`admin_service._clear_caches()`가 이미 부릅니다).

**완벽하지 않습니다.** 목표는 "실수로 통째로 흘러나가는 것"을 막는 것이고,
무엇이 안 가려지는지는 `privacy_preview()`로 눈으로 확인해야 합니다.
자치구 이름은 두 글자 이상만 줄임말로 잡습니다 — `중구` → `중`은 집중·중요·도중을
921회 오탐해서 뺐습니다.

---

## 설계 원칙

### 자치구(25개) 단위 변수를 순위 계산에 쓰지 않는다

같은 구의 행정동이 전부 같은 값을 받아 구별할 정보가 없어집니다.
모든 인프라 지표는 **행정동 단위 밀도(개수 ÷ km²)** 로 변환해 씁니다.

소음·미세먼지처럼 구 단위밖에 없는 값은 참고 정보로만 쓰고,
표시할 때 "○○구 평균"임을 반드시 밝힙니다.

### 백분위로 바꾼 뒤 계산한다

밀도 원값을 그대로 곱하면 단위가 제각각입니다
(학원 1,263개/km² vs 공원 19개/km²). 그래서 모든 지표를
427개 동 중 백분위(0~100)로 바꾼 뒤 가중합합니다.

**같은 값은 반드시 같은 점수를 받습니다.** 밀도 칸에는 0이 대량으로 몰려 있어서
(도서관 275/427, 지하철역 169, 경찰관서 164) 동점 처리가 필수입니다.
예전에는 `argsort()`를 두 번 쓰는 방식이라 동점이 **DB 저장 순서(행정동 코드 순)**로
줄 세워졌고, 도서관이 똑같이 0곳인데 영등포구는 평균 56점 · 성동구는 14점을 받는
자치구 단위 편향이 생겼습니다. 지금은 동점 그룹이 순위를 평균내어 나눠 갖습니다.

백분위 구현은 두 곳에 있고 **규칙이 같아야 합니다** — `app/engine/recommend.py`의
`to_percentile()`(427개 배열, 순위 계산용)과 `app/repositories/regions.py`의
`column_percentile()`(칸+값 하나, 화면 표시용). 둘 다 화면에서 똑같이 "상위 N%"로
보이기 때문입니다. 입력이 달라서 **합칠 수는 없고**, 한쪽만 고치면 같은 동네가
화면마다 다른 점수로 보입니다.

### 절대점수만 쓰면 "만능 동네"가 항상 이긴다

골고루 높은 동네가 어떤 검색어를 넣어도 1위가 됩니다.
`build_relative`로 "그 동네 안에서 이 지표가 상대적으로 강점인 정도"를
같이 반영합니다(`mix` 파라미터로 비율 조절).

### 가중치 편차를 증폭한다

교육 4.6 vs 나머지 3.0은 비율로 1.5배뿐이라, 7개를 다 더하면
교육이 전체의 20%밖에 차지하지 못해 순위를 못 바꿉니다.
`sharpen=6`으로 평균 대비 편차를 지수로 키워, 사용자가 중시한 지표가
실제로 순위를 좌우하게 만듭니다.

### 예산은 "낮을수록 좋다"가 아니라 "목표가에 가까울수록 좋다"

처음엔 시세를 "무조건 낮을수록 좋다"로 볼 뻔했지만, 목표가를 구체적으로 준 경우
(예: "전세 4억 정도")엔 다릅니다. 강남처럼 비싼 동네에서도 그중 저렴한 집을 찾는
사람만 있는 게 아니라, 일부러 그 가격대 매물을 찾는 사람도 있기 때문입니다.

그래서 목표가가 있으면 `housing.py`가 목표가 대비 ±30%(`tolerance`) 안의 동만
후보로 남기고, 그 안에서 기존 7개 지표로 순위를 매깁니다. 목표가가 없을 때만
"시세는 낮을수록 좋다"를 8번째 참고 신호로 살짝 얹습니다(`DEFAULT_PRICE_WEIGHT`).

### 검색어를 사람 묘사로 바꿔서 검색한다

사용자 검색어는 "좋은 곳"처럼 **장소**를 찾는 문장인데,
회원 벡터에 담긴 건 **사람**을 묘사한 문장입니다.
성격이 다른 두 문장을 그대로 비교하면 엉뚱한 결과가 나옵니다.

그래서 Claude가 검색어를 `persona_query`("초등학생 자녀를 키우며
교육 환경을 중시하는 부모")로 바꾼 뒤 그 문장으로 검색합니다.

---

## 주의할 점

**임베딩 모델을 바꾸면 벡터를 전부 다시 만들어야 합니다.**
현재 OpenAI `text-embedding-3-small`(1536차원). 다른 모델은 차원부터 다르고,
저장할 때와 검색할 때가 반드시 같은 모델이어야 합니다.

**접두사는 이제 안 붙입니다.** `passage:` / `query:`는 e5 계열 전용 규칙이었고,
2026-09에 OpenAI로 옮기면서 `to_passage` / `to_query`와 함께 사라졌습니다.
길이를 1로 맞추는 것도 OpenAI가 해서 주므로 `vector_store.search()`는 내적만 합니다.

**벡터는 `chunks.embedding` 칸에 JSON 문자열로 담습니다.** 예전 `BLOB`(float32)이 아닙니다.
넣고 꺼내는 곳이 `app/ai/vector_store.py` 하나뿐이니(`to_text` / `from_text`),
나중에 pgvector로 옮길 때도 그 파일만 고치면 됩니다.

**청크를 고쳤으면 캐시를 버려야 합니다.** `vector_store`가 청크 9,900개를 메모리에 들고
있어서, `invalidate()`를 안 부르면 서버를 껐다 켜기 전까지 옛 벡터로 검색합니다
(`app/engine/resync.py`가 재임베딩 직후 대신 불러 줍니다).

**행정동 이름 표기가 파일마다 다릅니다.** `고덕제1동` vs `고덕1동`.
`app/domain/dong.py`의 `dong_variants()`가 양쪽을 다 시도합니다
(`app/repositories/regions.py`가 이걸 import해서 씁니다 — 사본을 만들지 마세요).

**LLM 프롬프트에 가중치를 실었으면 그 지표의 점수도 함께 실으세요.**
근거 수치 없이 항목 이름만 보이면 Claude가 그 항목을 지어내서 설명합니다.
특히 `시세` 점수는 `invert=True`라 **값이 클수록 저렴하다**는 뜻이므로,
방향 설명을 같이 주지 않으면 "시세 85점"을 "비싸다"로 정반대 해석합니다.

**`INDICATORS` 순서를 바꾸지 마세요.** 순서로 값을 꺼내는 코드가 있습니다.

---

## 데이터 출처

| 데이터 | 출처 |
|---|---|
| 행정동 인프라 | 서울열린데이터광장 |
| 주거 만족도 | 서울시 주거실태조사 마이크로데이터 (15,730명) |
| 페르소나 | NVIDIA Nemotron-Personas-Korea |
| 행정동 경계 | 통계청 SGIS |

---

## 아직 안 된 것

- 학교·버스·CCTV는 `master_dataset_v3`의 밀도(개수/km²)로만 순위 계산에 쓰이고,
  `facilities`(시설 "이름" 목록)엔 아직 없음 — 문화시설·의료·학원·공원·점포 5종만 있음
- 필터 지원 (`exclude_gu` — "강남 외" 같은 제외 조건)
- `schema.py`의 4·5단계(CSV 스캔·타입 추론·FK 추론)가 `if __name__` 없이 모듈 최상위에서
  실행됨 — `import pipeline.schema`만 해도 즉시 돈다
- 월세는 시세 25~75% 분포를 못 보여줌 — 원본 `시세_지역별_전처리.csv`에 `월임대료`용
  25/75 분위 칼럼 자체가 없음(매매가·보증금엔 있음). 신뢰등급·거래건수는 월세도 정상 표시됨
- 추천 정확도(hit@k)를 재는 평가 도구가 없음 — 지금 실측 기록은 전부 **속도**뿐.
  `tests/golden/`은 "전과 같은가"만 보지 "정확한가"는 안 본다(자리만 잡아 두었던
  `eval/golden.py`는 2026-09에 지웠다)
- `app/features/` 다리 여덟과 `app/repositories/`의 `members`·`chunks`·`history`·`regions`
  다리는 언젠가 지울 것 — `Life-Web`은 이미 HTTP로 넘어왔지만(`services/engine.py`가 `httpx`로
  `:8000`을 친다) `app/api/` 라우터가 아직 다리를 거친다(`check.sh` ③이 잡는 그것)
- **`tools/check_contract.py`는 절반만 유효하다** — 진짜 계약이 파이썬 이름에서 HTTP 경로로
  바뀌었다. 이름 36개가 다 살아 있어도 `app/main.py`가 라우터를 안 등록하면 웹은 404를 받는다

---

## 논의 필요

### 목표가 일치도를 순위에도 반영할 것인가 (2026-09-01 제기)

현재 `housing.py`의 `housing_fit_score()`(목표가 대비 0~100점)는 **후보를 추리는 필터로만**
쓰입니다. `app/services/search_service.py`의 `recommend_by_weights()`가 `matching_regions()`로 tolerance
(±30%) 안의 동만 남긴 뒤, 그 안에서의 순위는 기존 7개 지표로만 매깁니다.

그래서 "전세 6억 5천" 검색에서 62,000만원인 동(일치도 85점)과 73,000만원인 동(59점)이
**순위 계산에서는 완전히 동등하게** 취급됩니다.

- **지금대로 두는 쪽** — 가격은 "들어갈 수 있냐 없냐"의 문제고, 그 안에서는 생활
  인프라로 고르는 게 맞다. tolerance가 이미 ±30%로 좁으므로 후보는 전부 "예산에 맞는 곳"이다.
- **순위에 넣는 쪽** — 위 "설계 원칙"의 *예산은 목표가에 가까울수록 좋다*를 필터에서만
  지키고 순위에서는 버리는 셈이다. 일치도를 8번째 신호로 넣으면 원칙이 끝까지 일관된다.

넣기로 결정하면, `recommend_by_weights()`의 housing 분기에서 목표가가 없을 때 `시세`를
얹는 것과 **똑같은 방식**으로 `일치도`를 넣으면 됩니다(`scores`/`relative`/`weights` 세 곳).

### 설명문의 시세 어법 (위 결정과 함께 볼 것)

순위 반영 여부와 별개로, 지금은 Claude에게 **사용자가 말한 목표 금액 자체가 전달되지 않고**,
`price_fit_score()`가 `abs()`를 쓰기 때문에 방향(목표보다 비싼지 싼지)도 사라집니다.
그래서 "원하시는 가격대보다 조금 높은 편입니다" 같은 답변이 원리적으로 불가능합니다.
같은 일치도 85점이 62,000만원(싼 쪽)일 수도 68,000만원(비싼 쪽)일 수도 있습니다.

목표가와 방향을 프롬프트에 같이 넣어야 합니다.
(수정안이 적혀 있던 `STUDY.md`는 마이그레이션 때 지웠습니다 —
`git show 81af7d1^:STUDY.md`로 꺼내 볼 수 있습니다.)
