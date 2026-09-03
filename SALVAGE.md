# SALVAGE.md — 버리기 전에 빼둔 미커밋 작업

## 이 파일은 무엇인가

2026-09-02, `jihye` 브랜치에 **커밋하지 않은 채 작업 중이던 내용**을 `origin/dev-embed`를
머지해 받기로 결정하면서 통째로 걷어냈다. 그때 사라지는 코드·설계 의도·DB 스키마 변경을
항목별로 여기 남긴다. **되살리고 싶으면 이 파일만 보면 된다.**

- 기준 커밋: `247910f` (키워드부재시 빵점나오는 문제를 llm으로 땜빵하는 함수 추가)
- 걷어낸 대상: `app/core/db.py`(+82줄) · `app/features/admin.py`(+23줄) ·
  `app/features/analysis.py`(신규 246줄, untracked) · `AGENTS.md`(문서 개편) ·
  `data/life.db`(스키마 변경분)
### 보관 위치 — 전부 저장소 밖(`C:\Users\lecra\Desktop\life-db-backup\`)이라 git·LFS와 무관하다

```
life.db.20260902-224751.bak   70MB. [항목 G]의 DB 스키마·데이터는 여기에만 남아 있다
salvage/analysis.py           [항목 E] 신규 파일 전문 (246줄)
salvage/AGENTS.md             [항목 F] 문서 개편본 전문
salvage/db.py.patch           [항목 A][항목 B] diff
salvage/admin.py.patch        [항목 C][항목 D] diff
salvage/AGENTS.md.patch       [항목 F] diff
```

`.patch`는 기준 커밋 `247910f` 위에서 만든 것이다. 되살릴 때는 그냥 붙지 않을 가능성이 높다
(dev-embed가 같은 자리를 고쳤다 — [항목 B] [항목 C] 참고). 먼저 이렇게 시험해 보고,

```bash
git apply --3way "C:/Users/lecra/Desktop/life-db-backup/salvage/db.py.patch"
```

충돌이 나면 패치를 **읽기 자료로만 쓰고 손으로 옮기는 편이 빠르다.** 아래 항목별 원문이
그래서 있다.

### 왜 갈아엎었나 — dev-embed와 설계가 정면으로 부딪혔다

여기 있는 코드는 검색·대화 기록을 **`customer_id` 칸을 따로 둔 새 표**로 다루는 설계다.
반면 `origin/dev-embed`(HeoJaeSeong)는 **기존 `anon_id` 칸 하나를 겸용**하기로 했다 —
로그인하면 `anon_id` 자리에 `customer_id`를 써넣는 방식이다.

```
[이쪽 - 폐기]  search_history(history_id PK, anon_id, customer_id, query, created_at)
               조회: WHERE customer_id = ?          ← db.customer_history()

[dev-embed]    search_history(anon_id, query, created_at)
               조회: WHERE anon_id = ?              ← db.list_search_history(customer_id)
                                                      (anon_id 자리에 customer_id를 넣어 부른다)
```

같은 표 이름을 다른 방식으로 쓰기 때문에 **텍스트 충돌을 다 풀어도 한쪽은 조용히 0건**이
된다. 그래서 섞지 않고 한쪽(dev-embed)으로 통일했다.

> 되살릴 때 반드시 먼저 정할 것 — 로그인 전 익명 활동과 로그인 후 활동을 **구분할 것인가**.
> 구분하려면 이 파일의 [항목 B]가 맞고, 구분 안 할 거면 dev-embed 쪽이 단순해서 맞다.
> `anon_id` 겸용은 한번 섞이면 되돌릴 수 없다는 점만 알고 고르면 된다.

---

## 항목 A — `db.customer_preferences_initial()` (가입 시 가중치 조회)

**무엇** — `user_preferences`의 `녹지_초기`~`문화_초기` 7칸을 읽어, **`_초기`를 뗀 키**로
돌려준다. 현재값(`customer_preferences()`)과 키 모양이 같아서 화면이 같은 코드로 두 번 돌 수 있다.

