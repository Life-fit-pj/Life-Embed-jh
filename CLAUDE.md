# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**LIFE,FIT** — 서울 427개 행정동 중 사용자의 자연어 검색어(예: "애들 학원 보내기 좋은 곳")에 맞는 동네
TOP 5를 추천하고, LLM(Claude)이 근거를 들어 설명해주는 서비스의 백엔드 파이프라인이다.
`src/`, `docu/DESIGN.md`는 여전히 비어 있다. 실제 코드는 `app/core/`(조회 인프라), `app/features/`
(검색·설명·채팅 창구), `pipeline/`(DB 적재·추천 로직) 세 곳에 있다.

프레임워크·빌드·린트·테스트 도구를 정의하는 매니페스트(`requirements.txt`, `pyproject.toml` 등)가 없다.
검증은 각 파일 하단의 `if __name__ == "__main__":` 블록을 직접 실행해 눈으로 확인하는 방식으로 이루어진다.

## Setup & running

의존성은 매니페스트가 없으므로 코드에서 실제로 import하는 것 기준으로 설치해야 한다:
`python-dotenv`, `langchain-anthropic`, `langchain-huggingface`(+ 내부적으로 `sentence-transformers` 필요), `numpy`.

`.env`에 `ANTHROPIC_API_KEY`가 반드시 있어야 한다 — 없으면 `app/core/config.py`가 import 시점에
`RuntimeError`를 던진다.

### 실행 방법: 반드시 프로젝트 루트에서 `-m`으로 (해결됨)

과거에는 `core.*`/`pipeline.*`가 서로 다른 루트에 있는데 위치가 안 맞아 `ModuleNotFoundError`가 났다.
지금은 전 파일이 `from app.core.xxx import ...` / `from app.features.xxx import ...` 형태로 통일되어,
**프로젝트 루트가 sys.path에 있기만 하면** `app.core.*`, `app.features.*`, `pipeline.*` 모두 resolve된다
(`app/`은 `__init__.py` 없는 네임스페이스 패키지).

- 실행은 항상 프로젝트 루트에서 모듈 경로로: `python -m pipeline.schema`, `python -m app.features.pipeline_api`
  등. 직접 확인함 — `python -m pipeline.schema`가 정상적으로 `core.config`/`app.core.io`까지 다 resolve해
  기존 DB 존재 여부를 묻는 프롬프트까지 도달한다.
- **파일 경로로 직접 실행하면 여전히 안 된다**: `python pipeline/schema.py`는 `ModuleNotFoundError: No
  module named 'app'`로 즉시 실패한다 (직접 확인함). 이건 버그가 아니라 `-m` 없이 스크립트를 실행하면
  프로젝트 루트가 sys.path에 안 잡히는 파이썬의 일반적인 동작이므로, 스크립트를 돌려달라는 요청이 오면
  항상 `python -m <점경로>` 형태로 실행할 것.
- `pipeline_api.py`는 `app/core/`에서 `app/features/`로 이동했다. 안에 남아있는
  `sys.path.insert(0, .../app)`는 이제 불필요하지만 해가 되지도 않는다 (import는 전부
  `app.core.*`/`app.features.*`/`pipeline.*`로 이미 루트 기준이라 이 줄과 무관하게 동작함)..

### `config.py`의 ROOT 계산 (해결됨)

`ROOT = Path(__file__).resolve().parent.parent.parent`로 고쳐져 프로젝트 루트를 정확히 가리킨다
(`DATA_DIR` = 루트의 `data/`, `DB_PATH` = `data/life.db`). 직접 확인함 — `DB_PATH.exists()` True,
`data/life.db`가 실제로 227MB로 채워져 있음 (표들이 다 적재된 상태). `config.py`에 이제 `DB_PATH`가
없을 때 알림을 찍는 방어 코드도 추가되어 있다.

### `save_csv` 누락 (해결됨)

과거에는 `pipeline/chunk_kb.py`와 `pipeline/sample_kb.py`가 `app/core/io.py`에 없는 `save_csv`를
import해 실행 시 `ImportError`가 났다. 지금은 `app/core/io.py`에 `save_csv`(딕셔너리 목록을
utf-8-sig CSV로 저장, 저장 후 줄 수·용량을 출력)가 구현되어 있어 두 파일 모두 정상 동작한다
(직접 확인함).

## Architecture

### 계층 분리: `app/core/` (조회 인프라) vs `app/features/` (기능 창구) vs `pipeline/` (파이프라인)

