# ADR-0001: FastAPI 서버를 Life-Embed-jh로 옮기고 Life-Web은 httpx로 호출

- **Status**: Accepted (2026-09-08)
- **Context**

  `Life-Web`이 `sys.path`로 `Life-Embed-jh`를 직접 import해서 같은 프로세스·같은
  이벤트 루프에서 돌리고 있었다. 판단 축은 두 개였다.

  | 축 | 기준 | 지금 LifeFit |
  |---|---|---|
  | ① 호출자 수(확장성) | 여러 클라이언트가 부르나 | `Life-Web` 하나뿐 |
  | ② 의존성/배포 격리 | 무거운 라이브러리·다른 배포 주기가 필요한가 | `sentence-transformers`, `langchain-anthropic` 보유. `Life-Web`과 같은 프로세스에서 돎 |

  ①만 보고 "호출자 하나니까 지금 구조가 맞다"고 결론 내리는 건 ②를 무시한 것이었다.
  임베딩 모델 로딩·동기 추론이 FastAPI 이벤트 루프를 막아 인증·CRUD 요청과 같은
  프로세스를 다투는 문제는 "언젠가 스케일링이 필요할 수 있다"는 미래형 베팅이 아니라
  지금 바로 재현·측정 가능한 문제였다 — 이게 ①보다 훨씬 단단한 근거였다.

- **Decision**

  `Life-Embed-jh`에 자체 FastAPI 서버(`app/api/*.py` + `app/schemas/*.py`, 8000번
  포트)를 신설한다. `Life-Web`은 `sys.path` import 대신 `httpx.Client`(커넥션
  재사용, `EMBED_API_BASE` 환경변수로 주소 지정)로 호출한다. 기존 함수 계약(이름·
  인자·반환값·예외)은 그대로 두고 전달 방식만 함수 호출 → HTTP로 바꾼다 —
  `Life-Web/routers/*.py`는 수정할 필요가 없게 `services/engine.py` 안에서만 흡수한다.

  예외 → HTTP 변환 규칙: "없음"은 함수 반환값 `None` → HTTP 404, 값 검증 실패
  (`InvalidPatch`)는 HTTP 422, `app.features.analysis.ask()`처럼 예외 대신
  `{"error": ...}` dict를 돌려주던 기존 계약은 라우터가 감지해 422로 바꾸고
  `Life-Web` 쪽 httpx 클라이언트가 다시 원래의 dict 모양으로 복원한다(둘 다 바뀌면
  안 깨진다).

- **Consequences**
  - 긍정: 독립 배포·스케일링 가능, 이벤트 루프 경합 해소, 엔진 교체 계약
    (`Life-Web/services/engine.py` 한 파일만 고치면 됨) 유지.
  - 부정: 로컬 개발 시 uvicorn 프로세스 2개(5000, 8000)를 각각 띄워야 함, CORS
    설정 필요, 단순 조회 엔드포인트에 밀리초 단위 지연 추가(재검토 트리거는
    REFACTOR.md 8번 참고), 예외→HTTP 변환 계층이 각 라우터마다 필요.
  - 알려진 한계(이번 결정과 무관, 별도 이슈): 이 환경에서 임베딩 모델
    (`app.llm.get_embedder()`, sentence-transformers/torch)을 타는 경로
    (`/search`, `/survey/recommend`, `/admin/members/{id}/preview`·`/similar`)가
    세그폴트를 일으킨다. FastAPI/httpx 코드 문제가 아니라 로컬 환경 문제로 확인됨.

- **References**: `docs/REFACTOR.md` (전체 논의 기록), `Life-Web/AGENTS.md` Architecture 절