**왜** — 관리자 화면이 "가입 때 이랬는데 지금 이렇다"를 위아래로 보여준다. 한 딕셔너리에
섞어 주면 화면이 칸 이름에서 `_초기`를 떼어내며 돌아야 해서 화면 쪽이 더러워진다.

**원문** (`app/core/db.py`, `customer_preferences()` 바로 아래에 있었다)

```python
def customer_preferences_initial(customer_id):
    """가입 시 가중치 7개(`녹지_초기` 등). 없으면 None.

    현재값과 따로 꺼내는 이유 —
    관리자 화면이 "가입 때 이랬는데 지금 이렇다"를 위아래로 보여준다.
    한 딕셔너리에 섞어 주면 화면이 칸 이름에서 `_초기`를 떼어내며 돌아야 한다.

    돌려주는 키는 `_초기`를 뗀 이름이다 — 현재값과 같은 키라서 화면이
    같은 방식으로 돌 수 있다
    """
    cols = ", ".join(f'"{name}_초기" AS "{name}"' for name in INDICATORS)
    rows = dicts(
        f"SELECT {cols} FROM user_preferences WHERE customer_id = ?",
        (customer_id,),
    )
    return rows[0] if rows else None
```

**되살릴 때** — dev-embed와 충돌하지 않는다(그쪽은 이 근처를 안 건드린다).
다만 **[항목 G]의 `_초기` 7칸이 DB에 없으면 `no such column`으로 죽는다.**

---

## 항목 B — `db.ensure_history()` / `db.customer_history()` (새 기록 표)

**무엇** — `search_history` · `chat_history`를 `history_id` PK + `anon_id` + `customer_id`
구조로 만들고, 회원 한 명 몫을 화면 계약과 같은 모양으로 돌려준다.

**왜** — 로그인 전(익명 `anon_id`)과 로그인 후(`customer_id`) 활동을 **구분해서** 쌓으려고
칸을 나눴다. 화면 계약은 이미 정해져 있었다
(`Life-Web/frontend/ui/history.js`: `GET /api/history?anonId=...` →
`{searches:[{query,created_at}], chats:[{question,answer,created_at}]}`).
관리자 화면과 사용자 화면이 같은 그리기 코드를 나눠 쓸 수 있게 반환 모양을 그 계약에 맞췄다.

**⚠ 이 항목이 dev-embed와 직접 충돌하는 지점이다.** 위 "왜 갈아엎었나" 참고.

**원문** (`app/core/db.py` 맨 끝, `write_admin_log()` 다음에 있었다)

```python
# ── 검색·대화 기록 ──────────────────────────────
# ⚠ 이 표 구조는 "제안"이다. 로그인·기록 저장을 맡은 분과 맞춰야 한다.
#   화면 쪽 계약은 이미 정해져 있다(Life-Web/frontend/ui/history.js 5번째 줄):
#     GET /api/history?anonId=... → {searches:[{query,created_at}], chats:[{question,answer,created_at}]}
#   그 계약을 그대로 담을 수 있게 칸을 잡았고, 관리자 화면이 회원별로도 볼 수 있게
#   customer_id 를 하나 더 뒀다. 로그인 전에는 anon_id 만, 로그인 후에는 둘 다 채우면 된다

_history_ready = False


def ensure_history():
    """검색·대화 기록 표가 없으면 만든다. likes 와 같은 방식이다."""
    global _history_ready
    if _history_ready:
        return

    con = get_con()
    con.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            anon_id     TEXT,
            customer_id TEXT,
            query       TEXT NOT NULL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            anon_id     TEXT,
            customer_id TEXT,
            question    TEXT NOT NULL,
            answer      TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 회원별 조회가 관리자 화면의 주 사용처라 그 칸에만 색인을 둔다
    con.execute("CREATE INDEX IF NOT EXISTS ix_search_customer ON search_history(customer_id)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_chat_customer ON chat_history(customer_id)")
    con.commit()
    _history_ready = True


def customer_history(customer_id, limit=30):
    """회원 한 명의 검색어·대화 기록. 아직 저장 기능이 없으면 빈 목록이 온다.

    화면 계약(history.js)과 같은 모양으로 돌려준다 — 나중에 사용자 화면과
    관리자 화면이 같은 그리기 코드를 나눠 쓸 수 있게 하려는 것이다
    """
    ensure_history()
    return {
        "searches": dicts(
            "SELECT query, created_at FROM search_history "
            "WHERE customer_id = ? ORDER BY history_id DESC LIMIT ?",
            (customer_id, limit),
        ),
        "chats": dicts(
            "SELECT question, answer, created_at FROM chat_history "
            "WHERE customer_id = ? ORDER BY history_id DESC LIMIT ?",
            (customer_id, limit),
        ),
    }
```

