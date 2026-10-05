<div align="center">

# LIFE,FIT — 추천 엔진

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.121-009688?style=flat-square&logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-pgvector-3FCF8E?style=flat-square&logo=supabase&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Haiku_4.5-D97757?style=flat-square&logo=anthropic&logoColor=white)
![OpenAI](https://img.shields.io/badge/Embedding-text--embedding--3--small-412991?style=flat-square&logo=openai&logoColor=white)

서울 427개 행정동 중 자연어 검색어에 맞는 동네 TOP 5를 고르고, LLM이 근거를 들어 설명하는 엔진입니다.

[무엇을 하는가](#무엇을-하는가) · [설치](#설치) · [실행](#실행) · [확인](#확인) · [구조](#구조) · [설계 원칙](#설계-원칙) · [남은 일](#남은-일)

</div>

---

이 저장소는 자체 API 서버(`app/main.py` · `:8000`)를 갖고 있고, 화면은
[Life-Web](https://github.com/Life-fit-pj/Life-Web)(`:5000`)이 **HTTP로 이 엔진을 불러** 그립니다 —
그래서 서버를 둘 다 띄워야 화면이 돕니다. DB는 **Supabase PostgreSQL** 하나이고 `.env`의
`DATABASE_URL`로 붙습니다.

## 무엇을 하는가

```
"애들 학원 보내기 좋은 곳"
    ↓  weights.py      검색어 → 7개 지표 가중치
       교육 4.6 / 나머지 2.6~3.3
    ↓  (housing.py)    건물유형·거래유형·예산이 있으면 그 조건에 맞는 동으로 먼저 추림
    ↓  recommend.py    가중치 → TOP 5
       방이1동 · 중계1동 · 쌍문제4동 · 대치1동 · 염리동
    ↓  explain.py      결과 → 사람이 읽을 설명문 (시세·조건 일치도 포함)
```

인구통계("3인 가구 40대")가 아니라 **라이프스타일 선호도**로 동네를 고릅니다.
추천 뒤에는 지도 핀 하나를 설명하는 창구(`services/region_service.py`)와
후속 질문에 답하는 창구(`services/chat_service.py`)가 더 있습니다.

## 설치

### 1. 패키지

```bash
py -m pip install -r requirements.txt
```

버전이 고정돼 있습니다 — sqlalchemy · psycopg · pgvector · fastapi · uvicorn · anthropic · openai · langgraph.
LangChain과 sentence-transformers는 2026-09 마이그레이션에서 뺐습니다(되살아나면 `check.sh` ⑤가 잡습니다).

### 2. 환경 변수

프로젝트 루트에 `.env`를 만듭니다. **하나라도 없으면** `app/core/config.py`가 import 시점에
`RuntimeError`를 냅니다.

```
DATABASE_URL=postgresql+psycopg://...    # Supabase → Connect → Session pooler
ANTHROPIC_API_KEY=sk-ant-...             # 설명문 LLM
OPENAI_API_KEY=sk-...                    # 임베딩
SUPABASE_URL=https://....supabase.co     # 인증
SUPABASE_SERVICE_ROLE_KEY=...
```

- `DATABASE_URL`은 반드시 `postgresql+psycopg://`로 시작합니다 — `+psycopg`를 빼면 옛 `psycopg2`를 찾다가 죽습니다.
- 모델은 `config.py`에 있습니다 — 설명문 `claude-haiku-4-5-20251001`(`MODEL`), 임베딩 `text-embedding-3-small`(`EMBED_MODEL`, 1536차원).
- 관리자 토큰(`ADMIN_TOKEN`, `ADMIN_WRITE_ENABLED`)은 여기가 아니라 `Life-Web/.env`에 있습니다.

### 3. DB 준비

`DATABASE_URL`만 채우면 팀이 쓰는 DB에 그대로 붙습니다 — **표를 다시 만들 필요가 없습니다.**

<details>
<summary><b>표를 처음부터 만들어야 할 때만</b> (⚠ 공유 DB의 표를 지웁니다)</summary>

<br/>

되돌릴 백업 파일이 없으니 팀에 미리 알리세요. Supabase에 `create extension if not exists vector`가
먼저 켜져 있어야 합니다(`chunks.embedding`이 `Vector(1536)`).

```bash
py -m pipeline.schema     # CSV → 표 생성 + 적재 (⚠ 기존 표를 DROP)
py -m pipeline.chunk      # kb_persona.csv · nemotron.csv → chunks 표 9,900줄 (벡터는 빈 칸)
py -m pipeline.embed      # 벡터가 빈 청크만 OpenAI로 채움 (100개씩)
```

- `kb_persona.csv`가 없으면 `py -m pipeline.sample_kb`로 먼저 만듭니다(`seoul_persona_full.csv.gz`에서 구별 40명 층화추출).
- `pipeline.embed`는 `embedding IS NULL`만 찾으므로 **끊겨도 이어서** 합니다.
- `pipeline.chunk`는 `chunks` 표를 지우고 다시 만들어 **벡터 9,900개가 같이 날아갑니다** — `pipeline.embed`를 다시 돌려야 합니다(약 0.1달러 · 10분).
- `pipeline.schema`를 돌렸다면 셋을 순서대로 다 돌리는 편이 안전합니다.

</details>

## 실행

**반드시 프로젝트 루트에서 `-m`으로 실행합니다.** 파일 경로로 실행하면(`py pipeline/schema.py`)
루트가 검색 경로에 안 잡혀 `ModuleNotFoundError`가 납니다.

```bash
py -m uvicorn app.main:app --reload --port 8000    # API 서버. 문서는 /docs
```

한 단계씩 떼어서 확인할 때:

```bash
py -m app.engine.weights            # 검색어 → 가중치
py -m app.engine.recommend          # 가중치 → TOP 5
py -m app.engine.explain            # TOP 5 → 설명문
py -m app.services.search_service   # 전체 흐름 한 번에
py -m app.services.region_service   # 동네 하나 설명 (시설명 근거)
py -m app.rag.retriever kb "조용한 동네에서 아이 키우는 사람"    # 벡터 검색만
```

> 이름이 옮겨 다녔습니다 — 추천 알고리즘은 `pipeline/` → `app/engine/`, 창구는 `app/features/` → `app/services/`.
> `pipeline.weights` · `pipeline.recommend` · `pipeline.search_kb` · `pipeline.chunk_kb` · `app/features/`는 더 이상 없습니다.

## 확인

```bash
py -m pytest tests -q       # 테스트
bash check.sh               # 규칙 여섯 가지
py -m tools.check_routes    # Life-Web이 부르는 HTTP 경로가 다 열렸나 (반드시 -m)
py -m tools.show_prompts    # Claude에게 가는 프롬프트 일곱을 최종 글로 찍는다
```

| | `check.sh`가 세는 것 | 통과 |
| --- | --- | --- |
| ① | `app/`·`pipeline/`에 날 SQL(`text("…")`)이 있나 | 0곳 |
| ② | 함수 안 import가 있나 | 0곳 |
| ③ | 계층 방향 (`tests/test_layers.py`) | 통과 |
| ④ | 0바이트 `__init__.py`가 있나 | 0개 |
| ⑤ | LangChain이 되살아났나 | 0곳 |
| ⑥ | SQLite 전용 코드가 되살아났나 | 0곳 |

- `tests/golden/`은 **"달라졌나"만** 봅니다 — 정확한지는 안 봅니다. 다시 찍으려면 파일을 지우고 `py -m tests.make_golden`.
- `tests/test_golden.py`는 청크 본문을 전부 읽습니다(Supabase 전송량). 평소에는 `--ignore=tests/test_golden.py`로 뺍니다.
- ②가 규칙인 이유 — 함수 안 import는 순환 참조를 **고치는 게 아니라 덮습니다.** 필요해지면 공통 부분을 아래층으로 내리라는 신호입니다.

> Windows PowerShell에는 `bash`·`grep`이 없습니다. Git Bash 터미널(VSCode 터미널 `∨` → Git Bash)에서 돌리세요.

## 구조

```
Life-Embed-jh/
├── app/          추천 엔진 본체 (아래 표)
├── pipeline/     한 번만 돌리는 적재 작업 (schema · sample_kb · chunk · embed · io) + golden_search(추천 품질 측정)
├── tests/        pytest + 골든 사진
├── tools/        check_routes.py — Life-Web이 부르는 HTTP 경로 점검 · show_prompts.py — 프롬프트 찍어 보기
├── docs/         배포 문서 · ADR · 옛 계획
├── check.sh      규칙 여섯 가지를 센다
└── data/         원본 CSV (DB는 Supabase에 있다) · golden/ — 측정 문항
```

### app/ — 위층만 아래층을 부른다

번호는 `tests/test_layers.py`의 `LAYER` 표와 같습니다 — 폴더를 옮기면 그 표도 같이 고칩니다.

| 층 | 폴더 | 무엇이 있나 |
| --- | --- | --- |
| 0 | `domain/` | `dong.py` — 행정동 이름 표기 변형. 순수 함수 |
| 1 | `schemas/` · `core/` | API 형식(pydantic) · 설정(`DATABASE_URL`·키·모델명·`INDICATORS`) |
| 2 | `models/` | ORM 모델 — `customer` · `preference` · `chunk` · `history` · `region` |
| 2 | `repositories/` | **표를 실제로 읽고 쓰는 곳**(전부 ORM). `members`·`chunks`·`history`·`regions`는 옛 이름을 지키는 다리 |
| 2 | `ai/` | `llm`(Claude) · `embedder`(OpenAI) · `vector_store` · `chunker` · `masking` |
| 3 | `rag/` | `retriever.py` — 검색어로 뜻이 가까운 청크를 찾는다 |
| 4 | `engine/` | 점수 계산 — `weights` · `recommend` · `ranking`(조건 걸기 · 준비물 캐시) · `explain` · `chat_context`(채팅 재료) · `housing` · `resync` |
| 4 | `prompts/` | **Claude에게 가는 글 일곱** — `search` · `chat` · `admin` + 공통 `common`. 프롬프트는 여기서만 고친다 |
| 5 | `services/` | 업무 순서를 엮는 창구 — search · region · chat · admin · auth · privacy · survey · history · analysis · activity |
| 5 | `graph/` · `tools/` | LangGraph 흐름(검색 · 채팅)과 채팅 도구 일곱. **`services`를 부르지 않는다** — 부르면 순환이 되살아난다(`check.sh` ②) |
| 7 | `api/` | 라우터 — **여기만 FastAPI를 안다.** `main.py`가 전부 `include_router` |

### 요청 하나가 흐르는 길

```
POST /search  "애들 학원 보내기 좋은 곳"
 └ api/recommend.py                   ← FastAPI를 아는 유일한 층
    └ schemas/                          값 검사. 틀리면 여기서 422
    └ services/search_service.py        그래프 입구
       └ graph/nodes.py                 weights → recommend → explain 순서로 돈다
          ├ engine/weights.py           검색어 → 가중치 7개   (ai/llm.py · prompts/search.py)
          │  └ rag/retriever.py         비슷한 회원·사례 찾기 (pgvector)
          ├ engine/ranking.py           예산·자치구·세부 조건을 걸고 TOP 5를 뽑는다
          │  ├ engine/housing.py        예산 조건이 있으면 후보를 먼저 추린다
          │  └ engine/recommend.py      가중치 → 점수 계산
          └ engine/explain.py           TOP 5 → 설명문        (ai/llm.py · prompts/search.py)
             └ repositories/ → db.py → Supabase Postgres
```

### 무엇을 고치려면 어디를 여나

| 고치고 싶은 것 | 여는 파일 |
| --- | --- |
| 검색어에서 가중치 7개를 뽑는 규칙 | `engine/weights.py` (`ask_claude` · `blend`) |
| TOP 5를 고르는 계산 | `engine/recommend.py` `recommend` |
| 예산·자치구·세부 조건을 거는 순서 | `engine/ranking.py` `recommend_by_weights` |
| Claude에게 주는 지시문(프롬프트) | `prompts/` — 검색 `search.py` · 채팅 `chat.py` · 관리자 `admin.py`. 고친 뒤 `py -m tools.show_prompts`와 `tests/test_prompts.py` |
| 채팅이 쓰는 도구 | `tools/tools.py` |
| Claude를 부르는 곳 | `ai/llm.py` `ask` |
| 좋아요를 눌렀을 때 저장되는 것 | `repositories/history_repository.py` `add_like` |
| 전화번호·이름을 가리는 규칙 | `ai/masking.py` `mask` (DB 연결은 `services/privacy_service.py`) |
| 관리자가 회원을 고칠 때의 값 검사 | `services/admin_service.py` `_validate` |
| API 키·DB 주소를 읽는 곳 | `core/config.py` |
| 행정동 표를 읽는 곳 | `repositories/region_repository.py` |
| CSV에서 DB를 만드는 곳 | `pipeline/schema.py` (⚠ 공유 DB의 표를 지우고 다시 만든다) |

### 엔드포인트를 하나 더할 때

```
1. app/schemas/<이름>_schema.py     주고받을 형식
2. app/api/<이름>_router.py         라우터. app.services를 부른다
3. app/main.py                      include_router 한 줄   ← 빼먹기 쉽다. 빠지면 웹이 404
4. bash check.sh                    여섯 가지 전부 OK
```

파일 이름 뒤에는 역할을 붙입니다(`…_schema.py` · `…_router.py` · `…_service.py` · `…_repository.py`) —
`recommend`라는 이름이 세 층에 다 있어서, 안 붙이면 `grep`이 세 갈래로 갈립니다.

<details>
<summary><b>관리자 창구 · 개인정보 마스킹</b></summary>

<br/>

`Life-Web` 관리자 화면이 부르는 함수들입니다(`app/services/admin_service.py`). 조회는 화이트리스트로
칸을 제한하고, 수정은 값 범위를 검사한 뒤(`_validate`) 저장합니다.

| 하는 일 | 함수 |
|---|---|
| 조회 | `list_members` · `get_member` · `list_regions` · `get_region` (지표 12개 + 427동 백분위) |
| 수정 | `update_member` · `update_region` |
| 참고 | `preview_member`(희망조건으로 TOP 5 미리보기) · `similar_members`(페르소나가 비슷한 회원) |
| 점검 | `health` · `dashboard` · `recent_logs` |
| 개인정보 | `privacy_preview`(원본 ↔ 가린 것 나란히) |
| 캐시 | `clear_caches` |

**회원을 고칠 때는 세 곳이 같이 움직여야 합니다** — ① DB 값 → ② 페르소나를 고쳤다면 고친 칸의 벡터 재생성
(`resync_member`) → ③ 이름 목록 캐시 비우기(`_clear_member_caches`). 하나라도 빠지면 "화면엔 새 값인데 추천은 옛날 것"이 됩니다.
행정동 값을 고쳤을 때는 순위 준비물까지 전부 비웁니다(`_clear_caches`).

**개인정보 마스킹** — 내보내기 전에 전화번호·이메일·회원 이름·주소를 가리고, 연락 수단이 적힌 문장은
문장째 걷어냅니다. 규칙은 `app/ai/masking.py`(순수 함수), DB 연결은 `app/services/privacy_service.py`
(앱은 `mask_text()` 하나만 부릅니다). **완벽하지 않습니다** — 목표는 통째로 흘러나가는 것을 막는 것이고,
확인은 `privacy_preview()`로 합니다. 자치구 이름은 두 글자 이상만 줄임말로 잡습니다(`중구` → `중`은 921회 오탐).

</details>

## 설계 원칙

| 원칙 | 이유 |
|---|---|
| 자치구(25개) 단위 변수를 순위에 쓰지 않는다 | 같은 구의 동이 전부 같은 값을 받아 구별할 정보가 없다. 인프라는 **행정동 밀도(개수 ÷ km²)** 로 쓴다 |
| 백분위로 바꾼 뒤 계산한다 | 밀도 단위가 제각각이다(학원 1,263개/km² vs 공원 19개/km²) |
| 동점은 순위를 평균내 나눠 갖는다 | 0이 몰린 칸(도서관 275/427)에서 저장 순서가 점수를 정하던 편향을 없앴다 |
| 절대점수에 상대 강점을 섞는다 | 안 섞으면 골고루 높은 "만능 동네"가 항상 1위다(`build_relative`, `mix`) |
| 가중치 편차를 증폭한다 | 교육 4.6 vs 3.0은 합산하면 20%뿐이라 순위를 못 바꾼다(`sharpen=6`) |
| 예산은 "목표가에 가까울수록 좋다" | 목표가가 있으면 ±30% 안의 동만 남기고, 없을 때만 "시세는 낮을수록"을 8번째 신호로 얹는다 |
| 검색어를 사람 묘사로 바꿔 검색한다 | 회원 벡터는 **사람**을 묘사한 문장이라, 장소 문장을 `persona_query`로 바꿔 비교한다 |

<details>
<summary><b>주의할 점</b></summary>

<br/>

- **임베딩 모델을 바꾸면 벡터를 전부 다시 만들어야 합니다.** 저장과 검색이 반드시 같은 모델(`text-embedding-3-small`, 1536차원)이어야 합니다.
- **접두사는 안 붙입니다.** `passage:`/`query:`는 e5 계열 전용 규칙이었습니다.
- **벡터는 `chunks.embedding`에 pgvector `Vector(1536)`으로 담고, 검색도 DB가 합니다**(`<=>` 코사인 거리, top_k 줄만). 메모리에 9,900개를 올리던 방식은 egress 초과로 버렸습니다.
- **백분위 구현은 두 곳이고 규칙이 같아야 합니다** — `engine/recommend.py`의 `to_percentile()`(순위용)과 `repositories/region_repository.py`의 `column_percentile()`(화면용). 한쪽만 고치면 같은 동네가 화면마다 다른 점수로 보입니다.
- **행정동 이름 표기가 파일마다 다릅니다**(`고덕제1동` vs `고덕1동`). `domain/dong.py`의 `dong_variants()`만 쓰세요 — 사본을 만들지 마세요.
- **LLM 프롬프트에 가중치를 실었으면 점수도 함께 실으세요.** 근거 수치가 없으면 Claude가 지어냅니다. 특히 `시세` 점수는 `invert=True`라 **클수록 저렴하다**는 뜻이니 방향 설명을 같이 줘야 합니다.
- **`INDICATORS` 순서를 바꾸지 마세요.** 순서로 값을 꺼내는 코드가 있습니다.

</details>

## 데이터 출처

| 데이터 | 출처 |
|---|---|
| 행정동 인프라 | 서울열린데이터광장 |
| 주거 만족도 | 서울시 주거실태조사 마이크로데이터 (15,730명) |
| 페르소나 | NVIDIA Nemotron-Personas-Korea |
| 행정동 경계 | 통계청 SGIS |

## 남은 일

- 학교·버스·CCTV는 밀도로만 순위에 쓰이고 `facilities`(시설 이름 목록)에는 아직 없음
- 제외 필터 (`exclude_gu` — "강남 외")
- `pipeline/schema.py`의 일부 단계가 `if __name__` 없이 모듈 최상위에서 실행됨 — import만 해도 돈다
- 월세는 시세 25~75% 분포를 못 보여줌 — 원본에 `월임대료` 분위 칼럼이 없음
- 추천 정확도(hit@k)는 `py -m pipeline.golden_search`로 잽니다(27문항, Claude를 부릅니다 — 요금 주의). 채팅의 도구 선택은 아직 재는 도구가 없음
- `repositories/`의 다리 넷(`members`·`chunks`·`history`·`regions`) 정리

<details>
<summary><b>논의 필요 — 목표가 일치도를 순위에도 반영할 것인가</b> (2026-09-01 제기)</summary>

<br/>

`housing.py`의 `housing_fit_score()`(목표가 대비 0~100점)는 지금 **후보를 추리는 필터로만** 쓰입니다.
tolerance(±30%) 안의 동만 남긴 뒤, 순위는 7개 지표로만 매깁니다. 그래서 "전세 6억 5천" 검색에서
62,000만원인 동(일치도 85점)과 73,000만원인 동(59점)이 순위에서는 동등합니다.

- **지금대로** — 가격은 "들어갈 수 있냐"의 문제고, 그 안에서는 생활 인프라로 고르는 게 맞다.
- **순위에 넣기** — "목표가에 가까울수록 좋다"를 필터에서만 지키고 순위에서는 버리는 셈이다.

넣기로 하면 `recommend_by_weights()`의 housing 분기에서 `시세`를 얹는 것과 같은 방식으로 `일치도`를
넣습니다(`scores`/`relative`/`weights` 세 곳).

**설명문의 시세 어법** — 지금은 Claude에게 목표 금액이 전달되지 않고 `price_fit_score()`가 `abs()`를
써서 방향(비싼지 싼지)도 사라집니다. "원하시는 가격대보다 조금 높은 편입니다" 같은 답이 불가능하니,
목표가와 방향을 프롬프트에 같이 넣어야 합니다. (옛 수정안: `git show 81af7d1^:STUDY.md`)

</details>