- **`app/core/`** — 이미 만들어진 SQLite DB에서 데이터를 "꺼내기만" 하는 인프라 계층.
  - `config.py` — 경로, `ANTHROPIC_API_KEY`, 모델 이름, 7개 지표 이름(`INDICATORS`), 페르소나
    청킹 대상 칸(`CHUNK_COLUMNS`) 등 전역 설정.
  - `db.py` — SQLite 조회 함수 모음. 회원/지식베이스 벡터·가중치 조회(`member_chunks`,
    `member_weights`, `region_densities`, `kb_chunks`), 시설 조회(`facilities`, `facility_counts`,
    `facility_categories` — 분류별 개수, `region_extras` — 슬라이더 7개 지표 외 부가 생활 정보),
    백분위 계산(`to_percentile`)까지 담당한다. 행정동 이름 표기 변형은 `dong_variants()`가 처리하는데,
    함수 docstring은 "'제' 를 없애는 방향으로만 만들고 반대는 만들지 않는다"고 적어 두었지만 실제
    코드는 정규식을 하나 더 두어 반대 방향('N동' → '제N동') 변형도 함께 만든다 — docstring과 코드가
    어긋나 있으니 이 함수를 손댈 때 실제 정규식 두 줄을 직접 확인할 것.
  - `io.py` — CSV 읽기/쓰기 유틸. `read_csv`는 utf-8-sig → cp949 순으로 인코딩을 자동 시도하고,
    `save_csv`는 딕셔너리 목록을 utf-8-sig CSV로 저장한다.
  - `llm.py` — 임베딩 모델(`HuggingFaceEmbeddings`, e5 계열)과 Claude(`ChatAnthropic`)를 만드는
    유일한 곳. `to_passage`/`to_query`는 e5 모델이 요구하는 접두사를 붙인다 — 저장할 때와 검색할
    때 접두사가 다르므로 반드시 짝 맞춰 써야 한다.

- **`app/features/`** — `app/core/`와 `pipeline/`을 엮어 실제 기능(검색·설명·채팅)을 제공하는 창구 계층.
  - `pipeline_api.py` — `pipeline/`의 각 단계를 순서대로 호출하는 통합 창구. `search(query)` 하나가
    외부(서버)에 노출되는 메인 진입점이다. 무거운 준비물(회원 벡터, 지역 점수)은 `get_ready()`가 처음
    호출될 때만 만들고 캐시한다. `recommend_by_weights()`는 검색어 없이 슬라이더 값만으로 TOP 5를
    뽑을 때 쓴다.
  - `region_explain.py` — TOP 5 전체가 아니라 지도에서 클릭한 동네 하나만, 실제 시설 이름을 근거로
    들어 설명하는 별도 LLM 호출. 같은 (동네, 검색어) 조합은 `region_explain_cached()`가 메모리 딕셔너리에
    캐시해 재호출을 막는다(서버 재시작 시 사라지는 휘발성 캐시).
  - `chat.py` — 추천을 받은 뒤 사용자가 이어서 묻는 후속 질문에 답한다. TOP 5 동네 전체의 지표 점수와
    시설 개수/분류를 컨텍스트로 넣어 Claude에게 넘긴다(`region_explain.py`와 달리 어느 동네를 물을지
    미리 모르기 때문). `history` 인자는 아직 안 쓰지만 나중에 대화 저장 기능을 붙일 자리로 남겨둔 것.

