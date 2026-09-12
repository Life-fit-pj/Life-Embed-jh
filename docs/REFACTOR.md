# REFACTOR — Life-Embed-jh / Life-Web 계층 재정비

작업 기록. 결정 사항과 아직 안 끝난 논의를 구분해서 남긴다.
참고자료: `day1.html` 튜토리얼 문서(계층 설명), `RAG-learn` 예제 프로젝트(실제 코드),
`dev-data-embed` 프로젝트(예외→HTTP 변환 패턴) — 전부 이 워크스페이스 밖의 로컬 자료라
경로는 기록하지 않는다.

## 1. 시작한 이유

`RAG-learn`처럼 백엔드/프론트 구조와 계층을 분리하는 리팩토링을 하려 했다.
day1.html의 계층 정의:

```
api/            받는다   주소·상태 코드만. 일은 안 한다
services/       시킨다   업무 로직. 중심
repositories/   꺼낸다   DB 조회·저장
models/         DB 모양 (계층 아니고 재료)
schemas/        바깥 모양 (계층 아니고 재료)
```

## 2. 첫 진단 — 계층 비교 결과 (전제 뒤집힘)

처음엔 "Life-Embed-jh(엔진, FastAPI 없음) vs Life-Web(FastAPI+프론트)"인 줄 알았는데,
확인해보니 FastAPI/uvicorn은 **Life-Web에만** 있다 (`Life-Embed-jh/requirements.txt`엔 없음,
`Life-Embed-jh/AGENTS.md`에 "이 저장소엔 서버가 없다"고 명시).

- **Life-Embed-jh** — `domain → core → tables/llm → engine → features` 5계층,
  `tests/test_layers.py`가 import 그래프를 AST로 검사해서 자동으로 위반을 잡는다.
  RAG-learn의 3계층보다 이미 더 엄격하다. **손대지 않기로 함.**
- **Life-Web** — `routers/`(=api) · `services/`(=services)는 이미 있음. 빈 구멍은
  **schemas 계층**: pydantic 요청 모델이 `routers/*.py` 안에 인라인으로 있음
  (`PredictRequest`, `LoginRequest`, `SurveyRequest` 등). `repositories/`·`models/`는
  Life-Web이 DB를 직접 소유하지 않으므로(엔진 쪽 `life.db`가 원본) 도입 안 함.

**원래 계획(보류됨)**: Life-Web에 `schemas/` 신설, `routers/*.py`의 pydantic 모델을 이동.
1단계 예시로 `routers/recommend.py`의 `PredictRequest`/`RegionRequest`/`ChatRequest` →
`schemas/recommend.py` 초안까지 작성했었음 — 아래 3번 결정으로 순서가 바뀌어 보류.

## 3. 방향 전환 — FastAPI를 어느 쪽에 둘 것인가

`routers/`가 필요 없지 않냐는 질문에서 시작해, "서버가 Life-Embed-jh에 있어야 하는 거
아니냐"는 논의로 이어짐. 판단 축은 두 개.

| 축 | 기준 | 지금 LifeFit |
|---|---|---|
| ① 호출자 수(확장성) | 여러 클라이언트가 부르나 | `Life-Web` 하나뿐 → 이 축만 보면 라이브러리로 합쳐도 됨 |
| ② 의존성/배포 격리 | 무거운 라이브러리·다른 배포 주기가 필요한가 | `sentence-transformers`, `langchain-anthropic` 보유. 지금 `Life-Web`과 같은 프로세스에서 돎 |

①만 보고 "호출자 하나니까 지금 구조가 맞다"고 결론 내렸던 게 **틀렸음** — ②를 무시한 것.
`Life-Embed-jh/app/llm.py:9-12`에 이미 "모델 로딩 몇 초 걸린다"는 인지가 있고, 지금은
싱글턴(`_embedder`)으로 **재로딩만** 막아둔 상태. 안 풀린 문제: 배포 이미지에 무거운
의존성이 같이 실림 + 동기 임베딩 추론이 FastAPI 이벤트 루프를 막아 인증·CRUD 요청과
같은 프로세스를 다툼.

**이 문제는 "언젠가 스케일링이 필요할 수 있다"는 미래형 베팅이 아니라, 지금 바로
재현·측정 가능한 문제** — 이게 확장성 근거보다 훨씬 단단한 근거.

**결정: `Life-Embed-jh`에 자체 FastAPI 서버를 신설하고, `Life-Web`은 `sys.path` import
대신 HTTP(`httpx`)로 호출한다.**

