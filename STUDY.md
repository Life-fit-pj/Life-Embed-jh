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

# 엔진이 느린 진짜 이유 — find_cases() 가 검색할 때마다 22,500개 벡터를 다시 만든다

다른 AI가 작성한 `엔진_성능진단_및_최적화방안.txt` 를 받아서, 거기 적힌 다섯 가지 지적
([A]~[E])을 실제 파일([pipeline/explain.py](pipeline/explain.py),
[app/features/pipeline_api.py](app/features/pipeline_api.py),
[app/core/llm.py](app/core/llm.py), [pipeline/embed_kb.py](pipeline/embed_kb.py),
[pipeline/embed_member.py](pipeline/embed_member.py))과 하나씩 대조해봤다. 다섯 개 전부
코드에 그대로 있는 게 맞았다. 아래는 왜 그런지, 그리고 어떻게 고치는지를 정리한 것이다.

## 왜 검색 한 번에 8~13초나 걸릴까

검색 한 번이 거치는 단계를 나눠보면:

1. `ask_claude()` — Claude 에게 가중치 초안 받기 (1~3초, API 호출이라 원래 걸림)
2. `find_similar_members()` — 회원 100명 중 비슷한 사람 찾기 (30ms, 이미 캐시된 벡터 씀)
3. `recommend()` — 427개 동 점수 계산 (1ms 미만, numpy)
4. `find_cases()` — 지식베이스에서 유사 사례 찾기 (**3~4초**)
5. `explain()` — 설명문 생성 (3~6초, API 호출)