- **`pipeline/`** — DB를 만들고 채우고, 검색어를 추천 결과로 바꾸는 실제 로직.
  1. `schema.py` — `data/*.csv`를 훑어 칸 타입(`INTEGER`/`FLOAT`/`DATE`/`TEXT`)과 PK/FK를 추론한 뒤
     SQLite DB를 통째로 새로 만든다. 파일명 접두어(`kb_`, `member_persona`, `nemotron` 등)로 어떤
     CSV를 표로 만들지 걸러낸다.
  2. `sample_kb.py` — `seoul_persona_full.csv.gz`(18.5만 명)에서 구마다 100명씩 층화 추출 →
     `kb_persona.csv` (지식베이스용, 2,500명).
  3. `chunk_kb.py` — 페르소나 서술형 칸들(`CHUNK_COLUMNS`)을 문장 단위 청크로 쪼갬 → `kb_chunk.csv`.
  4. `embed_kb.py` — 청크를 임베딩해 `kb_chunk` 테이블(vector 칸은 JSON 문자열)에 저장.
  5. `embed_member.py` — `nemotron.csv` 앞 100명을 회원(`C001`~`C100`)으로 취급해 같은 방식으로
     청킹·임베딩 → `member_chunk` 테이블.
  6. `search_kb.py` — 저장된 벡터로 코사인 유사도(정규화되어 있어 내적으로 계산) 검색. 단독 CLI로도
     쓸 수 있음.
  7. `weights.py` — 검색어 → 7개 지표 가중치. **두 신호를 섞는다**: (B) Claude가 검색어를 읽고 만든
     가중치 초안 + persona 묘사 문장, (A) 그 persona 문장과 벡터 유사도가 높은 회원들의 실제
     가중치 평균. `CLAUDE_RATIO`(기본 0.7)로 blend. 검색어("장소")와 회원 벡터("사람 묘사")는
     성격이 달라 그대로 비교하면 안 되므로, Claude가 만든 persona_query로 바꿔서 검색한다는 점이 핵심.
  8. `recommend.py` — 가중치 → TOP 5. 밀도 원값을 그대로 곱하면 단위가 제각각이라, 모든 지표를
     427개 동 중 백분위(0~100)로 바꾼 뒤 가중합한다. 절대점수만 쓰면 "골고루 높은 동네"가 항상
     이기므로, `build_relative`로 "그 동네 안에서 이 지표가 상대적으로 강점/약점인 정도"도 같이
     반영한다(`mix` 파라미터로 절대/상대 비율 조절). `sharpen` 지수로 가중치 편차를 증폭해 사용자가
     중시한 지표가 실제로 순위를 좌우하게 만든다.
  9. `explain.py` — TOP 5 + 지표 점수 + 지식베이스에서 찾은 유사 사례를 Claude에게 넘겨 사람이 읽을
     설명문을 받는다. 프롬프트에서 "데이터에 있는 숫자만 쓰라"고 강하게 제한해 숫자 환각을 막는다.

### 데이터 흐름 요약

```
CSV(data/) → schema.py → SQLite(life.db)
                              ↑
kb_persona.csv → chunk_kb.py → kb_chunk.csv → embed_kb.py → kb_chunk 테이블
nemotron.csv ──────────────────────────────→ embed_member.py → member_chunk 테이블

검색어 → weights.py(가중치) → recommend.py(TOP 5) → explain.py(설명문)
       └─ app/features/pipeline_api.py.search() 가 이 셋을 순서대로 호출

추천 결과 클릭/후속 질문 → app/features/region_explain.py(동네 하나 설명) /
                          app/features/chat.py(후속 질문 답변)
```

### 도메인 규칙 (코드 곳곳에 흩어져 있어 놓치기 쉬움)

- **7개 지표**는 `config.py`의 `INDICATORS = ["녹지","안전","교통","상권","의료","교육","문화"]`가
  유일한 정의처다. `user_preferences` 테이블 칸 이름이자 `recommend.py`의 `INDICATOR_COLUMNS` 키와
  반드시 일치해야 한다.
- **임베딩 모델은 저장/검색 시 반드시 동일해야 한다** (`EMBED_MODEL`, 현재 `intfloat/multilingual-e5-small`,
  차원 384). 모델을 바꾸면 이미 저장된 벡터를 전부 다시 만들어야 한다.
- **e5 접두사 규칙**: 저장할 문서는 `passage:`, 검색 질의는 `query:`를 붙인다 (`to_passage`/`to_query`).
- 행정동 이름 표기가 파일마다 다르다 (`고덕제1동` vs `고덕1동`). `db.py`의 `dong_variants()`가 양방향
  변형(제N동 제거 / 제N동 삽입)을 모두 만들어 시도한다. 함수 docstring은 `홍제1동 → 홍1동` 같은
  오류 때문에 반대 방향은 일부러 안 만든다고 설명하지만, 실제 코드는 두 방향 다 만들고 있어 docstring과
  코드가 어긋난 상태다 — 이 부분을 신뢰하지 말고 코드를 직접 볼 것.

## Data directory

`data/`는 git으로 추적하지 않는다(`.gitignore`). CSV들과 `data/life.db`가 실제로 채워져 있다
(`life.db`는 `schema.py`로 적재된 실제 DB, 현재 약 227MB). `data/`의 구체적인 스키마·칸 이름·행 수를
가정하지 말고, 필요하면 직접 열어서 확인할 것 — 파일 구성이 바뀔 수 있다.