## 4. ADR-0001 (요약, 원본은 `Life-Embed-jh/docs/adr/0001-move-fastapi-to-embed.md`)

- **Status**: Proposed
- **Context**: 위 3번 내용
- **Decision**: 위 3번 결정
- **Consequences**
  - 긍정: 독립 배포·스케일링 가능, 이벤트 루프 경합 해소, 엔진 교체 계약(`services/engine.py`
    한 파일만 고치면 됨) 유지
  - 부정: 로컬 개발 시 프로세스 2개 동시 기동, CORS 신규 필요, 단순 조회 엔드포인트에
    밀리초 단위 지연 추가(아래 6번 트리거 참고), 예외→HTTP 변환 계층 필요(→ 5번에서 해결)
- **References**: `dev-data-embed/app/api/errors.py`, `docs/REFERENCES.md:30`

## 5. API 계약 (엔드포인트 목록)

`Life-Web/services/engine.py`가 지금 `Life-Embed-jh`에서 직접 부르는 함수 20여 개를
도메인별로 묶은 것. 상세 요청/응답 필드는 코드 작성 단계에서 확정.

| 도메인 | 원본 함수 | 엔드포인트 |
|---|---|---|
| 추천 | `search` | `POST /search` |
| | `recommend_by_weights` | `POST /recommend` |
| | `recommend_by_weights_explained` | `POST /recommend/explained` |
| 동네 설명/대화 | `facility_counts`+`facilities`+`region_extras` | `GET /regions/{gu}/{dong}/facilities` |
| | `region_explain_cached` | `POST /regions/{gu}/{dong}/explain` |
| | `chat` | `POST /chat` |
| 회원/설문 | `customer_one` | `GET /customers/{customer_id}` |
| | `score_survey` | `POST /survey/score` |
| | `get_survey_recommendation` | `POST /survey/recommend` |
| 인증 | `login` | `POST /auth/login` |
| | `id_exists` | `GET /auth/id-exists/{login_id}` |
| | `signup` | `POST /auth/signup` |
| 좋아요/기록 | `add_like`/`remove_like` | `POST /likes`, `DELETE /likes` |
| | `add_search_history`+`add_chat_history` 등 | `POST /history`, `GET /history/{anon_id}` |
| 관리자(마지막) | `get_member`/`list_members`/`create_member`/`update_member` | `GET/POST/PATCH /admin/members[/{id}]` |
| | `preview_member`/`similar_members`/`privacy_preview` | `GET /admin/members/{id}/preview` 등 |
| | `get_region`/`list_regions`/`update_region` | `GET/PATCH /admin/regions[/{gu}/{dong}]` |
| | `health`/`clear_caches`/`dashboard`/`recent_logs` | `GET/POST /admin/*` |
| | `backfill_logins` | `POST /admin/backfill-logins` |
| | `analysis_engine.ask/list_chats/get_chat/delete_chat` | `/admin/analysis/*` |

**고정사항**: 함수 계약 자체는 안 바뀜(전달 방식만 함수 호출 → HTTP). `search`/
`recommend_by_weights` 중 뭘 부를지 정하는 분기는 `Life-Web`(클라이언트) 쪽에 그대로
둔다 — 이번 전환은 전송 방식만 바꾸는 것. 예산 필터링은 `Life-Embed-jh` 안에서 한
번만(루트 `CLAUDE.md` 원칙).

## 6. 진행 순서

1. API 계약 확정 — **완료**
2. `Life-Embed-jh`: `requirements.txt`(`fastapi`, `uvicorn`) + `app/schemas/` + `app/api/errors.py`
3. `Life-Embed-jh`: `main.py` + `app/api/` 첫 슬라이스 — `GET /customers/{customer_id}` ← **다음 할 일**
4. 나머지 도메인 반복 — 추천 → 설명/대화 → 인증 → 설문 → 기록 → 관리자
5. `Life-Web`: `services/engine.py`를 `httpx` 클라이언트로 전환 (커넥션 재사용 — 요청마다 새로 만들지 않음)
6. 문서 갱신 — 양쪽 `AGENTS.md`, 루트 `CLAUDE.md`의 Cross-repo contract
7. ADR 저장 — 원본 `Life-Embed-jh/docs/adr/`, `Life-Web/AGENTS.md`에서 링크만(사본 금지)

## 7. 열린 질문 — SQLAlchemy 도입 여부 (미결정)

