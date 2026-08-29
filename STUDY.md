# 기록 방법
    - 사용자는 코딩을 막 시작한 초보개발자.
    - 함수나 기능에 대한 설명 필요
    - 원본 코드 -> 수정할 코드를 알기 쉽게 표기
    - 예시:
        클릭은 되는데 드래그만 안 되는 이유

        슬라이더를 끄는 건 mousedown → mousemove → mouseup 세 단계예요. 그런데 search.js가 문서 전체에 mousemove 리스너를 걸어놨죠:

       ```
        document.addEventListener("mousemove", (e) => {
        ...
        updateMagnetic(mx, my);
        });
        ```

        떠다니는 단어의 자석 효과예요. 이게 계속 돌면서 getBoundingClientRect()를 14번씩 호출해요. 검색 화면이 사라진 뒤에도요.

        클릭(한 번의 이벤트)은 되는데 드래그(연속 이벤트)가 버벅이는 게 이 증상과 맞아요.

        고치기 — 화면이 걷히면 자석을 멈춘다

        search.js의 updateMagnetic 맨 앞에 한 줄 넣으세요.

        ```
        function updateMagnetic(mx, my) {
        // 검색 화면이 걷힌 뒤에는 계산할 이유가 없다.
        // 그대로 두면 mousemove 마다 getBoundingClientRect 를 14번씩 부르느라
        // 슬라이더 드래그 같은 다른 조작이 버벅인다
        const screen = document.getElementById("searchScreen");
        if (!screen || screen.classList.contains("out")) return;

        document.querySelectorAll(".ss-word").forEach((word) => {
            ...    
        ```

---

# 진행 상황

`엔진_성능진단_및_최적화방안.txt` 의 다섯 가지 지적([A]~[E]) 중 **[A] find_cases 캐싱, [C] to_passage
통일, [E] 임베딩 모델 선로딩은 완료**했다. 아래는 아직 안 건드린 **[B] 벡터 저장 포맷(BLOB 전환)**,
**[D] BATCH_SIZE 활용**을 어떻게 고쳐야 하는지 정리한 것 — 직접 구현해볼 사람을 위한 설명.

---

# [B] 벡터가 SQLite 에 JSON 글자로 저장돼서 DB 가 3배 이상 크다

## 왜 문제인가 — TEXT 는 숫자를 "글자"로 저장한다

`kb_chunk`, `member_chunk` 두 테이블 모두 벡터(숫자 384개)를 이렇게 저장한다
([pipeline/embed_kb.py:60](pipeline/embed_kb.py#L60)):

```python
# pipeline/embed_kb.py (원본) — embed_and_store() 안
values = [
    (r["uuid"], r["district"], r["category"], r["text"],
     json.dumps(vec))          # 숫자 384개 -> "[0.0123, -0.0456, ...]" 같은 긴 문자열
    for r, vec in zip(rows, vectors)
]
```

SQLite 에는 "숫자 배열" 이라는 타입이 없다. 그래서 `json.dumps` 로 숫자를 사람이 읽는 글자로
바꿔서 저장한다. 문제는 `0.123456` 같은 숫자 하나가 원래는 4바이트(float32)면 충분한데, 글자로
쓰면 `"0.123456"` 처럼 8~9바이트가 된다 — 2배 이상 커지는 것이다. `kb_chunk` 는 22,500줄 ×
384개 숫자라서 이 차이가 누적되면:

| 저장 방식 | 용량 (kb_chunk 기준) | 다시 숫자로 읽는 시간 |
|---|---|---|
| JSON 문자열 (지금) | 186.8 MB | 3.52초 |
| BLOB (바이트 그대로) | 44.1 MB | 0.067초 |

`life.db` 전체가 216MB 인데 그중 187MB 가 이 벡터 칸 하나다. BLOB 으로 바꾸면 DB 가 약
70MB 대로 줄어든다.

> **[A] 캐싱을 이미 적용했기 때문에** 로딩 시간 3.52초→0.067초 차이는 서버가 켜질 때 딱
> 한 번만 영향을 준다(그마저도 몇 초 차이). 그래서 이 작업의 진짜 가치는 **속도가 아니라
> DB 용량**이다 — Git LFS 로 관리하는 `life.db`(216MB)를 가볍게 만드는 것이 목적.

## 무엇을 바꿔야 하나 — 세 군데

벡터를 다시 임베딩할 필요는 없다. 이미 저장된 JSON 문자열을 읽어서 BLOB 으로 다시 쓰기만
하면 된다. 그래도 손댈 곳은 세 군데다.

### 1) 마이그레이션 스크립트 (한 번만 실행하고 버릴 코드)

```python
# 예: pipeline/migrate_vector_blob.py (새로 만드는 1회용 스크립트)
import json
import sqlite3
import numpy as np
from app.core.config import DB_PATH

def migrate(table, con):
    cur = con.cursor()
    cur.execute(f"ALTER TABLE {table} ADD COLUMN vector_blob BLOB")

    rows = cur.execute(f"SELECT chunk_id, vector FROM {table}").fetchall()
    for chunk_id, vector_json in rows:
        vec = np.array(json.loads(vector_json), dtype="float32")   # 반드시 float32
        cur.execute(
            f"UPDATE {table} SET vector_blob = ? WHERE chunk_id = ?",
            (vec.tobytes(), chunk_id),
        )
    con.commit()
    print(f"✅ {table}: {len(rows):,}줄 변환 완료")

if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    migrate("kb_chunk", con)
    migrate("member_chunk", con)
    con.close()
```

변환 후 `vector_blob` 값이 제대로 들어갔는지 확인하고 나서, 옛 `vector`(TEXT) 칼럼은
`ALTER TABLE ... DROP COLUMN vector`(SQLite 3.35+) 로 지우거나, 새 테이블을 만들어
옮기는 방식으로 정리한다. 컬럼 이름을 다시 `vector` 로 맞추면 아래 2), 3) 에서 이름을
안 바꿔도 된다.

