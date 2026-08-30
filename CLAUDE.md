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

### 실행은 반드시 프로젝트 루트에서 `-m`으로

전 파일이 `from app.core.xxx import ...` / `from app.features.xxx import ...` 형태로 통일돼 있어
**프로젝트 루트가 sys.path에 있기만 하면** `app.core.*`, `app.features.*`, `pipeline.*` 모두 resolve된다
(`app/`은 `__init__.py` 없는 네임스페이스 패키지). 예: `python -m pipeline.schema`,
`python -m app.features.pipeline_api`.

**파일 경로로 직접 실행하면 안 된다**: `python pipeline/schema.py`는 `ModuleNotFoundError: No module
named 'app'`로 즉시 실패한다 — `-m` 없이 실행하면 프로젝트 루트가 sys.path에 안 잡히는 파이썬의 일반
동작이므로, 스크립트를 돌려달라는 요청이 오면 항상 `python -m <점경로>` 형태로 실행할 것.

### `config.py`의 루트 계산 — 재발 이력이 있는 파일

`BASE_DIR = Path(__file__).resolve().parents[2]`로 프로젝트 루트를 가리킨다(`DATA_DIR` =
`BASE_DIR / "data"`, `DB_PATH` = `DATA_DIR / "life.db"`). `DB_PATH`가 없을 때 알림만 찍고 죽지는
않는다.

**주의 — 머지로 두 번 깨졌던 이력이 있다.** 브랜치 머지 과정에서 옛 변수명(`ROOT`)을 참조하는 줄과
새 이름(`BASE_DIR`)이 한 파일에 같이 남아 `import app.core.config`만 해도 `NameError`가 난 적이
있다(2026-08-30 재현·수정, 현재는 정리됨). 이 파일은 프로젝트 거의 모든 모듈이 import하므로, 파일
경로 문제처럼 보이는 에러가 나면 먼저 `python -c "import app.core.config"` 단독으로 돌려서 이 파일
자체가 깨진 게 아닌지부터 확인할 것 — 머지할 때마다 재발할 수 있는 유형이다.

## Architecture

### 계층 분리: `app/core/` (조회 인프라) vs `app/features/` (기능 창구) vs `pipeline/` (파이프라인)

- **`app/core/`** — 이미 만들어진 SQLite DB에서 데이터를 "꺼내기만" 하는 인프라 계층.
  - `config.py` — 경로, `ANTHROPIC_API_KEY`, 모델 이름, 7개 지표 이름(`INDICATORS`), 페르소나
    청킹 대상 칸(`CHUNK_COLUMNS`) 등 전역 설정.
  - `db.py` — SQLite 조회 함수 모음. **두 종류의 표를 각자 다른 목적으로 조회한다**: (1) `region_densities`,
    `region_extras`, `to_percentile`은 전부 `master_dataset_v3`(427개 행정동 × 62칸 집계 표) 하나만
    쿼리한다 — 슬라이더 7개 지표와 백분위 계산의 유일한 소스. (2) `facilities`, `facility_counts`,
    `facility_categories`는 `FACILITY_TABLES`(문화시설_개별_행정동매칭·의료_전처리·학원_전처리·
    서울시_25개구_도시공원정보_통합_행정동포함·대규모점포_전통시장_통합_최종, 총 5개)를 각각 조회해
    시설 "이름" 단위 목록을 꺼낸다 — `region_explain.py`가 근거로 드는 실제 시설명이 여기서 나온다.
    이 둘을 헷갈리면 안 된다: 밀도·순위 계산은 master_dataset_v3, 시설명 나열은 FACILITY_TABLES.
    회원/지식베이스 벡터·가중치 조회(`member_chunks`, `member_weights`, `kb_chunks`)도 담당한다.
    행정동 이름 표기 변형은 `dong_variants()`가 처리하는데,
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
    외부(서버)에 노출되는 메인 진입점이다. 무거운 준비물(회원 벡터, kb 벡터, 지역 점수)은 `get_ready()`가
    처음 호출될 때만 만들고 캐시한다(`member_rows/vectors`, `kb_rows/vectors`, `names/scores/relative`).
    임베딩 모델(`get_embedder()`)도 여기서 미리 한 번 올려서 첫 검색자만 로딩 비용을 떠안지 않게 한다.
    `recommend_by_weights()`는 검색어 없이 슬라이더 값만으로 TOP 5를 뽑을 때 쓴다.
  - `region_explain.py` — TOP 5 전체가 아니라 지도에서 클릭한 동네 하나만, 실제 시설 이름을 근거로
    들어 설명하는 별도 LLM 호출. 같은 (동네, 검색어) 조합은 `region_explain_cached()`가 메모리 딕셔너리에
    캐시해 재호출을 막는다(서버 재시작 시 사라지는 휘발성 캐시).
  - `chat.py` — 추천을 받은 뒤 사용자가 이어서 묻는 후속 질문에 답한다. TOP 5 동네 전체의 지표 점수와
    시설 개수/분류를 컨텍스트로 넣어 Claude에게 넘긴다(`region_explain.py`와 달리 어느 동네를 물을지
    미리 모르기 때문). `history` 인자는 아직 안 쓰지만 나중에 대화 저장 기능을 붙일 자리로 남겨둔 것.