`Life-Embed-jh/app/core/db.py`는 `sqlite3`를 직접 쓴다(`connect_args` 없이
`sqlite3.connect(DB_PATH)`). `RAG-learn/app/db.py`는 SQLAlchemy로 추상화돼 있어서
`.env`의 `DATABASE_URL` 한 줄만 바꾸면 SQLite ↔ Supabase(Postgres)를 오갈 수 있다.

**아직 결정 안 됨**: 이번 FastAPI 이전 작업에 SQLAlchemy 전환을 같이 넣을지, 아니면
별도 작업으로 미룰지.

- 같이 하면: 이번에 `db.py`를 어차피 만지므로(엔드포인트마다 `app/tables/*` 호출) 나중에
  다시 손대는 걸 피할 수 있음.
- 미루면: 지금 목표(FastAPI 위치 이전)와 무관한 범위 확장 — YAGNI 위반 소지. 지금
  SQLite로 충분히 돌아가고 있고, Supabase 이전이 확정된 계획도 아님(2번 항목의 "누구나
  접속 가능한 도메인" 논의는 가정이었지 결정된 로드맵이 아님).

**다음 세션에서 결정할 것.**

## 7-2. 열린 질문 — 증분 임베딩 (미결정)

**있는 것**: `app/engine/resync.py`의 `resync_kb_person`/`resync_member` — 관리자가
한 명 수정한 직후 그 사람 청크만 지우고 다시 만든다. 이미 증분이다. 손댈 필요 없음.

**없는 것**: 배치 파이프라인(`pipeline/embed_kb.py`, `pipeline/embed_member.py`)은
재실행하면 매번 표를 통째로 지우고 처음부터 다시 만든다 — "지우고 처음부터
다시할까요? (y/n)" 프롬프트, 20~40분 소요. CSV에 새 행 몇 개만 추가돼도 전체를 다시 돌림.

**아직 결정 안 됨**: 배치 쪽에 "이미 임베딩된 id는 건너뛰고 새 것만" 로직을 넣을지.
이번 FastAPI 이전과는 다른 축(파이프라인 성능, API 설계와 무관)이라 이번 작업
범위에 넣을지 별도 작업으로 뺄지부터 정해야 함.

## 7-3. 열린 질문 — LangGraph 도입 (미결정)

**현재**: `README.md`/`STUDY.md`/`AGENTS.md` 어디에도 LangGraph 언급 없음 — 완전히
새 논의. `app/features/search.py`의 `search()`는 `weights → recommend → explain`을
그냥 순서대로 직접 호출하는 평범한 함수 체인(AGENTS.md Data Flow Summary 참고).
day1.html 기준으로 `graph/`는 계층이 아니라 "부품을 어떤 순서로 부를지 정하는 흐름"
부품 상자 — 그 자리에 해당하는 폴더가 지금 `Life-Embed-jh`엔 없음.

**아직 결정 안 됨**: 지금 체인엔 분기·재시도·툴콜이 없고 순차 호출로 잘 돈다.
LangGraph를 넣어서 얻는 게 뭔지(예: 검색 실패 재시도, 조건부 분기, 향후 도구 호출
확장)부터 확인해야 함 — 구체적 필요가 있으면 도입 근거가 서고, 없으면 지금 구조
유지가 YAGNI에 맞음. 이번 FastAPI 이전 작업과 독립적인 결정.

## 8. 재검토 트리거 (숫자는 잠정치, 모니터링 붙으면 갱신)

- `customer_one` 같은 단순 조회의 p99 지연이 브라우저에서 체감될 정도(잠정 100ms대 진입)로
  확인되면 → `Life-Web` 자체 캐시 또는 읽기 전용 DB 복제본 도입 재검토
- 두 서버가 실제로 다른 호스트/리전에 배포되거나, Supabase처럼 DB 자체가 네트워크
  너머로 이동하면 → 레이턴시 재계산 필요 (DB 홉이 지금의 마이크로초에서 수십 ms로 바뀜)
- `Life-Embed-jh` API에 `Life-Web` 외의 두 번째 호출자가 생기면 → ①(호출자 수) 축도
  같이 성립하게 되므로 지금 결정의 근거가 더 강해짐(재검토 불필요, 오히려 확인)
- 도메인을 공개(누구나 접속 가능)로 바꾸면 → `Life-Embed-jh` API에 서비스 인증 필수,
  Supabase 서비스 롤 키 노출 금지(브라우저·`Life-Web`에 전달 금지), CORS allowlist 필수
