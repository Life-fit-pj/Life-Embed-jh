# AGENTS.md

<!-- agents.md 공개 스펙 파일. Claude Code 외 다른 AI 코딩 도구(Cursor, Codex, Aider, Gemini CLI 등)도 이 파일을 읽는다.
     이 저장소에서는 "도구 무관 공통 지침"만 여기 쓰고, Claude Code 전용 사항은 CLAUDE.md에 남긴다.
     (지금 CLAUDE.md 는 `@AGENTS.md` 한 줄짜리 포인터다.) -->

## Project overview

**LIFE,FIT** — 서울 427개 행정동 중 사용자의 자연어 검색어(예: "애들 학원 보내기 좋은 곳")에 맞는 동네
TOP 5를 추천하고, Claude가 근거를 들어 설명해주는 추천 엔진이다.

**2026-09-02~12 두 차례 마이그레이션으로 구조가 크게 바뀌었다.** 바뀐 것 여섯:

| | 전 | 후 |
| --- | --- | --- |
| **DB** | `data/life.db` (SQLite 파일 331MB) | **Supabase PostgreSQL** — `.env` 의 `DATABASE_URL` 한 줄이 정한다 |
| **DB 접근** | `sqlite3` 직접 + 날 SQL | **전부 SQLAlchemy** (`app/models/` + `app/repositories/`). 앱에 SQL 문자열 0곳 |
| LLM·임베딩 | LangChain 래퍼 | **`anthropic` · `openai` SDK 직접** (`app/ai/`) |
| 임베딩 저장 | 로컬 `e5-small` 384차원 · BLOB | **OpenAI `text-embedding-3-small` 1536차원 · pgvector `Vector(1536)`** |
| 청크 표 | `kb_chunk` + `member_chunk` 둘 | **`chunks` 하나** (`source` 로 가름, 9,900줄) |
| 서버 | 없음 (Life-Web 이 import) | **자체 FastAPI** (`app/main.py` · `:8000`) |

**Life-Web 은 이제 HTTP 로 이 엔진을 부른다.** `Life-Web/services/engine.py` 가
`httpx` 로 `EMBED_API_BASE`(기본 `http://127.0.0.1:8000`)를 친다 — `sys.path` import 가 아니다.
**따라서 서버를 둘 띄워야 화면이 돈다**(엔진 `:8000` · 웹 `:5000`).

`app/features/` 여덟은 **옛 이름을 지키는 다리**이고 실제 내용은 `app/services/` 에,
`app/repositories/` 의 `members`·`chunks`·`history`·`regions` 넷도 다리이고 실제 내용은
같은 폴더의 `*_repository.py` 에 있다. **새 코드는 다리를 부르지 않는다** — `app/services/` 를
곧장 부른다(`check.sh` ⑥이 센다).

패키지는 `requirements.txt`. `pyproject.toml`·린트 설정은 아직 없다.
검증은 `tests/`(pytest 8파일 42개) + `bash check.sh`(일곱 가지) + `py -m tools.check_contract`(계약 36개).

## Setup / commands

