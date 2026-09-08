# DEPLOY.md

Docker / Supabase / Vercel / Render를 이 프로젝트에 어떻게 붙일지 정리한 계획이다.
`Life-Embed-jh`·`Life-Web` 두 저장소에 걸친 내용이라 여기(엔진 저장소)에 기록한다.
작성일 2026-09-08, 아직 실행 전 — 계획 단계.

## 전체 그림

```
                    ┌─────────────┐
   브라우저  ──────▶ │   Vercel    │  Life-Web/frontend (정적, 빌드 없음)
                    └──────┬──────┘
                           │ fetch(API_BASE + "/api/...")   ← CORS
                           ▼
                    ┌─────────────┐        ┌─────────────┐
                    │   Render    │──httpx─▶│   Render    │
                    │  Life-Web   │EMBED_API│Life-Embed-jh│
                    │  (:5000역)  │  _BASE  │  (:8000역)  │
                    └──────┬──────┘        └──────┬──────┘
                           │                       │
                           └─────────┬─────────────┘
                                     ▼
                            ┌─────────────┐
                            │  Supabase   │  Postgres (life.db 대체)
                            └─────────────┘

   Docker: 위 두 Render 서비스를 담는 컨테이너 규격 (지금은 native runtime, 나중에 교체)
```

두 저장소가 지금도 독립 배포 단위(`sys.path` 직접 import 아니고 `httpx` 호출,
`docs/adr/0001-move-fastapi-to-embed.md`)라서, Render에도 하나로 합치지 않고
**서비스 2개**로 나눠 올린다.

## 담당 분리

| 영역 | 담당 | 상태 |
|---|---|---|
| Vercel(프론트 배포), Render(백엔드 배포), CORS | 나 | 계획 완료, 착수 전 |
| Docker화 | 팀원 A | R&D 중 |
| Supabase + SQLAlchemy ORM(`app/db.py`, `app/models/`) | 팀원 B | 작업 중 |

지금 당장 할 수 있는 건 Vercel·Render뿐이다. sqlite(`data/life.db`)를 그대로 두고
움직이는 걸 목표로 하고, Docker·Supabase는 아래처럼 **나중에 값만 갈아끼우면 합류되도록**
자리만 잡아둔다.

## Render — 백엔드 2개

| 항목 | Life-Embed-jh | Life-Web |
|---|---|---|
| 타입 | Web Service | Web Service |
| 지금 단계 | native Python (`buildCommand: pip install -r requirements.txt`, `startCommand: uvicorn app.main:app`) | 동일 (`uvicorn main:app`) |
| Docker 완성 후 | `render.yaml`의 `env: python` → `env: docker`로 필드만 교체 (Dockerfile만 있으면 그대로 인식) | 동일 |
| DB | 지금: Persistent Disk에 `life.db` 1회 수동 업로드 / Supabase 완성 후: `DATABASE_URL` 환경변수로 교체하고 디스크 제거 | 없음 (Life-Embed-jh 경유) |
| 필수 env | `ANTHROPIC_API_KEY`, (나중에) `DATABASE_URL` | `EMBED_API_BASE` = Life-Embed-jh의 Render 내부 URL |
| 서비스 간 통신 | — | 같은 리전이면 Render private network(`onrender.com` 내부 호스트)로 무료 통신 가능 |

`render.yaml`은 각 저장소가 자기 걸 들고 있는다 — Life-Web이 Life-Embed-jh 배포 설정까지
아는 건 계층 규칙(창구는 SQL·배포 세부를 모른다) 위반이다.

## Vercel — 프론트 1개

- 대상: `Life-Web/frontend/`만 (Life-Web FastAPI가 지금 겸하는 정적 서빙 역할을 대체).
- `vercel.json`: output directory만 `frontend`로 지정, 빌드 커맨드 없음(순수 HTML/JS/CSS).
- 환경변수 `API_BASE`(Render Life-Web URL) → `frontend/lib/api.js`가 이 값을 읽어
  지금의 `/api/...` 상대경로 앞에 붙인다. `api.js`는 지금 전부 상대경로라 그대로 두면
  Vercel에 올라간 뒤 자기 자신을 호출하게 되어 깨진다 — 이 수정이 선행돼야 한다.