**되살릴 때 반드시 알아야 할 것**

1. `db.py`에는 **옛 정의가 따로 있다** — `ensure_search_history()` / `ensure_chat_history()`
   (`anon_id NOT NULL`, PK 없음). 둘 다 `CREATE TABLE IF NOT EXISTS`라 **먼저 실행된 쪽이
   조용히 이긴다**(에러도 경고도 없다). 되살리려면 옛 정의와 그 짝 함수
   (`add_search_history` `list_search_history` `add_chat_history` `list_chat_history`)를
   **같이 정리해야** 한다. 안 그러면 어느 스키마가 실제로 만들어질지 실행 순서에 좌우된다.
2. dev-embed는 그 옛 함수들을 `admin.get_member()`에서 **실제로 쓰기 시작했다**
   (`list_search_history(customer_id)`). 즉 되살리는 순간 그쪽 호출부도 같이 바꿔야 한다.
3. 표를 새로 만드는 것만으로는 아무 값도 안 들어온다 — **기록을 "쌓는" 쪽(로그인 담당)이
   같은 규칙으로 써 줘야** 한다.

---

## 항목 C — `admin.get_member()`에 `preferences_initial` 추가

**무엇** — 회원 한 명 조회 결과에 가입 시 가중치를 한 칸 더 실었다.

**왜** — 관리자가 현재값을 고쳐도 가입 시 값은 보존된다. 화이트리스트
`PREFERENCE_FIELDS`가 `INDICATORS` 7개뿐이라 `_초기` 칸은 **수정 대상에 아예 안 들어가기**
때문이다. 이게 [항목 E]의 "변동 추이" 분석이 성립하는 근거다.

**원문** (`app/features/admin.py`)

```python
from app.core.db import (
    customer_list, customer_one, customer_preferences, customer_preferences_initial,
    customer_persona, region_list, region_one,
    update_customer, update_preferences, update_region as db_update_region,
    column_percentile, write_admin_log, ensure_admin_log, dicts, one,
    customer_history,
)

def get_member(customer_id):
    """회원 한 명 = 기본정보 + 희망조건(현재/가입시) + 페르소나 9칸

    preferences_initial 은 가입 때 받은 값이다. 관리자가 고쳐도 안 바뀐다 —
    화이트리스트(PREFERENCE_FIELDS)가 INDICATORS 7개뿐이라 `_초기` 칸은
    수정 대상에 아예 안 들어간다
    """
    customer = customer_one(customer_id)
    if customer is None:
        return None
    return {
        "customer": customer,
        "preferences": customer_preferences(customer_id) or {},
        "preferences_initial": customer_preferences_initial(customer_id) or {},
        "persona": customer_persona(customer_id),
    }
```

**되살릴 때** — dev-embed도 **바로 이 import 블록과 `get_member()`를 고쳤다**(활동 3종
`likes`/`searches`/`chats`를 추가). 되살리면 두 변경을 손으로 합쳐야 한다.
합친 모습은 대략 이렇다:

```python
    return {
        "customer": customer,
        "preferences": customer_preferences(customer_id) or {},
        "preferences_initial": customer_preferences_initial(customer_id) or {},   # 이쪽 것
        "persona": customer_persona(customer_id),
        "likes": list_likes(customer_id),                                          # dev-embed 것
        "searches": list_search_history(customer_id),
        "chats": list_chat_history(customer_id),
    }
```

---

## 항목 D — `admin.member_history()` (회원별 기록 창구)

**무엇** — 회원 한 명의 검색어·대화 기록. 없는 회원이면 `None`.