> 전부 **저장소 루트**에서 `-m` 모듈 형태로 실행한다 (`app/`이 `__init__.py` 없는 네임스페이스
> 패키지라 루트가 sys.path에 있어야 `app.*`/`pipeline.*`이 resolve됨). 파일 경로로 직접 실행
> (`python pipeline/schema.py`)하면 `ModuleNotFoundError: No module named 'app'`로 실패한다.
>
> `.env` 에 **넷**이 필요하다 — `DATABASE_URL`(Supabase Postgres) · `ANTHROPIC_API_KEY`(설명문 LLM) ·
> `OPENAI_API_KEY`(임베딩) · `SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY`(인증).
> **하나라도 없으면** `app/core/config.py` 가 import 시점에 RuntimeError 를 낸다 — 기본값이 없다.
> `DATABASE_URL` 은 **`postgresql+psycopg://`** 로 시작해야 한다. `+psycopg` 를 빼면 SQLAlchemy 가
> 옛 `psycopg2` 를 찾다가 `ModuleNotFoundError` 로 죽는다.
>
> **API 서버**
> py -m uvicorn app.main:app --reload --port 8000    # 문서는 /docs. Life-Web 이 이걸 친다
>
> **적재 파이프라인 (data/*.csv → Supabase)**
> py -m pipeline.schema       # CSV 훑어 칸 타입 추론 -> 표 24개 재생성 (⚠ 아래 함정)
> py -m pipeline.sample_kb    # seoul_persona_full.csv.gz -> kb_persona.csv (구별 40명 층화추출)
> py -m pipeline.chunk        # kb_persona.csv · nemotron.csv 앞 100명 -> chunks 표 9,900줄 (⚠ 표를 지우고 다시)
> py -m pipeline.embed        # embedding IS NULL 인 청크만 OpenAI 로 채운다 (100개씩, 이어 하기 됨)
> py -m pipeline.fix_member_persona   # customers 표와 페르소나 인물이 어긋난 것 교정 (재실행 안전)
>
> **추천 파이프라인 (검색어 -> TOP 5 -> 설명문)**
> py -m app.engine.weights           # 검색어 -> 7개 지표 가중치
> py -m app.engine.recommend         # 가중치 -> TOP 5
> py -m app.engine.explain           # TOP 5 -> 설명문
> py -m app.services.search_service  # 위 셋을 순서대로 (search)
> py -m app.services.region_service  # 동네 하나 설명 (시설명 근거)
> py -m app.rag.retriever kb "조용한 동네에서 아이 키우는 사람"    # 벡터 검색만 (디버깅)
>
> `app/features/`·`app/repositories/regions.py` 는 다리라서 `__main__` 이 없다 — `py -m app.features.search` 는 안 돈다.
> 없어진 이름: `pipeline.weights` · `pipeline.recommend` · `pipeline.search_kb` · `pipeline.chunk_kb` ·
> `pipeline.embed_kb` · `pipeline.embed_member` · `app/llm.py` · `pipeline/prep/chunking.py`.

## Code style

디자인패턴을 준수하고, 파일에서 정해진 역할외에 의존성을 어기지않는 코드 설계를 한다.
함수 인자값에는 자료형을 명시하고 (doc : str), 핵심 주석을 간단 명료하게 작성한다.
코드 네이밍을 규격화하고 모두가 읽기 편한 방식으로 구조를 설계한다.

파일 이름 뒤에 역할을 붙인다 — `…_schema.py` · `…_router.py` · `…_service.py` · `…_repository.py`.
`recommend` 라는 이름이 `engine`·`services`·`api` 세 층에 다 있어서, 안 붙이면 grep 이 갈린다.

## Testing instructions

데이터 정합성을 검사하며, 사용자 쿼리에 따른 응답의 질을 높히는 것을 목표로한다.
청킹과 임베드 품질 향상에 중점을 두어 테스트를 통해 개선한다.

### 돌리는 법

    py -m pytest tests -q        # 저장소 뿌리에서. 8파일 42개 (40 통과 / 2 실패 — 아래 참고)
    bash check.sh                # 규칙 일곱 가지
    py -m tools.check_contract   # Life-Web 이 부르는 이름 36개 (HTTP 로 바뀌어 절반만 유효 — Architecture 참고)

    tests/test_dong.py         행정동 이름 표기 변형 (양방향)
    tests/test_masking.py      개인정보 마스킹. 긴 이름부터 지우는 순서까지 지킨다
    tests/test_percentile.py   백분위 동점 처리
    tests/test_layers.py       import 그래프가 한 방향인가 (LAYER 표와 짝)
    tests/test_db.py           engine 이 설정한 DB(postgresql)를 보나 · 여러 스레드에서 안 죽나
    tests/test_models.py       모델 칸 이름이 실제 표와 맞나 · 고정 표 줄 수(100·100·9,900)
    tests/test_golden.py       리팩터링 전후가 같나 (tests/golden/ 사진 4장)
    tests/test_supabase_auth.py 가짜 토큰을 거부하나 (⚠ 지금 실패 — 아래 참고)

**골든 사진은 "달라졌나"만 본다 — "정확한가"는 안 본다.** 다시 찍으려면 파일을 지우고
`py -m tests.make_golden`. `embed.json` 한 장은 OpenAI 를 실제로 부른다(문장 하나).

`tools/check_contract.py` 는 **반드시 `-m` 으로** 부른다. 파일 경로로 실행하면 뿌리가 검색
경로에 안 잡혀 36개가 전부 "import 실패"로 나온다 — 코드는 멀쩡하고 부르는 법만 틀린 것이다.

### 규칙이 지켜지나 — `bash check.sh` 일곱 가지

| | 무엇 | 통과 |
| --- | --- | --- |
| ① | **`app/`·`pipeline/` 에 날 SQL 이 있나** (`text("…")`) | 0곳 |
| ② | 함수 안 import 가 있나 | 0곳 |
| ③ | 계층 방향 (`tests/test_layers.py`) | `3 passed 1 failed` (아래 참고) |
| ④ | 0바이트 `__init__.py` 가 있나 | 0개 |
| ⑤ | LangChain 이 되살아났나 | 0곳 |
| ⑥ | `app` 밖(tests·tools·pipeline)이 다리에 기대나 | 0곳 |
| ⑦ | **SQLite 전용 코드가 되살아났나** | 0곳 |

**②가 왜 규칙인가** — 함수 안 import 는 순환 참조를 고치는 게 아니라 눈에 안 보이게 덮는다.
필요해지면 그건 공통 부분을 아래층으로 내리라는 신호다.

**①이 `text("…")` 만 보는 이유** — 4단계에서 전부 ORM 으로 옮긴 뒤로 **날 SQL 을 실행할 길이
`text()` 하나뿐**이다. `SELECT `·`INSERT ` 같은 낱말로 훑으면 "옛 SQL 은 `SELECT *` 였다" 같은
**주석까지 잡혀** 검사가 늘 X 로 끝난다. `app/models/` 만 예외인데, 거기 `text("CURRENT_TIMESTAMP")` 는
질의가 아니라 `server_default` 다. ⑦도 같은 이유로 글자 "SQLite" 가 아니라 `import sqlite3` 같은
**코드**만 본다 — 주석의 "SQLite 시절에는 …" 은 왜 이렇게 짰나를 남긴 기록이다.

**③은 지금 하나 실패한다** — `app/api/` 라우터 열이 `app/services/` 가 아니라 다리(`app/features/`)를
부른다. `supa-j` 가 API 를 만들 때부터 그랬고 DB 작업과 무관하다. `origin/dev-deploy` 에 고쳐져 있다.

Windows PowerShell 에는 `bash`·`grep` 이 없다. Git Bash 터미널에서 돌리거나
(VSCode 터미널 `∨` → Git Bash), VSCode `Ctrl+Shift+F`(files to include 에 `*.py`)를 쓴다.

**마지막 확인 2026-09-12** — pytest `40 passed / 2 failed`, check.sh ①②④⑤⑥⑦ OK(③은 위 참고),
계약 36개 전부 생존. 표 24개 · `chunks.embedding` 9,900줄 전부 채워짐.

**남은 실패 둘은 DB 작업과 무관하다** — ③(위)과 `tests/test_supabase_auth.py`.
후자는 한글 가짜 토큰을 HTTP 헤더에 넣어서 요청을 보내기도 전에 `UnicodeEncodeError` 로 죽는다
(헤더는 latin-1 만 담는다). 토큰을 ASCII 로 바꾸면 통과한다 — 인증 작업 때 같이 본다.

## Security considerations

API, Key 등 민감정보가 포함된 데이터는 .env폴더에서 별도로 관리하며, 외부로 노출시키지 않는다.
`.env` 에 키가 넷이다(`ANTHROPIC_API_KEY` · `OPENAI_API_KEY` · `SUPABASE_*` 둘).
**`DATABASE_URL` 에 DB 비밀번호가 들어 있다** — `.env` 는 `.gitignore` 안이고, 로그·이슈에 붙여넣지 않는다.
`service_role` 키는 RLS 를 무시하는 전권 키다. 서버 밖으로 절대 내보내지 않는다. 관리자 토큰
(`ADMIN_TOKEN`·`ADMIN_WRITE_ENABLED`)은 여기가 아니라 `Life-Web/.env` 에 있다.

밖으로 나가는 글은 `app/services/privacy_service.mask_text()` 를 거친다 — 전화·메일·회원 이름·
주소를 가린다. 규칙은 `app/ai/masking.py`(순수 함수, DB 를 모른다). **완벽하지 않다** —
목표는 "실수로 통째로 흘러나가는 것"을 막는 것이고, 확인은 `admin_service.privacy_preview()` 로 한다.

## Commit / PR guidelines

사용자가 직접 git 에 접근하며, Agent는 Commit, Push는 하지않는다.

## Architecture

```
app/domain/       dong.py                    순수 계산. 아무것도 안 부른다
app/schemas/      recommend_schema.py        API 가 주고받는 형식. pydantic 만 안다
app/core/         config.py                  설정(DATABASE_URL·키·모델·INDICATORS). db.py 는 지웠다
app/models/       customer, preference,      표를 클래스로 (ORM). history.py 에 표 여섯
                  chunk, history, region     region.py 는 sqlacodegen 이 찍은 Table 여덟(칸 이름에
                                             ㎡·/·숫자시작이 있어 클래스로 못 적는다 — .c["이름"] 로 쓴다)
app/repositories/ chunk_, member_, history_, 표를 실제로 읽고 쓰는 곳(ORM). 딕셔너리·튜플만 낸다
                  region_repository
                  members, chunks, history,  옛 이름을 지키는 다리. _run() 이 세션을 열고 닫는다
                  regions
app/ai/           llm(Claude), embedder      외부 모델과 순수 규칙. 모델 교체는 이 폴더만 고친다
                  (OpenAI), vector_store,
                  chunker, masking
app/rag/          retriever.py               검색어 -> 뜻이 가까운 청크·사람
app/engine/       weights, recommend,        점수 계산. resync 는 한 명만 재임베딩(관리자 수정 직후)
                  explain, housing, resync
app/services/     search, region, chat,      업무 순서를 엮는 창구 여덟. SQL 도 표 이름도 없다
                  admin, analysis, auth,
                  privacy, survey
app/features/     같은 이름 여덟             ★ 다리. `from ..._service import *` 한 줄뿐
app/api/          라우터 열                  여기만 FastAPI 를 안다. Life-Web 이 HTTP 로 친다
app/db.py                                    Base · engine · SessionLocal. DB 접근은 전부 여기를 지난다
app/main.py                                  py -m uvicorn app.main:app --port 8000
pipeline/         schema, sample_kb, chunk,  CSV -> Postgres · chunks 표. 배포엔 안 따라간다
                  embed, io, fix_member_persona
tests/            8파일 + golden/ 사진 4장   DB 는 쓰고 서버·화면은 안 띄운다
tools/            check_contract.py          Life-Web 이 부르는 계약 36개를 센다
```

**`tools/check_contract.py` 는 이제 절반만 유효하다.** Life-Web 이 `sys.path` import 를 버리고
HTTP 로 넘어가면서 **진짜 계약은 파이썬 이름이 아니라 엔드포인트 경로**가 됐다.
이 검사기는 아직 `app.repositories.*`·`app.features.*` 의 이름 36개를 세는데, 그게 다 살아 있어도
`app/main.py` 가 라우터를 안 등록하면 웹은 404 를 받는다. **둘 다 봐야 한다.**

**층 번호 — 아래층은 위층을 부르지 않는다.**

```
0 domain → 1 schemas · core → 2 models · repositories · tables · ai
         → 3 rag → 4 engine → 5 services → 6 features(다리) → 7 api → Life-Web
```

이 번호표는 `tests/test_layers.py`의 `LAYER` 표와 짝이다. 한쪽만 고치면 어긋난다.
같은 층끼리 부르는 것은 허용하되 순환은 안 된다 — 순환이 필요해지면 그건
공통 부분을 아래층으로 내리라는 신호다(함수 안 import 로 덮지 말 것).

**계층 예외는 이제 없다.** 예전엔 `app/engine/resync.py` 가 `pipeline/prep/chunking.py` 를
import 했지만, 4단계에서 청킹 규칙이 `app/ai/chunker.py` 로 올라오면서 사라졌다
(`test_layers.py` 의 `ALLOWED_PIPELINE` 이 빈 집합인 이유). **청킹 규칙은 여전히 한 곳뿐이고,
적재(`pipeline/chunk.py`)와 관리자 재임베딩(`resync.py`)이 그 한 곳을 같이 쓴다** — 고칠 때는
양쪽이 같이 바뀐다는 것을 알고 고친다.

### Data Flow Summary

```
master_dataset_v3.csv, customers_v2.csv, 개별 시설 CSV들 → pipeline/schema.py → Supabase Postgres(표 17)
                                                       → Base.metadata.create_all() → 모델 표 7

kb_persona.csv ─┐
nemotron.csv ───┴→ pipeline/chunk.py → chunks 표(9,900줄, embedding 은 빈 칸)
                                     → pipeline/embed.py → embedding 채움(OpenAI 1536차원 Vector)

검색어 → engine/weights.py(가중치) → engine/recommend.py(TOP 5) → engine/explain.py(설명문)
       └ app/services/search_service.py 의 search() 가 이 셋을 순서대로 호출
       └ 가격 조건이 있으면 engine/housing.py 가 후보를 먼저 추린다

추천 결과 클릭/후속 질문 → services/region_service.py(동네 하나) / services/chat_service.py(후속 질문)
벡터 검색 → rag/retriever.py → ai/embedder.py(질문 벡터) + ai/vector_store.py(캐시·코사인)
```

### Domain Rule

- **7개 지표**는 `config.py`의 `INDICATORS = ["녹지","안전","교통","상권","의료","교육","문화"]`가
  유일한 정의처다. `user_preferences` 칸 이름이자 `recommend.py`의 `INDICATOR_COLUMNS` 키,
  `Preference` 모델의 칸 이름과 반드시 일치해야 한다.
- **`user_preferences` 의 `_초기` 7칸은 CSV 에 없는 파생 칸이다.** `pipeline/schema.py` 가 적재
  직후 현재값을 복사해 만든다(`SNAPSHOT_COLUMNS`). 관리자 화면의 "가입 시 희망 조건"과
  `analysis_service.facts_drift()` 가 읽는다. 낡은 DB 에는 없을 수 있어서
  `member_repository.has_initial_columns()` 가 **실제 DB 를 보고** 먼저 확인한다 —
  ORM 은 "칸이 있다고 치고" 도는 도구라 이 질문에 답하지 못한다.
- **임베딩은 저장할 때와 검색할 때가 반드시 같은 모델이어야 한다** (`EMBED_MODEL` =
  `text-embedding-3-small`, `EMBED_DIMENSION` = 1536). 모델을 바꾸면 9,900개를 전부 다시 만든다.
- **접두사는 안 붙인다.** `passage:`/`query:` 는 e5 계열 전용 규칙이었고 `to_passage`/`to_query`
  와 함께 사라졌다. 길이를 1로 맞추는 것도 OpenAI 가 해서 주므로 `vector_store.search()` 는
  내적만 한다.
- **벡터는 `chunks.embedding` 에 pgvector 의 `Vector(1536)` 으로 담는다**(옛 JSON 글자 아님).
  드라이버가 숫자 배열을 그대로 건네주므로 되돌리는 절차가 없다 — 옛 `to_text`/`from_text` 는 지웠다.
  **★ 담는 방식만 바꿨고 검색은 그대로 `app/ai/vector_store.py` 가 메모리에서 한다.** 9,900개는
  내적이 DB 왕복보다 빠르다. DB 의 `<=>` 로 옮기는 것은 별개 작업이다.
  `Vector` 칸을 만들려면 Supabase 에 `create extension if not exists vector` 가 먼저다.
- **청크를 고쳤으면 `vector_store.invalidate(source)` 를 반드시 부른다.** 9,900개를 메모리에
  들고 있어서, 안 버리면 서버를 껐다 켜기 전까지 옛 벡터로 검색한다(`resync.py` 가 부른다).
- **`chunks` 는 한 표다.** `source` 가 `"member"`/`"kb"`, `source_id` 가 `customer_id`/`uuid` 다.
  repository 가 부르는 쪽 편의를 위해 옛 키 이름으로 돌려주므로, 표 이름이 아니라 **`source` 로
  걸러야** 한다 — 안 걸면 kb 9,000줄이 회원 조회에 섞인다.
- 행정동 이름 표기가 파일마다 다르다 (`고덕제1동` vs `고덕1동`). **`app/domain/dong.py`의
  `dong_variants()`가 유일한 정의처**이고 `app/repositories/region_repository.py`가 import 해서 쓴다.
  양방향 변형을 모두 만들어 SQL `IN (...)` 으로 한 번에 시도한다. docstring 은 반대 방향을
  안 만든다고 적혀 있지만 실제 코드는 두 방향 다 만든다 — 코드를 직접 볼 것.
- **백분위는 동점을 순위 평균으로 처리한다.** 밀도 칸에 0이 대량으로 몰려 있어(도서관 275/427,
  지하철역 169, 경찰관서 164) 동점 처리를 안 하면 "값이 같은데 점수가 다른" 일이 생긴다.
  구현이 두 곳이고 **규칙이 반드시 같아야 한다** — `app/engine/recommend.py` 의
  `to_percentile(values, invert)`(427개 배열, 순위용), `app/repositories/region_repository.py` 의
  `column_percentile(column, value, invert)`(칸+값 하나, 화면 표시용). 입력이 달라 합칠 수 없고,
  한쪽만 고치면 같은 동네가 화면마다 다른 점수로 보인다.
- **"시세" 점수는 방향이 반대다.** `build_price_score()` 가 `invert=True` 로 만들어 **값이 클수록
  저렴한 동네**다. 가격 조건이 없는 검색에서만 `app/services/search_service.py` 가 8번째 지표로
  얹는다(`DEFAULT_PRICE_WEIGHT = 3`). LLM 프롬프트에 실을 때는 방향 설명을 반드시 같이 준다 —
  안 주면 "시세 85점"을 "비싸다"로 정반대 해석한다.
- **가중치와 점수는 항상 짝이 맞아야 한다.** 프롬프트에 어떤 지표의 가중치를 실었으면 그 지표의
  점수도 같이 싣는다. 가중치만 있고 근거 점수가 없으면 LLM 이 그 항목을 지어내서 설명한다.

### ⚠ DB 관련 함정

- **★ DB 가 파일이 아니라 팀이 함께 쓰는 Supabase 다.** `pipeline.schema` 는 이제
  "내 컴퓨터의 파일을 다시 만드는 명령"이 아니라 **"공유 서버의 표를 지우는 명령"** 이다.
  되돌릴 백업 파일이 없다. 돌리기 전에 팀에 말한다.
- **`py -m pipeline.schema` 는 표 17개를 DROP 하고 다시 만든다**(y/n 을 한 번 묻는다).
  쌓인 기록(좋아요·검색·채팅·관리자로그)이 **전부 날아간다.** `chunks` 는 안 지워지지만
  `customers` 가 다시 적재되므로 `pipeline.chunk` → `pipeline.embed` 를 이어서 돌리는 것이 안전하다
  (OpenAI 요금이 다시 나간다 — 약 0.1달러 · 10분).
- **`py -m pipeline.chunk` 는 `chunks` 표를 drop 하고 다시 만든다.** 텍스트는 CSV 에서 몇 초면
  돌아오지만 **벡터는 안 돌아온다** — 반드시 `pipeline.embed` 를 이어서 돌린다.
- **`py -m pipeline.embed` 는 안전하다.** `embedding IS NULL` 인 것만 찾으므로 중간에 끊겨도
  다시 돌리면 남은 것부터 이어서 한다.
- **`data/life.db` 는 지웠다**(`.gitattributes` 의 `*.db` 줄도 같이). 옛 파일이 필요하면
  `git show <SQLite 시절 커밋>:data/life.db` 로 이력에서 꺼낸다.
  `.csv.gz`·`nemotron.csv` 는 여전히 Git LFS 이므로 체크아웃 직후 `git lfs pull` 이 필요하다.
- 관리자가 **회원을 고칠 때는 셋이 같이 움직인다** — ① DB 값 ② 페르소나를 고쳤으면
  `resync_member()` 로 벡터 재생성 ③ `admin_service._clear_caches()`. 하나라도 빠지면
  "화면엔 새 값인데 추천은 옛날 것"이 된다.

## Logging

**`logs/` 폴더는 아직 없다.** 기록은 DB 표 다섯에 쌓인다 — `likes` · `search_history` ·
`chat_history` · `analysis_chat` · `admin_log`. 표를 세우는 일은 `pipeline/schema.py` 끝의
`Base.metadata.create_all()` 이 한 번에 한다 — **옛 `ensure_*` 여섯은 지웠다.**
"쓸 때 표를 만든다" 는 파일 DB 시절 습관이고, Postgres 에서는 서비스 코드가 DDL 을 던질 자리가 아니다.
`analysis_service` 는 이 표들을 집계해 Claude 에게 해석시킨다 — **집계는 우리가 만들고 Claude
에게는 숫자만 준다**(느린 쿼리·잘못된 조인·개인정보 칸 노출을 원천적으로 없앤다).

## 기록은 어디에 있나

| 파일 | 무엇 |
| --- | --- |
| `README.md` (이 저장소) | 설치·실행·설계 원칙·아직 안 된 것·논의 필요 |
| `docs/REFACTOR.md` | **옛 계획**(FastAPI 이전 논의, ADR-0001). 남의 컴퓨터 절대경로가 섞여 있다 |
| 루트 `studyall.md` | 지도 — 지금 어디 있고 무엇은 안 하기로 했나 |
| 루트 `study2.md` | 교안 — 지금 진행 중인 작업 하나(2026-09-08 기준 10단계: 지도와 검사) |
| 루트 `study2-archive.md` | 끝난 교안 보관함. 마이그레이션 0~9단계는 `[보관 11]`~`[보관 21]` |

**`STUDY.md`(엔진 성능 진단 [A]~[E]와 추천 품질 버그 5건)는 마이그레이션 때 지웠다.**
필요하면 `git show 81af7d1^:STUDY.md` 로 꺼내 본다. 거기 적힌 파일 경로는 8월 구조 기준이라
지금과 다르다 — 코드를 직접 볼 것.