- PR 프리뷰마다 도메인이 새로 생기므로 Render 쪽 CORS 허용 목록은 정확한 도메인 하나가
  아니라 `*.vercel.app` 패턴으로 열어야 프리뷰에서도 API가 붙는다.

## Supabase (팀원 B WIP) — 이 프로젝트에서의 역할만 미리 정의

- **역할**: `life.db`(SQLite) 대체 Postgres. `app/core/config.py`의 `DATABASE_URL`이
  이미 이 값을 받을 자리를 갖고 있다(지금은 미사용 `app/db.py` ORM 레이어만 봄).
- **합류 지점**: 실제 조회 경로인 `app/core/db.py`(지금 `sqlite3` 하드코딩,
  `PRAGMA table_info` 등 SQLite 전용 구문 사용)가 Postgres 드라이버로 바뀌면
  `repositories/*`가 그걸 통해 자동으로 넘어간다 — 이 레이어 경계 덕분에
  SQL을 직접 안 쓰는 다른 층(engine/features/api)은 한 줄도 안 고쳐도 된다.
- **Render와의 연결**: Supabase가 완성되면 Render 환경변수 `DATABASE_URL`만 채우고
  Persistent Disk 마운트를 빼면 끝 — 지금 Render 설정을 "DB 위치를 env var로 주입"하는
  구조로 짜두는 이유가 이거다.
- 벡터(BLOB) 저장을 `pgvector`로 바꿀지는 팀원 B 판단 영역이라 여기선 정하지 않는다.
- `pipeline/schema.py`(적재)도 `sqlite3`/`PRAGMA` 하드코딩이라 함께 손볼 대상이다.

## Docker (팀원 A R&D) — 이 프로젝트에서의 역할만 미리 정의

- **역할**: Render 배포 단위(Life-Embed-jh, Life-Web)를 컨테이너화. 로컬 개발용
  `docker-compose.yml`(워크스페이스 루트, 두 저장소 사이드바이사이드 마운트)도 겸할 수 있다.
- **합류 지점**: Render는 `render.yaml`의 `env` 필드만 `python → docker`로 바꾸면
  같은 서비스가 그대로 Dockerfile 빌드로 전환된다 — 지금 native로 먼저 올려도 나중에
  버리는 작업이 아니다.
- Life-Embed-jh는 무거운 ML 의존성(sentence-transformers 등)이 있어 이미지가 커질 수
  있다는 점만 팀원 A에게 공유하면 된다.

## Phase

| Phase | 담당 | 내용 |
|---|---|---|
| 1 | 나 | CORS 추가 + `frontend/lib/api.js`에 `API_BASE` 도입 + 두 저장소 `render.yaml` + `vercel.json` → sqlite 그대로, Render Disk에 수동 업로드 |
| 2 (병행) | 팀원 A | Docker화 → `render.yaml`의 `env` 필드 교체 |
| 3 (병행) | 팀원 B | Supabase + ORM → `app/core/db.py`를 Postgres로, `DATABASE_URL` env 채우고 Disk 제거 |

Phase 1의 결과물(env var로 DB 위치·API 주소를 주입하는 구조)이 2·3이 합쳐질 때
코드 충돌 없이 값만 갈아끼우게 하는 접점이다.

## 아직 안 정한 것

- `life.db`를 통째로 Supabase로 옮길지, 자주 바뀌는 표(`customers`, `user_preferences`)만
  옮기고 큰 벡터 표(`kb_chunk`, `member_chunk`)는 계속 파일/디스크로 둘지 — 팀원 B 결정 대기.
- Supabase Auth를 쓸지 — 지금 `app/features/auth.py`는 "임시 로그인 발급" 데모 수준이라
  별개 결정이 필요하다.