### 2) 읽는 쪽 — `json.loads` → `np.frombuffer`

벡터를 읽어서 numpy 배열로 되돌리는 곳이 세 군데 있다. 전부 같은 패턴으로 바꾼다.

```python
# 원본 — pipeline/explain.py:57, pipeline/weights.py:58, pipeline/search_kb.py:20 공통
vectors = np.array([json.loads(r["vector"]) for r in rows], dtype="float32")
```

```python
# 수정
vectors = np.array(
    [np.frombuffer(r["vector"], dtype="float32") for r in rows]
)
```

`app/core/db.py` 의 `kb_chunks()` / `member_chunks()` 자체는 안 건드려도 된다 — 그 함수들은
그냥 SELECT 해서 행을 돌려줄 뿐이라, 칼럼 값이 문자열이든 바이트든 상관없이 그대로 통과시킨다.
"꺼내주기만 한다"는 core 계층 역할은 유지된다.

### 3) 쓰는 쪽 — `json.dumps` → `.tobytes()`, `TEXT` → `BLOB`

새로 임베딩할 때(재임베딩 상황)를 위해 저장 코드도 같이 바꿔야 한다.

```python
# 원본 — pipeline/embed_kb.py:29-37, pipeline/embed_member.py:63-71 공통 (CREATE TABLE)
cur.execute("""
    CREATE TABLE IF NOT EXISTS kb_chunk (
        ...
        vector      TEXT
    )
""")
```

```python
# 수정
cur.execute("""
    CREATE TABLE IF NOT EXISTS kb_chunk (
        ...
        vector      BLOB
    )
""")
```

```python
# 원본 — pipeline/embed_kb.py:60, pipeline/embed_member.py:88 공통
values = [(..., json.dumps(vec)) for r, vec in zip(rows, vectors)]
```

```python
# 수정 — vec 을 반드시 float32 로 고정해서 바이트로 바꾼다
values = [(..., np.asarray(vec, dtype="float32").tobytes()) for r, vec in zip(rows, vectors)]
```

## 주의할 점

- **dtype 을 반드시 `float32` 로 고정한다.** 저장은 float32, 읽을 때는 실수로 float64 로
  읽으면 384개 숫자가 192개로 잘못 해석돼 차원이 깨진다. 에러가 나지 않고 결과만 미묘하게
  틀려지는 가장 찾기 힘든 종류의 버그이니 주의.
- **작업 전에 `data/life.db` 를 반드시 백업한다.** 216MB 파일이고, 재임베딩(20~40분)을 다시
  하고 싶지 않다면 되돌릴 방법이 없는 마이그레이션이다.
- 변환 후에는 `python -m pipeline.search_kb` 같은 단독 실행 스크립트로 검색 결과가 변환
  전과 동일하게 나오는지 확인한다. 숫자가 바뀌면 그건 버그다 — 저장 방식만 바뀌었을 뿐
  계산 결과는 완전히 같아야 한다.

---

# [D] BATCH_SIZE 상수가 선언만 되고 안 쓰인다

## 왜 문제인가