**왜** — `admin.py`가 SQL을 직접 안 짜고 `db.py`에만 맡긴다는 이 저장소 규칙을 지키면서,
"없는 회원"과 "기록이 없는 회원"을 구분해 주려고 얇게 한 겹 씌웠다.

**원문** (`app/features/admin.py`, `health()` 다음)

```python
def member_history(customer_id: str, limit: int = 30) -> dict | None:
    """회원 한 명의 검색어·대화 기록. 없는 회원이면 None.

    ⚠ 기록을 "쌓는" 쪽은 아직 없다(로그인·기록 저장 담당). 표만 미리 있어서
    지금은 항상 빈 목록이 온다. 저장이 붙으면 이 함수는 그대로 두고 채워진다
    """
    if customer_one(customer_id) is None:
        return None
    return customer_history(customer_id, limit=limit)
```

**⚠ 되살릴 때 — `Life-Web`이 이 이름을 이미 import하고 있다.**
`Life-Web/services/engine.py`의 admin import 목록에 `member_history`가 들어 있다.
dev-embed를 받은 뒤 이 함수가 없으면 **웹 서버가 import 단계에서 죽는다.**
아래 "머지 직후 확인할 것" 참고.

---

## 항목 E — `app/features/analysis.py` (관리자 분석, 신규 246줄)

**무엇** — DB를 SQL로 먼저 집계한 뒤, 그 숫자만 Claude에게 읽혀 관리자 질문에 답하게 하는
창구. 질문·답·**그때의 집계 스냅샷**을 `analysis_chat` 표에 남긴다.

**왜 Claude에게 SQL을 안 짜게 했나** (이 파일의 핵심 설계 — 되살릴 때 절대 바꾸지 말 것)
> 이 파일이 SQL로 집계표를 먼저 만들고, Claude는 그 숫자만 읽는다. Claude가 직접 쿼리를
> 짜게 하면 세 가지가 위험하다 — 느린 쿼리로 서버가 멈추고, 잘못된 조인으로 틀린 숫자가
> 나오고, 개인정보 칸(이름·전화·이메일)까지 긁어올 수 있다. 집계를 우리가 만들면 그 셋 다
> 원천적으로 없다.

**왜 집계 스냅샷까지 저장하나**
> 데이터는 계속 바뀐다. 한 달 뒤 이 답을 다시 열었을 때 "그때는 무슨 숫자를 보고 이렇게
> 답했나"를 알 수 없으면 답을 믿을 수 없다.

**왜 프롬프트가 그렇게 방어적인가**
> 여기서 나온 답은 "회사 내부 소비자 분석 자료"로 쓰인다. 표본이 100명이고 어떤 항목은
> 아직 0건인데 Claude가 그럴듯한 이야기를 지어내면 그게 그대로 자료가 된다. 그래서
> 집계에 "표본 수"와 "왜 비어 있는지"(`비어있는_이유`)를 같이 실어 보낸다.

**구성**

| 구획 | 함수 | 하는 일 |
|---|---|---|
| 집계 | `facts_members()` | 지표 7개 평균 + 1~5점 인원 분포 + 연령대 + 성별 |
| 집계 | `facts_regions(top=15)` | 거주/직장 자치구 분포, 좋아요 많은 동네 |
| 집계 | `facts_drift()` | 가입 시 값 대비 현재 값의 변화 (**[항목 G]의 `_초기` 칸 필요**) |
| 집계 | `facts_searches(top=20)` | 검색어 트렌드 (**[항목 B]의 표 필요**) |
| 집계 | `collect_facts()` | 위 넷을 한 덩어리로 |
| LLM | `SYSTEM`, `_facts_text()`, `ask()` | 집계 → 프롬프트 → Claude → 저장 |
| 보관 | `ensure_table()` `save_chat()` `list_chats()` `get_chat()` `delete_chat()` | `analysis_chat` CRUD |

**설계 관례 두 가지 (되살릴 때 지킬 것)**
- 모든 집계는 `{"label": ..., "value": ...}` 목록으로 통일한다 — 화면 차트 함수 하나로 전부
  그릴 수 있고, 프롬프트에 넣을 때도 같은 방식으로 글로 바꿀 수 있다. (`admin.dashboard()`와
  같은 관례다.)