- **`pipeline/`** — DB를 만들고 채우고, 검색어를 추천 결과로 바꾸는 실제 로직.
  1. `schema.py` — `data/*.csv`를 훑어 칸 타입(`INTEGER`/`FLOAT`/`DATE`/`TEXT`)과 PK/FK를 추론한 뒤
     SQLite DB를 통째로 새로 만든다. `EXCLUDE_PREFIX`(`kb_`, `member_persona`, `user_preferences_v`,
     `nemotron`)로 시작하는 파일명은 표로 만들지 않는다. `TABLE_ALIAS`가 파일 stem을 표 이름으로
     바꿔치기한다 — 지금은 `customers_v2.csv` → `customers` 표 하나뿐(버전 접미어를 뗀 이름으로
     저장하기 위함). `MANUAL_FKS`로 `customers.(city, city_dong)` → `master_dataset_v3.(구, 행정동명)`
     FK를 수동 지정해 둔다(자동 추론이 못 잡는 관계).
  2. `sample_kb.py` — `seoul_persona_full.csv.gz`(18.5만 명)에서 구마다 100명씩 층화 추출 →
     `kb_persona.csv` (지식베이스용, 2,500명).
  3. `chunk_kb.py` — 페르소나 서술형 칸들(`CHUNK_COLUMNS`)을 청크로 쪼갬 → `kb_chunk.csv`. **정정:
     실제로는 문장 단위로 나누지 않는다** — 칸 하나(예: `persona`)의 텍스트를 길이(`MIN_LENGTH`=20자)만
     넘으면 통째로 청크 하나로 만든다(코드 직접 확인함). 상한선(최대 길이)도 없다. 지금 데이터
     기준으로는 실측(`intfloat/multilingual-e5-small`의 512토큰 한도 대비 최대 157토큰)해 본 결과
     잘리는 사례가 없어 당장 문제는 아니지만, 페르소나 서술이 훨씬 길어지는 방향으로 데이터가
     바뀌면 512토큰을 넘는 칸이 조용히 잘려서 임베딩될 수 있다 — 그땐 이 함수에 2차 분할을 추가해야 함.
  4. `embed_kb.py` — 청크를 임베딩해 `kb_chunk` 테이블에 저장. `BATCH_SIZE`(32) 단위로 나눠 배치마다
     commit하고 진행률을 출력하며, 이미 들어간 만큼은 건너뛰고 이어서 진행한다(`__main__`의
     `done`/`rows[done:]`). vector 칸은 `BLOB`(float32 `.tobytes()`) — 예전엔 JSON 문자열(`TEXT`)로
     저장해 `life.db`가 3배 이상 컸었는데 BLOB 전환으로 해결함(직접 확인함, 2026-08-30). **dtype을
     반드시 float32로 고정할 것** — float64로 잘못 읽으면 384차원이 192차원으로 깨진다.
  5. `embed_member.py` — `nemotron.csv` 앞 100명을 회원(`C001`~`C100`)으로 취급해 `embed_kb.py`와
     완전히 같은 방식(배치 처리, BLOB 저장)으로 청킹·임베딩 → `member_chunk` 테이블. `SOURCE`가 여전히
     `nemotron.csv`를 가리키므로, 이 파일이 로컬 `data/`에 있는지부터 확인할 것(git엔 없음 — 아래
     "Data directory" 참고).
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
     `find_cases(persona_query, rows, vectors, top_k)`는 kb 벡터를 인자로 받는다 — 예전엔 함수
     안에서 매 요청마다 `kb_chunks()`로 22,500개를 다시 읽고 다시 파싱해 3.5초씩 걸렸는데(비율로
     따지면 실제 유사도 계산의 2,200배), `load_kb_vectors()`로 로딩을 분리해 `pipeline_api.get_ready()`가
     한 번만 만들어 캐시하도록 고쳤다(직접 확인함). `search_kb.py`, `weights.py`도 벡터를 읽을 때
     전부 `np.frombuffer(r["vector"], dtype="float32")`를 쓴다 — `kb_chunk`/`member_chunk` 어느
     쪽이든 vector 컬럼을 읽는 곳은 이 방식으로 통일돼 있어야 하며, 한 곳이라도 `json.loads`로
     남아 있으면 그 즉시 깨진다(BLOB 컬럼에 문자열이 아니라 진짜 바이트가 들어있으므로).

### 데이터 흐름 요약