[pipeline/embed_kb.py:14](pipeline/embed_kb.py#L14) 에 이렇게 선언돼 있다.

```python
BATCH_SIZE = 32          # 어디에서도 참조되지 않음
```

그런데 실제 임베딩은 이렇게 한 번에 다 들어간다 ([pipeline/embed_kb.py:51](pipeline/embed_kb.py#L51)):

```python
# pipeline/embed_kb.py (원본) — embed_and_store() 안
docs = [to_passage(r["text"]) for r in rows]      # docs 22,500개
...
vectors = get_embedder().embed_documents(docs)     # 22,500개가 통째로 한 번에 처리됨
```

결과적으로 문제가 두 가지다.

1. **진행 상황이 안 보인다.** 22,500개가 끝날 때까지 화면이 그대로 멈춰 있는 것처럼 보인다
   (실제로는 5분짜리 작업이 돌고 있는데도).
2. **중간에 실패하면 처음부터 다시 해야 한다.** 네트워크가 끊기거나 메모리가 부족해서
   20,000번째쯤에서 죽으면, 이미 처리한 20,000개도 버리고 처음부터 다시 돌려야 한다.

`embed_kb.py`(22,500개), `embed_member.py`(회원 청크) 둘 다 같은 문제다.

## 고치는 법 — BATCH_SIZE 단위로 나눠서 돌리고, 배치마다 commit

```python
# pipeline/embed_kb.py (원본) — embed_and_store()
def embed_and_store(cur, rows):
    docs = [to_passage(r["text"]) for r in rows]

    print(f"⏳ {len(docs):,}개 청크를 벡터로 바꾸는 중... (2만2천 개 기준 약 5분)")
    started = time.time()

    vectors = get_embedder().embed_documents(docs)

    print(f"✅ 완료 ({time.time() - started:.0f}초)")

    values = [
        (r["uuid"], r["district"], r["category"], r["text"], json.dumps(vec))
        for r, vec in zip(rows, vectors)
    ]
    cur.executemany(
        "INSERT INTO kb_chunk (uuid, district, category, text, vector) VALUES (?, ?, ?, ?, ?)",
        values,
    )
```

```python
# pipeline/embed_kb.py (수정) — embed_and_store() 가 con 을 받아서 배치마다 commit
def embed_and_store(cur, con, rows):
    total = len(rows)
    started = time.time()

    for start in range(0, total, BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        docs = [to_passage(r["text"]) for r in batch]

        vectors = get_embedder().embed_documents(docs)

        values = [
            (r["uuid"], r["district"], r["category"], r["text"], json.dumps(vec))
            for r, vec in zip(batch, vectors)
        ]
        cur.executemany(
            "INSERT INTO kb_chunk (uuid, district, category, text, vector) VALUES (?, ?, ?, ?, ?)",
            values,
        )
        con.commit()   # 배치 하나가 끝날 때마다 저장 — 여기서 죽어도 이전 배치는 남는다

        done = min(start + BATCH_SIZE, total)
        elapsed = time.time() - started
        print(f"⏳ {done:,}/{total:,}개 처리 중... ({elapsed:.0f}초 경과)")

    print(f"✅ 완료 ({time.time() - started:.0f}초)")
```

`cur` 만 받던 함수가 `con`(커밋을 하려면 커넥션이 필요하다)도 받아야 하므로, 호출부인
`__main__` 블록에서 `embed_and_store(cur, rows)` → `embed_and_store(cur, con, rows)` 로
바꿔줘야 한다. `pipeline/embed_member.py` 도 완전히 같은 방식으로 고치면 된다.

## 이어서 재개하고 싶다면 (선택)

배치마다 commit 해두면, 실패했을 때 이미 DB 에 몇 개가 들어갔는지 셀 수 있다.

```python
# __main__ 블록에서, 이미 들어간 만큼 건너뛰고 이어서 시작
done = cur.execute("SELECT COUNT(*) FROM kb_chunk").fetchone()[0]
embed_and_store(cur, con, rows[done:])   # 이미 처리한 부분은 다시 안 보낸다
```

단, 이건 "처음부터 새로 시작할지 / 이어서 할지"를 사람이 판단해서 골라야 하는 부분이라
필수는 아니다. 배치 + commit 만 해도 "어디까지 됐는지 눈에 보이고, 최소한 이미 저장된
데이터는 안 날아간다" 는 목적은 달성된다.

## 주의할 점

- `BATCH_SIZE` 를 너무 작게 잡으면(예: 1) commit 호출이 22,500번 일어나서 오히려 느려진다.
  32~128 정도가 무난하다.
- 임베딩을 다시 돌릴 일이 있을 때만 체감되는 변화다. 급한 작업 아님.
