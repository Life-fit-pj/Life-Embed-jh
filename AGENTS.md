# AGENTS.md

<!-- agents.md 공개 스펙 파일. Claude Code 외 다른 AI 코딩 도구(Cursor, Codex, Aider, Gemini CLI 등)도 이 파일을 읽는다.
     이 저장소에서는 "도구 무관 공통 지침"만 여기 쓰고, Claude Code 전용 사항은 CLAUDE.md에 남긴다. -->

## Project overview

**LIFE,FIT** — 서울 427개 행정동 중 사용자의 자연어 검색어(예: "애들 학원 보내기 좋은 곳")에 맞는 동네
TOP 5를 추천하고, LLM(Claude)이 근거를 들어 설명해주는 서비스의 백엔드 파이프라인이다.
`src/`, `docu/DESIGN.md`는 여전히 비어 있다. 실제 코드는 `app/core/`(조회 인프라), `app/features/`
(검색·설명·채팅 창구), `pipeline/`(DB 적재·추천 로직) 세 곳에 있다.

프레임워크·빌드·린트·테스트 도구를 정의하는 매니페스트(`requirements.txt`, `pyproject.toml` 등)가 없다.
검증은 각 파일 하단의 `if __name__ == "__main__":` 블록을 직접 실행해 눈으로 확인하는 방식으로 이루어진다.

## Setup / commands

> 전부 **저장소 루트**에서 `-m` 모듈 형태로 실행한다 (`app/`이 `__init__.py` 없는 네임스페이스
> 패키지라 루트가 sys.path에 있어야 `app.*`/`pipeline.*`이 resolve됨). 파일 경로로 직접 실행
> (`python pipeline/schema.py`)하면 `ModuleNotFoundError: No module named 'app'`로 실패한다.
>
> `.env`에 `ANTHROPIC_API_KEY` 필요 — 없으면 `app/core/config.py`가 import 시점에 RuntimeError.
>
> **적재 파이프라인 (data/*.csv → data/life.db, 벡터 테이블)**
> python -m pipeline.schema          # CSV 훑어 칸 타입 추론 -> life.db 통째로 재생성
> python -m pipeline.sample_kb       # seoul_persona_full.csv.gz -> kb_persona.csv (구별 100명 층화추출)
> python -m pipeline.chunk_kb        # kb_persona.csv ->칸 청킹)
> python -m pipeline.embed_kb        # kb_chunk.csv -> kb_chunk 테이블 (임베딩, BLOB 저장)
> python -m pipeline.embed_member    # nemotron.csv 앞 100명 -> member_chunk 테이블
> python -m pipeline.search_kb       # 저장된 벡터로 코 버깅용)
>
> **추천 파이프라인 (검색어 -> TOP 5 -> 설명문)**
> python -m app.features.pipeline_api  # search(query)
> python -m app.engine.weights         # 검색어 -> 7개 지표 가중치만 떼어 확인
> python -m app.engine.recommend       # 가중치 -> TOP 5만 떼어 확인
> python -m app.engine.explain         # TOP 5 -> 설명문
>
> 이 저장소엔 서버가 없다 — 별도 sibling 저장소 `Life-Web`이 `sys.path`로 이 엔진을 import해서
> `uvicorn main:app --reload`로 띄운다 (이 저장소가 아니


## Code style

디자인패턴을 준수하고, 파일에서 정해진 역할외에 의존성을 어기지않는 코드 설계를 한다.
함수 인자값에는 자료형을 명시하고 (doc : str), 핵심 주석을 간단 명료하게 작성한다.
코드 네이밍을 규격화하고 모두가 읽기 편한 방식으로 구조를 설계한다.
<!-- 이 저장소에서 지키는 코드 스타일/컨벤션. -->

## Testing instructions

데이터 정합성을 검사하며, 사용자 쿼리에 따른 응답의 질을 높히는 것을 목표로한다.
청킹과 임베드 품질 향상에 중점을 두어 테스트를 통해 개선한다.
<!-- 테스트가 있다면 실행 방법과 통과 기준. -->

## Security considerations

API, Key 등 민감정보가 포함된 데이터는 .env폴더에서 별도로 관리하며, 외부로 노출시키지 않는다.
<!-- 예: selectory.db는 더미 데이터라 민감정보 없음, API 키/자격증명 다루는 부분이 생기면 여기 추가. -->

## Commit / PR guidelines

사용자가 직접 git 에 접근하며, Agent는 Commit, Push는 하지않는다.
<!-- 커밋 메시지 컨벤션(예: 이 repo의 "fix :", "feat :" 접두사 패턴), PR 규칙. -->

## Architecture

> ```
> app/core/       config.py, db.py               설정 + SQLite 연결/조회 (조회 함수 전부 여기 모여 있음)
> app/adapters/   stores/llm.py                   외부 모델 어댑터 — 임베딩(e5-small)·LLM(Claude) 생성을
>                                                  LangChain으로 감쌈. 모델 교체는 이 파일만 고치면 됨
> app/engine/     weights.py, recommend.py,       검색어 -> 가중치 -> TOP 5 -> 설명문 알고리즘.
>                 explain.py, housing.py,          housing.py는 7개 지표와 별개로 시세 조건(건물유형·
>                 resync.py                        거래유형·목표가) 필터. resync.py는 회원/페르소나
>                                                  한 명만 통짜로 재임베딩(관리자 수정 직후 반영용)
> app/features/   pipeline_api.py,                 위 계층을 엮는 진입점. search()가 메인 API,
>                 region_explain.py, chat.py       region_explain/chat이 클릭·후속질문 응답
> pipeline/       schema.py, sample_kb.py,         CSV -> life.db와 벡터 테이블을 만드는 적재
>                 chunk_kb.py, embed_kb.py,         파이프라인. 배포에는 안 따라감. io.py(CSV 읽기/
>                 embed_member.py, search_kb.py,   쓰기), prep/chunking.py(청킹 로직)도 여기 소속
>                 io.py, prep/chunking.py
> ```
> ```

## Logging

모든 로그로 사용할 수 있는 데이터들은 logs 폴더에 적재한다.


### Data Flow Summary

```
master_dataset_v3.csv, customers_v2.csv, 개별 시설 CSV들 → schema.py → SQLite(life.db)

kb_persona.csv → chunk_kb.py → kb_chunk.csv → embed_kb.py → kb_chunk 테이블
nemotron.csv ──────────────────────────────→ embed_member.py → member_chunk 테이블

검색어 → weights.py(가중치) → recommend.py(TOP 5) → explain.py(설명문)
       └─ app/features/pipeline_api.py.search() 가 이 셋을 순서대로 호출

추천 결과 클릭/후속 질문 → app/features/region_explain.py(동네 하나 설명) /
                          app/features/chat.py(후속 질문 답변)
```

### Domain Rule

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


### Optimaze History

`STUDY.md`(루트)에 과거 성능 진단 [A]~[E] 다섯 항목을 어떻게 고쳤는지가 정리돼 있다: [A] find_cases
캐싱, [B] 벡터 BLOB 전환, [C] to_passage 통일, [D] BATCH_SIZE 활용, [E] 임베딩 모델 선로딩 — 다섯
항목 모두 코드에 반영 완료된 상태다. 진단 원본이었던 `엔진_성능진단_및_최적화방안.txt`는 루트에서
삭제됐다(더 이상 없음). `STUDY.md`의 "진행 상황" 절은 [B][D]를 "아직 안 건드림"이라고 적은 채 갱신
안 됐으니 그 서술은 신뢰하지 말 것.