4번만 유독 느리다. 이유는 [find_cases()](pipeline/explain.py#L74)를 열어보면 바로 보인다.

```python
# pipeline/explain.py (원본)
def find_cases(persona_query, top_k=3):
    rows = kb_chunks()                                            # DB에서 22,500줄 통째로 SELECT
    vectors = np.array([json.loads(r["vector"]) for r in rows],   # 22,500번 json.loads
                        dtype="float32")

    q = np.array(get_embedder().embed_query(to_query(persona_query)), dtype="float32")
    scores = vectors @ q          # 실제 계산은 여기 한 줄, 384차원 내적 22,500번 — 1.6ms 수준
    ...
```

`kb_chunk` 테이블의 벡터는 SQLite 에 **JSON 문자열**로 저장돼 있다
([pipeline/embed_kb.py](pipeline/embed_kb.py#L60-L65)의 `json.dumps(vec)` 참고). 그래서
`find_cases()` 를 부를 때마다: DB에서 22,500줄을 다 퍼오고 → 문자열 22,500개를 각각
`json.loads` 로 숫자 배열로 되돌리는 일을 **매 검색마다 처음부터 반복**한다. 정작 필요한
연산(벡터 내적)은 1.6ms인데, 그 앞의 "문자열 → 숫자 되돌리기"가 훨씬 오래 걸리는 구조다.

## 왜 이런 구조가 됐나 — get_ready() 가 회원 쪽만 캐싱했다

[app/features/pipeline_api.py](app/features/pipeline_api.py#L27)의 `get_ready()` 는 "무거운
준비물은 처음 한 번만 만든다"는 목적으로 만들어진 함수다. 실제로 회원 벡터(`member_vectors`)와
행정동 점수(`scores`, `relative`)는 여기서 한 번만 만들어 `_ready` 딕셔너리에 캐싱해둔다.

```python
# app/features/pipeline_api.py (원본)
def get_ready():
    global _ready
    if _ready is None:
        member_rows, member_vectors = load_member_vectors()   # 회원 100명 → 캐시됨 ✅
        names, values = load_regions()
        scores = build_scores(values)
        relative = build_relative(scores)                     # 행정동 427개 → 캐시됨 ✅

        _ready = {
            "member_rows": member_rows, "member_vectors": member_vectors,
            "names": names, "scores": scores, "relative": relative,
        }
    return _ready
```

그런데 지식베이스 벡터(22,500개, 회원의 225배 크기)는 여기 없다. `find_cases()` 가 자기
데이터를 `get_ready()` 를 거치지 않고 함수 안에서 직접 `kb_chunks()` 로 불러오는 구조라서,
캐싱 설계에서 통째로 빠진 것이다. `weights.py` 의 `load_member_vectors()` 와 완전히 같은
패턴인데 지식베이스 쪽만 그 패턴을 안 따른 셈이다.

## 고치는 법 — 회원 벡터와 같은 패턴으로 맞춘다

### 1) `pipeline/explain.py` — 벡터를 인자로 받게 바꾸고, 로딩 함수를 분리한다

```python
# pipeline/explain.py (수정)
# load_member_vectors() 와 동일한 패턴으로 분리
def load_kb_vectors():
    """지식베이스 청크 벡터를 전부 꺼낸다. numpy 배열로 만든다."""
    rows = kb_chunks()
    vectors = np.array([json.loads(r["vector"]) for r in rows], dtype="float32")
    return rows, vectors


def find_cases(persona_query, rows, vectors, top_k=3):
    """검색 문장과 비슷한 지식베이스 청크를 찾는다.

    rows, vectors 는 get_ready() 가 미리 만들어 캐시해둔 것을 받는다.
    이 함수 안에서 다시 불러오지 않는다 — 그게 느려지는 원인이었다.
    """
    q = np.array(get_embedder().embed_query(to_query(persona_query)), dtype="float32")
    scores = vectors @ q

    top = scores.argsort()[::-1][:top_k]

    return [
        {
            "district": rows[i]["district"].replace("서울-", ""),
            "category": rows[i]["category"],
            "text": rows[i]["text"][:200],
            "score": float(scores[i]),
        }
        for i in top
    ]
```

`__main__` 블록도 같이 고쳐야 한다 (안 고치면 단독 실행 테스트가 깨진다):

```python
# pipeline/explain.py 의 __main__ 블록 (수정)
    detailed = with_scores(result, names, scores)
    kb_rows, kb_vectors = load_kb_vectors()
    cases = find_cases(persona_query, kb_rows, kb_vectors)
```

### 2) `app/features/pipeline_api.py` — get_ready() 에 kb 벡터를 추가한다

```python
# app/features/pipeline_api.py (수정)
from pipeline.explain import explain, find_cases, load_kb_vectors, with_scores
from app.core.llm import get_embedder

def get_ready():
    global _ready
    if _ready is None:
        print("⏳ 파이프라인 준비 중...")

        get_embedder()   # [E] 임베딩 모델도 여기서 한 번 올려둔다 — 첫 검색자만 로딩 비용을 떠안지 않도록

        member_rows, member_vectors = load_member_vectors()
        kb_rows, kb_vectors = load_kb_vectors()          # [A] 지식베이스 벡터도 여기서 한 번만
        names, values = load_regions()
        scores = build_scores(values)
        relative = build_relative(scores)

        _ready = {
            "member_rows": member_rows, "member_vectors": member_vectors,
            "kb_rows": kb_rows, "kb_vectors": kb_vectors,
            "names": names, "scores": scores, "relative": relative,
        }
        print(f"✅ 준비 완료 · 회원 청크 {len(member_rows)}개 · "
              f"지식베이스 청크 {len(kb_rows)}개 · 행정동 {len(names)}개")
    return _ready


def search(query, top_k=5):
    r = get_ready()
    draft, persona_query = ask_claude(query)
    similar = find_similar_members(persona_query, r["member_rows"], r["member_vectors"])
    ids = [cid for cid, _ in similar]
    weights = blend(draft, member_weights(ids))

    detailed = recommend_by_weights(weights, top_k=top_k)

    cases = find_cases(persona_query, r["kb_rows"], r["kb_vectors"])   # 캐시된 걸 넘겨준다
    text = explain(query, weights, detailed, cases)
    ...
```

### 왜 이게 안전한 수정인가

- **계산 결과가 안 바뀐다.** 벡터 내적 공식도, 정렬 방식도, top_k 개수도 그대로다. 딱 "매번
  다시 만들던 걸 한 번만 만들어 재사용"하는 것뿐이다. 리팩터링 후 아래처럼 검증하면 된다:
  `python -m app.features.pipeline_api` 로 같은 검색어("애들 학원 보내기 좋은 곳")를 두 번
  돌려서, 추천 순위·가중치·유사 사례가 수정 전과 똑같이 나오는지 확인. 그리고 **두 번째
  검색부터** 확 빨라지는지 확인 — 첫 검색은 여전히 준비 시간(3~4초)을 포함하지만, 그 비용을
  서버 시작 시점으로 옮기는 게 목적이다.
- **db.py(조회 계층)는 안 건드린다.** `kb_chunks()` 는 그대로 둔다. "꺼내주기만 한다"는
  core 계층의 역할은 유지하고, "언제 꺼내서 얼마나 재사용할지"는 상위 계층(`pipeline_api.py`)
  책임으로 남긴다.
- **부작용 두 가지는 알고 있을 것.** 서버가 시작할 때 3~4초가 더 걸리지만 그 비용은
  전체 기간에 걸쳐 한 번뿐이다. 그리고 메모리를 약 33MB(22,500 × 384 × float32) 더 쓰는데,
  요청마다 새로 만들던 걸 계속 붙잡고 있는 차이일 뿐 늘어나는 게 아니다.
- **`kb_chunk` 테이블을 재임베딩하면 서버를 반드시 재시작해야 한다.** `_ready` 는 프로세스가
  살아있는 동안만 캐시되므로, DB 내용을 바꾸고 서버를 안 내리면 캐시가 갱신되지 않는다.

## 그다음 — `to_passage()` 가 세 파일에 따로 정의돼 있다

[app/core/llm.py](app/core/llm.py#L47), [pipeline/embed_kb.py](pipeline/embed_kb.py#L42),
[pipeline/embed_member.py](pipeline/embed_member.py#L74) 세 곳 모두
`def to_passage(text): return f"passage: {text}"` 를 각자 다시 정의하고 있다. 지금 당장
결과가 틀리지는 않는다 — 세 함수가 우연히 똑같기 때문이다. 문제는 나중에 임베딩 모델을
e5 계열에서 bge 계열 등으로 바꿀 때 터진다. e5 규칙(저장은 `passage:`, 검색은 `query:`)이
모델마다 다른데, `llm.py` 의 접두사만 고치고 `embed_kb.py`/`embed_member.py` 에 남아있는
사본을 놓치면 — 에러 없이 조용히 검색 품질만 떨어지는, 원인 찾기 제일 어려운 종류의 버그가
된다.

```python
# pipeline/embed_kb.py, pipeline/embed_member.py (원본 — 각 파일에 중복 정의)
def to_passage(text):
    return f"passage: {text}"
```

```python
# pipeline/embed_kb.py, pipeline/embed_member.py (수정 — 지역 정의 삭제하고 import)
from app.core.llm import get_embedder, to_passage
```

두 파일에서 `def to_passage(text): ...` 지역 정의를 지우고 위 import 로 바꾸면 끝이다.
동작은 지금과 완전히 동일하다(어차피 같은 내용을 복사한 것이었으므로) — 미래의 사고만 막는
수정이다.

## 나중에 할 것 — 벡터 저장 방식을 JSON 문자열에서 BLOB 으로

`life.db` 전체 216MB 중 `kb_chunk` 벡터 칸만 약 187MB 를 차지한다. 숫자를
`"0.123456"` 같은 글자로 저장하기 때문이다(SQLite 는 숫자 배열 타입이 없어 TEXT 를 씀).
같은 숫자를 SQLite 의 BLOB(바이트 그대로) 타입으로 저장하면 이론상 216MB → 70MB 대로
줄어든다. 다만 이건:

- **위 [A] 캐싱 수정을 먼저 적용한 다음에** 손댈 일이다. [A]만으로 로딩 3~4초가 사라지고,
  BLOB 전환은 이미 캐시된 뒤 남는 로딩 0.02~0.07초를 더 줄이는 것뿐이라 체감 효과가 훨씬
  작다. 반면 `embed_kb.py`/`embed_member.py` 의 `CREATE TABLE`, `json.dumps(vec)` →
  `np.asarray(vec, dtype="float32").tobytes()`, 그리고 `db.py` 를 쓰는 모든 곳
  (`json.loads` → `np.frombuffer(..., dtype="float32")`)을 다 같이 고쳐야 하는 큰 작업이고,
  **`life.db` 를 반드시 백업해두고** 진행해야 하는 마이그레이션이다. 벡터를 다시 임베딩할
  필요는 없다(기존 JSON을 읽어서 BLOB으로 다시 쓰기만 하면 된다) — 하지만 되돌리기 어려운
  작업이니 우선순위를 낮게 둔다.
- dtype 을 반드시 `float32` 로 고정해야 한다. 저장할 때 float32, 읽을 때 float64로 읽으면
  384개 숫자가 192개로 잘못 해석돼 차원이 깨진다 — 에러 없이 결과만 미묘하게 틀려지는
  버그이므로 주의.

## 적용 순서 정리

1. **[A] find_cases 캐싱 + [E] 임베딩 모델 미리 로딩** — 지금 바로. 효과가 가장 크고
   위험은 가장 작다 (검색 한 번 8~13초 → 5~9초로 감소, 두 번째 검색부터 체감).
2. **[C] to_passage 하나로 통일** — 5분짜리 작업, 지금 당장 체감 변화는 없지만 미래 사고를
   막는다.
3. **[B] BLOB 전환 + [D] BATCH_SIZE 진행률 출력** — DB 재작업이 필요한 나중 작업.
   `life.db` 백업 후 진행.