- 데이터가 없는 항목은 빈 값만 주지 않고 `비어있는_이유`를 채워 보낸다 — 그래야 Claude가
  "없는 데이터로 추세를 말하는" 대신 "그 자료는 아직 없다"고 답한다.

**⚠ 전문(全文)은 여기 옮기지 않았다.** 246줄이라 이 문서에 넣으면 오히려 안 읽힌다.
파일 자체를 아래 위치에 통째로 보관해 두었다:

```
C:\Users\lecra\Desktop\life-db-backup\salvage\analysis.py
```

**⚠ 되살릴 때 — `Life-Web`이 이 모듈을 이미 import하고 있다.**
`Life-Web/services/engine.py`에 `from app.features import analysis as analysis_engine`가
있다. 이 파일이 없으면 **웹 서버가 import 단계에서 죽는다.**

---

## 항목 F — `AGENTS.md` 문서 개편

**무엇** — 2026-09-02에 코드 전체를 훑어 `AGENTS.md`(= `CLAUDE.md`가 `@AGENTS.md`로 가리키는
실체)를 사실관계에 맞게 고쳤다. 고친 항목:

- `requirements.txt`가 **없다**고 적혀 있었으나 실제로는 버전 고정까지 돼 **있다**
- `docu/DESIGN.md` → 실제 경로는 `docs/`이고, `docs/*` `eval/golden.py` `test/*.py`
  8개가 전부 **0바이트**라는 사실 명시
- 아키텍처 표에 빠져 있던 `domain/masking.py` `features/privacy.py` `features/scoring.py`
  `features/analysis.py` `pipeline/migrate_vector_blob.py` 추가
- 깨져 있던 명령어 설명 복구 + `region_explain` `chat` `app.core.db` 실행법 추가
- `(이 저장소가 아니` 에서 끊겨 있던 마지막 문장을 복구하고, `Life-Web/services/engine.py`가
  실제로 import하는 이름 전체(= 바꾸면 서버가 죽는 목록)를 명시
- 새 함정 절 추가: `pipeline.schema` 재생성이 `_초기` 칸을 날린다 / history 표 정의가 두 벌 /
  `analysis.py`가 untracked인데 `Life-Web`이 쓴다 / `행정동별_시세_LLM요약`은 아무도 안 읽는다

**되살릴 때** — 이 문서 변경은 **dev-embed와 충돌하지 않는다**(그쪽은 `AGENTS.md`를 안
건드렸다). 다만 위 내용 중 **history 표 관련 서술은 dev-embed 설계 기준으로 다시 써야**
한다. 개편본 전문은 여기 보관했다:

```
C:\Users\lecra\Desktop\life-db-backup\salvage\AGENTS.md
```

---

## 항목 G — 코드가 아닌 것: DB 스키마 변경 ⚠ 가장 되살리기 어려움

**이 항목만은 코드가 아니라 데이터다. 백업 파일에만 남아 있다.**

`data/life.db`에 직접 가한 변경이라 CSV에도 `pipeline/schema.py`에도 없다. 즉
`python -m pipeline.schema`로 DB를 재생성하면 **다시 사라진다.**

### G-1. `user_preferences`의 `_초기` 7칸

`녹지_초기` `안전_초기` `교통_초기` `상권_초기` `의료_초기` `교육_초기` `문화_초기`.
현재 100명 전원이 가입 시 값 그대로라 변동은 0건인 게 정상이다.

이 칸이 없으면 [항목 A] [항목 C], 그리고 [항목 E]의 `facts_drift()`가
`no such column: 녹지_초기`로 죽는다.

**다시 만드는 SQL** (현재값을 가입 시 값으로 복사하는, 처음 만들 때와 같은 방식)

```sql
ALTER TABLE user_preferences ADD COLUMN "녹지_초기" REAL;
ALTER TABLE user_preferences ADD COLUMN "안전_초기" REAL;
ALTER TABLE user_preferences ADD COLUMN "교통_초기" REAL;
ALTER TABLE user_preferences ADD COLUMN "상권_초기" REAL;
ALTER TABLE user_preferences ADD COLUMN "의료_초기" REAL;
ALTER TABLE user_preferences ADD COLUMN "교육_초기" REAL;
ALTER TABLE user_preferences ADD COLUMN "문화_초기" REAL;

UPDATE user_preferences SET
    "녹지_초기" = "녹지", "안전_초기" = "안전", "교통_초기" = "교통",
    "상권_초기" = "상권", "의료_초기" = "의료", "교육_초기" = "교육",
    "문화_초기" = "문화";
```