```
master_dataset_v3.csv, customers_v2.csv, 개별 시설 CSV들 → schema.py → SQLite(life.db)

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
  `to_passage`/`to_query`는 `app/core/llm.py`에만 정의돼 있고 `embed_kb.py`/`embed_member.py`는
  그걸 import해서 쓴다 — 예전엔 세 파일이 각자 똑같은 함수를 중복 정의하고 있었다(정상 동작은
  했지만 나중에 모델을 e5 계열 아닌 걸로 바꿀 때 한 곳만 고치고 나머지를 빠뜨리기 쉬운 구조였음).
- **벡터는 `BLOB`(float32 raw bytes)로 저장한다.** `kb_chunk`/`member_chunk` 둘 다 마찬가지다.
  저장은 `np.asarray(vec, dtype="float32").tobytes()`, 읽기는 `np.frombuffer(v, dtype="float32")`로
  반드시 짝을 맞춰야 한다 — dtype이 어긋나면 384차원이 조용히 192차원으로 잘못 해석되는데 에러가
  안 나서 찾기 매우 힘들다.
- 행정동 이름 표기가 파일마다 다르다 (`고덕제1동` vs `고덕1동`). `db.py`의 `dong_variants()`가 양방향
  변형(제N동 제거 / 제N동 삽입)을 모두 만들어 시도한다. 함수 docstring은 `홍제1동 → 홍1동` 같은
  오류 때문에 반대 방향은 일부러 안 만든다고 설명하지만, 실제 코드는 두 방향 다 만들고 있어 docstring과
  코드가 어긋난 상태다 — 이 부분을 신뢰하지 말고 코드를 직접 볼 것.

## Data directory

`data/`는 git으로 추적된다(`.gitignore`에 `data/` 항목 없음). `.gitattributes`가 `*.db`, `*.csv.gz`,
`nemotron.csv`를 Git LFS 대상으로 지정한다.

**gotcha — 로컬 `life.db`가 133바이트짜리 LFS 포인터 텍스트일 수 있다 (지금 이 상태다, 2026-08-30
확인).** `git lfs pull`을 안 하면 체크아웃 시 실제 DB 바이너리 대신 `version https://git-lfs.../oid
sha256:.../size ...` 형태의 포인터 파일이 남는다. 이 상태에서 `sqlite3.connect(DB_PATH)`는 에러
없이 열리는 것처럼 보이다가 실제 쿼리 시점에 `sqlite3.DatabaseError: file is not a database`가 난다.
DB 관련 이상 동작을 볼 때는 `data/life.db` 파일 크기부터 확인할 것 — 정상이면 BLOB 전환 후
~70MB대, 100바이트대면 포인터 상태이므로 `git lfs pull`이 필요하다.

**핵심 표는 `master_dataset_v3.csv`(427개 행정동 × 62칸)와 `customers_v2.csv`(회원 100명,
`schema.py`의 `TABLE_ALIAS`로 `customers` 표가 됨) 둘로 통합돼 있다.** `db.py`의 밀도·백분위 조회는
전부 `master_dataset_v3` 하나만 보고(위 Architecture 절 참고), 나머지 개별 시설 CSV(문화시설·의료·
학원·공원·대규모점포)는 시설 "이름" 목록용으로 별도 유지된다. `시세_면적구간별.csv`, `시세_지역별.csv`
(부동산 시세)는 아직 `master_dataset_v3`에도 다른 코드에도 안 엮여 있다 — 읽거나 지표에 반영하는
코드가 없으므로 존재를 가정하지 말 것.

**`data/nemotron.csv`(약 460MB), `data/seoul_persona_full.csv.gz`(약 235MB)는 로컬에 있지만 git에는
커밋돼 있지 않다** (`git status`에 `??`로 뜸 — untracked, gitignore 대상도 아님). 즉
`pipeline/embed_member.py`, `pipeline/sample_kb.py`는 지금 로컬에서는 정상 실행되지만, 이 두 파일이
커밋되지 않은 상태로 남아 있다는 걸 인지하고 있을 것 — 다른 환경(새 클론, CI)에는 없을 수 있다.

`data/`의 나머지 구체적인 스키마·칸 이름·행 수를 가정하지 말고, 필요하면 직접 열어서 확인할 것 —
파일 구성이 자주 바뀐다.

### 성능 최적화 기록

`STUDY.md`(루트)에 과거 성능 진단 [A]~[E] 다섯 항목을 어떻게 고쳤는지가 정리돼 있다: [A] find_cases
캐싱, [B] 벡터 BLOB 전환, [C] to_passage 통일, [D] BATCH_SIZE 활용, [E] 임베딩 모델 선로딩 — 다섯
항목 모두 코드에 반영 완료된 상태다. 진단 원본이었던 `엔진_성능진단_및_최적화방안.txt`는 루트에서
삭제됐다(더 이상 없음). `STUDY.md`의 "진행 상황" 절은 [B][D]를 "아직 안 건드림"이라고 적은 채 갱신
안 됐으니 그 서술은 신뢰하지 말 것.