> ⚠ 이미 관리자가 값을 고친 뒤에 이 SQL을 돌리면 **고친 값이 "가입 시 값"으로 굳는다.**
> 변동 추이가 영영 0건이 된다. 반드시 백업 DB에서 옮겨오거나, 아무도 안 고친 상태에서 돌릴 것.
> 근본 해결은 `pipeline/schema.py`가 이 7칸을 처음부터 만들게 하는 것이다.

### G-2. `analysis_chat` 표

[항목 E]의 `ensure_table()`이 알아서 만들므로 **구조는 복구 불필요**하다.
다만 **쌓여 있던 분석 대화 기록은 사라진다** — 백업 DB에만 있다.

### G-3. `search_history` / `chat_history`의 새 스키마

현재 백업 DB에는 [항목 B]의 새 구조(`history_id` PK + `customer_id`)로 들어가 있다.
`dev-embed`의 DB로 갈아타면 그쪽 구조가 된다. **둘 다 0건이라 잃을 데이터는 없다.**

참고로 **dev-embed의 코드는 새 스키마 위에서도 그대로 돈다** — 새 표에도 `anon_id` 칸이
있어서 `list_search_history()`의 `WHERE anon_id = ?`가 정상 동작한다. 반대는 성립하지 않는다
(옛 표에는 `customer_id` 칸이 없어서 `customer_history()`가 죽는다).

### G-4. 두 life.db는 크기만 같고 내용이 다르다

```
작업본     sha256 f2307952d9eff2eb10dee198e67d714416885551f8adfd21f761ccb68aeffc44  (73,150,464 B)
dev-embed  oid    e5f94904b451115dc3f68dc2d42653933e45f7d43fb9191405b76d6633b65f5b  (73,150,464 B)
jihye HEAD oid    0d7f54716501d26497aca6726a25385bbd025c4cc39b39fcfc0d277e50ed301c  (73,121,792 B)
```

크기가 같아서 "같은 파일"로 오해하기 쉽다. **다른 DB다.** dev-embed 쪽에는 그쪽이 새로
만든 `user_login` 표가 들어 있을 것이고, 이쪽 `_초기` 칸은 없을 수 있다.

---

## 머지 직후 확인할 것 (체크리스트)

`origin/dev-embed`를 받은 뒤 `Life-Web`이 뜨는지부터 본다. 아래 두 이름은 `Life-Web/services/engine.py`가
**import 목록에 이미 적어 둔** 것이라, 없으면 서버가 시작조차 못 한다.

- [ ] `app/features/analysis.py` — [항목 E]. 없으면 `ModuleNotFoundError`
- [ ] `admin.member_history` — [항목 D]. 없으면 `ImportError: cannot import name 'member_history'`

둘 중 하나라도 빠지면 선택지는 셋이다:

1. **되살린다** — 이 문서의 [항목 D] [항목 E]를 dev-embed 위에 다시 붙인다
   (`analysis.py`는 [항목 G-1]의 `_초기` 칸도 같이 필요하다).
2. **`Life-Web` 쪽 import를 걷어낸다** — 관리자 분석·회원별 기록 화면을 잠시 끈다.
3. **`Life-Web`도 같이 되돌린다** — 그쪽 저장소에서 해당 기능 커밋 전으로 맞춘다.

그다음:

- [ ] `py -m app.core.db` — DB 조회가 도는지
- [ ] `py -m app.features.pipeline_api` — 추천 전체 흐름이 도는지
- [ ] 관리자 화면에서 회원 하나 열어보기 — `get_member()`가 dev-embed의 활동 3종을 잘 싣는지
- [ ] `AGENTS.md`의 history 관련 서술을 dev-embed 설계 기준으로 고쳐 쓰기 ([항목 F])
