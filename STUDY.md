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

지난번에 이 문서에 적어뒀던 [F]/[G]/[H] 계획은 지웠다 — 그때는 시세 데이터가 "동 하나에 여러
줄"인 원본(`시세_지역별.csv`)뿐이라 별도 표를 만들고 조인하는 계획을 짰는데, 지금은 상황이
바뀌었다. **`master_dataset_v3.csv`에 이미 시세 24개 칼럼이 "동 하나 = 한 줄"로 합쳐져 들어와
있다** — `db.py`가 지금 쓰는 방식(`region_densities`, `to_percentile`)을 거의 그대로 확장해서
쓸 수 있게 됐다는 뜻이다. 그래서 계획을 다시 짠다.

---

# 0. 지금 데이터 상태 (전부 직접 열어서 확인함)

## `master_dataset_v3.csv` — 62 → 86칸

기존 62칸(밀도·전입전출 등)은 그대로고, 시세 24칸이 새로 붙었다. **건물유형별로 4가지
(단독다가구·아파트·연립다세대·오피스텔)**, 거래유형은 매매/전세/월세다.

```
매매가    (4개) 단독다가구_매매_매매가, 아파트_매매_매매가, 연립다세대_매매_매매가, 오피스텔_매매_매매가
보증금    (8개) {건물유형}_전세_보증금, {건물유형}_월세_보증금  (4종 × 2)
월세      (4개) {건물유형}_월세_월세                          (보증금 말고 "매달 내는 돈")
㎡당가    (8개) {건물유형}_매매_㎡당가, {건물유형}_전세_㎡당가  (4종 × 2)
```

칼럼 이름 규칙은 `{건물유형}_{거래유형}_{금액종류}` 로 일관돼 있다. 단위는 **전부 만원**이다
(`아파트_매매_매매가 = 95250.0` → 9억 5,250만원). 이 값은 각 동 안에서 "그 조합의 시세 중앙값"
이다 — 매물 하나하나가 아니라 대표값이라는 걸 잊으면 안 된다(7번 "주의할 점" 참고).

## 새로 생긴 파일 — 용도가 서로 다르다

(`행정동별_시세_전처리.csv`는 `master_dataset_v3`의 부분집합이라 중복이었다 — 정리 완료, 지금
`data/`엔 없다.)

| 파일 | 행 × 칸 | 내용 | 이번 계획에서 쓸 곳 |
|---|---|---|---|
| `행정동별_시세_LLM요약.csv` | 427×4 | 동마다 "아파트매매 면적별 시세"를 사람이 읽는 문장으로 미리 만들어둔 것 (`135㎡초과 520,000만원 / 20-40㎡ ...`) | [3]에서 LLM 설명 프롬프트에 그대로 붙여 쓴다 — 단, **아파트+매매 조합만** 있다는 한계가 있다 |
| `시세_지역별_전처리.csv` | 5,124×22 | 기존 `시세_지역별.csv`와 같은 내용 + **`행정동ID_8자리` 칼럼이 추가됨** | 필요하면 [2]의 면적 필터를 더 정교하게 만들 때 쓴다(선택) |
| `시세_면적구간별_전처리.csv` | 23,948×17 | 기존 `시세_면적구간별.csv`와 같은 내용 + `행정동ID_8자리` 추가 | 위와 동일, 선택 사항 |

`행정동ID_8자리`가 새로 붙었다는 게 중요하다 — `master_dataset_v3`도 같은 이름·같은 형식의
칼럼을 갖고 있어서(`11230680`처럼 8자리 숫자), 이 칼럼으로 정확하게 조인할 수 있게 됐다.
지난 계획에서 걱정했던 "자치구명/지역명이라는 다른 이름 때문에 자동으로 안 엮인다"는 문제가
이 두 파일에서는 해결된 것이다(단, 자동 PK 추론까지는 안 되므로 `MANUAL_FKS`에 직접 적어야
한다 — [5]에서 다룬다).

**(완료)** 옛날 원본 `시세_지역별.csv`/`시세_면적구간별.csv`/중복이던 `행정동별_시세_전처리.csv`는
정리했고, `life.db`도 새 86칸 기준으로 재생성했다 — 자세한 순서는 [4]의 "DB 재생성 순서" 참고.

---

# 1. 시세 점수는 상황에 따라 "방향"이 다르다

처음엔 "시세는 무조건 낮을수록 좋다"로 짰는데, 다시 생각해보면 **이건 사용자가 구체적인
목표가를 안 준 경우에만 맞는 말**이다. 목표가를 준 경우(화면의 "전세 보증금 2억 3,000만"
슬라이더 같은 것)엔 다르다 — 강남처럼 비싼 동네에서도 그중 저렴한 집을 찾는 사람만 있는 게
아니라, 일부러 신축·고가 매물을 찾는 사람도 있다. 그러니 "낮을수록 좋다"가 아니라 **"목표가에
가까울수록 좋다"**가 맞다.

그래서 이 계획엔 시세 점수가 두 가지 성격으로 따로 존재한다.

- **목표가가 없을 때** (접근 A — "시세"를 8번째 지표로, 1~5점짜리 중요도 슬라이더만 있고
  구체적인 금액은 없는 경우) — 다른 7개 지표와 같은 성격의 "일반적으로 저렴한 편을 선호"
  이므로, 여기서만 "낮을수록 좋다"가 맞다. 이 절에서 고치는 `to_percentile()`의 `invert`가
  이 경우에 쓰인다.
- **목표가가 있을 때** (접근 B — 화면의 예산 슬라이더처럼 구체적인 금액을 지정한 경우) —
  "목표가에 가까울수록 좋다"로 완전히 다르게 계산해야 한다. 이건 [2]에서 따로 다룬다 —
  `to_percentile()`의 `invert`로는 표현이 안 되는 계산이라(전체 427개 동 중 등수가 아니라
  "내가 정한 숫자와의 거리"이므로), 새 함수가 필요하다.

## 목표가 없을 때 (접근 A용) — `to_percentile()`에 `invert` 추가

기존 7개 지표(녹지·안전·교통...)는 전부 "숫자가 클수록 좋다"였다. `db.py`의 `to_percentile()`을
그대로 쓰면 "비쌀수록 점수가 높은" 정반대의 결과가 나온다.

```python
# app/core/db.py (원본)
def to_percentile(column, value):
    """어떤 값이 427개 동 중 백분위 몇인지 계산한다."""
    if value is None:
        return None

    total = one('SELECT COUNT(*) FROM master_dataset_v3')[0]
    below = one(
        f'SELECT COUNT(*) FROM master_dataset_v3 WHERE "{column}" <= ?',
        (value,),
    )[0]
    return round(below / total * 100)
```

`below`(자기보다 작거나 같은 동의 개수)를 그대로 점수로 쓰면 "비싼 동네일수록 100점"이 된다.
`invert` 인자를 추가해서, 필요할 때만 뒤집게 고친다.

```python
# app/core/db.py (수정)
def to_percentile(column, value, invert=False):
    """어떤 값이 427개 동 중 백분위 몇인지 계산한다.

    invert=True 면 "낮을수록 높은 점수"로 뒤집는다 (시세처럼 작을수록 좋은 지표용).
    """
    if value is None:
        return None

    total = one('SELECT COUNT(*) FROM master_dataset_v3')[0]
    below = one(
        f'SELECT COUNT(*) FROM master_dataset_v3 WHERE "{column}" <= ?',
        (value,),
    )[0]
    pct = round(below / total * 100)
    return 100 - pct if invert else pct
```

기존 호출부(`region_extras()`의 `to_percentile("쓰레기통_밀도", ...)`)는 `invert`를 안 줘도
기본값 `False`라 그대로 동작한다.

---

# 2. 접근 세 가지 — 로드맵이 정리해 둔 것 그대로

로드맵 원문의 코드 블록은 안 깨져서 그대로 읽었다. 정리하면:

- **접근 A** — 시세를 8번째 지표로 추가한다. 구현이 제일 쉽지만, "예산 3억"처럼 구체적인
  숫자 조건은 반영할 수 없다 — "상대적으로 저렴한 동네"만 위로 올라올 뿐이다.
- **접근 B** — 사용자가 입력한 조건(건물유형·거래유형·금액)에 맞는 동만 추리고, 그 안에서
  기존 7개 지표로 순위를 매긴다. **단, 로드맵의 원안("예산 이하는 다 통과")은 그대로 안 썼다**
  — [1]에서 정리했듯 "목표가에 가까울수록 좋다"가 맞는 방향이라, 걸러내는 기준을 "이하"가
  아니라 "목표가 근처(±허용범위)"로 바꿨다. 구조 자체(마스터 표 하나만 보면 된다)는 로드맵과
  같다.
- **접근 C** — B로 먼저 거르고, "목표가와 얼마나 가까운가" 점수를 참고 정보로 화면에 같이
  보여준다. **최종 권장** — "2억 3천을 찾는다"는 조건에 맞는 동네 위주로 추천하면서, "그중에서도
  얼마나 목표가에 가까운지"까지 보여줄 수 있다.

## 접근 A — `recommend.py`에 8번째 지표 추가

```python
# pipeline/recommend.py (원본)
INDICATOR_COLUMNS = {
    "녹지" : ["공원_밀도"],
    "안전" : ["CCTV_밀도","경찰관서_밀도"],
    "교통": ["버스정류장_밀도", "지하철역_밀도"],
    "상권": ["점포_밀도", "대형점포_밀도"],
    "의료": ["의료기관_밀도"],
    "교육": ["학교_밀도", "학원_밀도"],
    "문화": ["문화시설_밀도", "도서관_밀도"],
}
```

지표 하나가 칼럼 여러 개를 가질 수 있는 구조라, "시세"도 같은 모양으로 넣을 수 있다. 다만
`build_scores()`가 각 칼럼을 `to_percentile()`(지금은 `recommend.py` 자체 버전, [1]에서 고친
`db.py`의 것과는 다른 함수다 — 이름이 같아서 헷갈리기 쉽다)로 바꾸는데, **여기엔 아직
invert가 없다.** 이 함수도 같이 고쳐야 한다.

```python
# pipeline/recommend.py (원본)
def to_percentile(values) :
    order = values.argsort().argsort()
    return order / (len(values) - 1) * 100
```

```python
# pipeline/recommend.py (수정)
def to_percentile(values, invert=False):
    order = values.argsort().argsort()
    pct = order / (len(values) - 1) * 100
    return 100 - pct if invert else pct

INDICATOR_INVERT = {"시세"}   # 이 지표들은 낮을수록 좋다

def build_scores(values):
    scores = {}
    for indicator, cols in INDICATOR_COLUMNS.items():
        invert = indicator in INDICATOR_INVERT
        parts = [to_percentile(values[c], invert=invert) for c in cols]
        scores[indicator] = sum(parts) / len(parts)
    return scores
```

`INDICATORS`(`app/core/config.py`)에도 `"시세"`를 추가해야 `explain.py`의 `with_scores()`가
TOP 5 결과에 시세 점수를 붙여준다. **단, 이 시점엔 사용자가 어떤 건물유형·거래유형을 원하는지
아직 모른다** — `search()`/`recommend_by_weights()`는 검색어/슬라이더만 받지 "아파트 전세"
같은 조건은 안 받기 때문이다. 그래서 접근 A만 단독으로 쓰려면 "아파트 전세 ㎡당가" 하나로
고정하고 시작하는 게 현실적이다 — 이건 임시방편이라, 결국 접근 B(사용자 조건을 실제로 받는
구조)가 필요해진다.

## 접근 B — 목표가 근접 필터 (권장, 로드맵 원안에서 방향 수정)

로드맵의 `filter_by_budget()`은 `df[df[col] <= amount * margin]`처럼 "예산 이하"만 걸렀다 —
"예산은 상한선"이라는 전제다. 이번엔 그 전제를 안 쓴다. 대신 목표가를 기준으로 **위아래
`tolerance`(허용범위, 기본 30%) 안에 있는 동만 후보**로 남긴다 — 너무 싸도(원하는 것과 다른
매물일 가능성), 너무 비싸도 후보에서 뺀다.

```python
# pipeline/housing.py (새로 만드는 파일)
"""
할 일 : 건물유형·거래유형·목표가 조건에 맞는 동을 추리고, 목표가와 얼마나 가까운지 점수를 매긴다.

기존 7개 지표와 다르게 "많고 적음"이 아니라 "사용자가 정한 숫자와 얼마나 가까운가"를 보는
필터다. master_dataset_v3 에 이미 (건물유형, 거래유형) 별 시세가 동마다 한 줄로 있으므로
새 표를 만들 필요 없이 여기서 바로 걸러낸다.
"""

from app.core.db import region_densities

# {건물유형}_{거래유형}_{금액종류} 규칙 그대로 매핑한다.
# 매매·전세는 금액이 하나("예산")뿐이지만, 월세는 다르다 — 보증금(목돈)과 월세(매달 나가는 돈)가
# 따로 있고, 사용자가 실질적으로 더 신경 쓰는 건 월세 쪽이다. 그래서 월세 거래에서는 "예산"을
# 월세 칼럼에 매핑하고, 보증금은 있으면 참고하는 보조 조건(secondary)으로 따로 받는다.
DEAL_COLUMNS = {
    ("단독다가구", "매매"): {"예산": "단독다가구_매매_매매가"},
    ("아파트",     "매매"): {"예산": "아파트_매매_매매가"},
    ("연립다세대", "매매"): {"예산": "연립다세대_매매_매매가"},
    ("오피스텔",   "매매"): {"예산": "오피스텔_매매_매매가"},

    ("단독다가구", "전세"): {"예산": "단독다가구_전세_보증금"},
    ("아파트",     "전세"): {"예산": "아파트_전세_보증금"},
    ("연립다세대", "전세"): {"예산": "연립다세대_전세_보증금"},
    ("오피스텔",   "전세"): {"예산": "오피스텔_전세_보증금"},

    ("단독다가구", "월세"): {"예산": "단독다가구_월세_월세", "보증금": "단독다가구_월세_보증금"},
    ("아파트",     "월세"): {"예산": "아파트_월세_월세",     "보증금": "아파트_월세_보증금"},
    ("연립다세대", "월세"): {"예산": "연립다세대_월세_월세", "보증금": "연립다세대_월세_보증금"},
    ("오피스텔",   "월세"): {"예산": "오피스텔_월세_월세",   "보증금": "오피스텔_월세_보증금"},
}

# 필드별 가중치. "월세가 보증금보다 더 중요한 지표"라는 기준을 숫자로 표현한 것이다.
# 매매·전세는 필드가 "예산" 하나뿐이라 이 가중치가 어차피 안 쓰인다.
FIELD_WEIGHT = {"예산": 0.7, "보증금": 0.3}


def price_fit_score(price, target, tolerance=0.3):
    """목표값 하나와 얼마나 가까운지 0~100점으로 매긴다.

    100 = 목표값과 정확히 일치. tolerance(기본 30%)만큼 벗어나면 0점.
    너무 싸도(-30%) 너무 비싸도(+30%) 똑같이 감점되는 대칭 구조다 —
    "저렴할수록 무조건 좋다"가 아니라 "목표값에서 벗어날수록 안 좋다"는 뜻이라서다.
    matching_regions() 의 tolerance 와 같은 값을 써야 앞뒤가 맞는다.
    """
    if price is None or target in (None, 0):
        return None
    diff_ratio = abs(price - target) / target
    return max(0, round(100 * (1 - diff_ratio / tolerance)))


def housing_fit_score(row, cols, targets, tolerance=0.3):
    """한 동네가 사용자 조건(들)과 얼마나 맞는지 0~100점으로 합친다.

    cols: DEAL_COLUMNS[(건물유형, 거래유형)] 처럼 {"예산": 칼럼명} 또는
          {"예산": 칼럼명, "보증금": 칼럼명}(월세) 형태.
    targets: 사용자가 실제로 입력한 값. {"예산": 70} 또는 {"예산": 70, "보증금": 5000}.

    필드가 하나면(매매·전세) price_fit_score 하나만 쓰는 것과 같은 결과다.
    필드가 둘이면(월세) FIELD_WEIGHT 로 가중 평균한다 — 월세가 보증금보다 크게 반영된다.
    """
    total_w, total_score = 0, 0
    for field, col in cols.items():
        target = targets.get(field)
        if target is None:
            continue
        score = price_fit_score(row.get(col), target, tolerance)
        if score is None:
            continue
        w = FIELD_WEIGHT.get(field, 1.0)
        total_score += score * w
        total_w += w
    return round(total_score / total_w) if total_w else None


def matching_regions(건물유형, 거래유형, targets, tolerance=0.3, fallback=20):
    """조건(들)에 맞는 동 이름("구 동" 형태) 목록을 돌려준다.

    targets 예시: {"예산": 65000}                    매매·전세
                {"예산": 70, "보증금": 5000}          월세 (예산=월세, 보증금은 옵션)

    후보가 너무 적으면(5개 미만) 종합 점수(housing_fit_score)가 가장 높은 fallback 개를
    대신 돌려준다 — "이 조건엔 맞는 곳이 없다"고 빈 결과를 주는 것보다, 대안을 보여주는 쪽이 낫다.
    """
    cols = DEAL_COLUMNS.get((건물유형, 거래유형))
    if not cols:
        return []

    rows = region_densities(list(cols.values()))
    scored = [(r, housing_fit_score(r, cols, targets, tolerance)) for r in rows]
    scored = [(r, s) for r, s in scored if s is not None]

    candidates = [r for r, s in scored if s > 0]   # tolerance 안에 조금이라도 걸치는 동
    if len(candidates) < 5:
        candidates = [r for r, s in sorted(scored, key=lambda x: -x[1])[:fallback]]

    return [f"{r['구']} {r['행정동명']}" for r in candidates]
```

`region_densities()`는 이미 `db.py`에 있는 함수를 그대로 재사용한 것이다 — "칼럼 이름 목록을
주면 427개 동의 그 칼럼 값을 돌려준다"는 지금 하는 일이 시세 칼럼에도 그대로 들어맞는다.
새 조회 함수를 따로 만들 필요가 없다는 게, 지난 계획보다 이번이 훨씬 간단해진 이유다.

`price_fit_score()`는 [1]에서 고친 `db.py`의 `to_percentile(..., invert=True)`와는 다른
계산이라는 점을 짚어둔다 — `to_percentile`은 "427개 동 중 몇 등인가"(전체 분포 안에서의
위치)를 보는 것이고, `price_fit_score`는 등수와 무관하게 "내가 정한 숫자와 얼마나 가까운가"만
본다. 그래서 이 둘은 서로 대체할 수 있는 관계가 아니라, 목표가가 있냐 없냐에 따라 아예 다른
함수를 쓰는 것이다.

## `recommend_by_weights()` 호출부 수정 — 접근 C (B 먼저, A는 참고용)

```python
# app/features/pipeline_api.py (원본)
def recommend_by_weights(weights, top_k=5):
    """가중치 → TOP 5. 슬라이더로 바로 올 때 쓴다 (검색어 없음)."""
    r = get_ready()
    result = recommend(r["names"], r["scores"], r["relative"], weights, top_k=top_k)
    return with_scores(result, r["names"], r["scores"])
```

```python
# app/features/pipeline_api.py (수정)
import numpy as np
from pipeline.housing import matching_regions

def recommend_by_weights(weights, top_k=5, housing=None):
    """가중치 → TOP 5. housing 을 주면 그 조건에 맞는 동으로 먼저 추린다.

    housing 예시(전세): {"건물유형": "아파트", "거래유형": "전세", "targets": {"예산": 65000}}
    housing 예시(월세): {"건물유형": "아파트", "거래유형": "월세",
                       "targets": {"예산": 70, "보증금": 5000}}   (단위: 만원)
    """
    r = get_ready()
    names, scores, relative = r["names"], r["scores"], r["relative"]

    if housing:
        candidates = set(matching_regions(**housing))
        keep = np.array([n in candidates for n in names])
        names = [n for n, k in zip(names, keep) if k]
        scores = {ind: arr[keep] for ind, arr in scores.items()}
        relative = {ind: arr[keep] for ind, arr in relative.items()}

    result = recommend(names, scores, relative, weights, top_k=top_k)
    return with_scores(result, names, scores)
```

`search()`(검색어 경로)도 같은 방식으로 `housing`을 받아 그대로 넘기면 된다. `housing_fit_score()`
는 이 필터를 통과한 동네들 안에서 "조건과 얼마나 맞는가"를 보여주는 **참고 점수**로만 쓴다
— TOP 5의 순서를 매기는 데는 안 쓰고(순서는 기존 7개 지표가 정한다), 화면에 "이 동네 아파트
월세는 조건과 88% 일치(월세 위주로 계산)"처럼 곁들이는 용도다. `detailed`의 각 동네에 대해
`housing_fit_score(region_densities(list(cols.values()))에서 찾은 행, cols, housing["targets"])`
를 계산해 붙이면 된다.

---

# 3. LLM 연동

## 검색어에서 예산 조건 뽑아내기

```python
# pipeline/weights.py — ask_claude() 의 응답 스키마에 추가
{
  "녹지": 1~5, "안전": 1~5, "교통": 1~5, "상권": 1~5,
  "의료": 1~5, "교육": 1~5, "문화": 1~5,
  "건물유형": "단독다가구|아파트|연립다세대|오피스텔|null",
  "거래유형": "매매|전세|월세|null",
  "예산": 숫자(단위 만원) 또는 null,   // 매매=매매가, 전세=보증금, 월세=월세(월 임대료)
  "보증금": 숫자(단위 만원) 또는 null  // 월세일 때만 의미 있다. 매매·전세는 항상 null
}
```

"전세 4억 정도로 조용한 동네" 같은 검색어에서 Claude가 `{"거래유형":"전세", "예산":40000, ...}`
를 뽑아내게 하는 것이다. "월세 70에 보증금 5천 정도"라면 `{"거래유형":"월세", "예산":70,
"보증금":5000, ...}`가 된다 — "예산"이 거래유형별로 가장 중요한 금액(매매가/보증금/월세)을
가리키도록 통일해뒀다([2]의 `DEAL_COLUMNS`가 이 규칙 그대로다). 건물유형·거래유형·예산 셋 중
하나라도 `null`이면(예: "조용한 동네"처럼 예산 언급이 없으면) `housing` 필터를 아예 건너뛰고
지금처럼 전체 427개 동을 대상으로 추천한다.

슬라이더로 직접 조건을 주는 화면(검색어 없이 필터만 쓰는 경로)에서도 이 `null` 처리를 그대로
쓴다 — 화면에 "가격 상관없음" 체크박스를 추가해서, 체크하면 건물유형·거래유형·예산·보증금을
아예 안 보내거나 `null`로 보내도록 프론트에 요청해뒀다(`to_frontend.md` 1번). 슬라이더를
최소값으로 내리는 것과는 다른 동작이라는 점이 중요하다 — 최소값도 여전히 "그 가격대를
원한다"는 목표가로 처리되기 때문에, "가격은 안 봐도 된다"는 이 체크박스로만 표현할 수 있다.

`search()`를 부르기 전에, Claude가 준 이 JSON을 [2]의 `matching_regions()`가 기대하는 모양으로
한 번 바꿔줘야 한다.

```python
# app/features/pipeline_api.py (search() 안, 원본 뒤에 추가)
targets = {"예산": draft["예산"]}
if draft["거래유형"] == "월세" and draft.get("보증금"):
    targets["보증금"] = draft["보증금"]

housing = None
if draft["건물유형"] and draft["거래유형"] and draft["예산"]:
    housing = {"건물유형": draft["건물유형"], "거래유형": draft["거래유형"], "targets": targets}
```

> **참고**: 지금 스키마는 "4억 정도"와 "4억 이하로"를 구분 못 하고 둘 다 `예산: 40000`으로
> 뽑는다. [2]에서 정한 대로 이 숫자는 항상 "목표가"(근접도 기준)로 처리된다. 사용자가 "4억
> 넘지 않게"처럼 명확히 상한선을 말하는 경우까지 구분하고 싶다면, 스키마에 `예산_기준:
> "목표|상한"` 같은 필드를 추가하고 `matching_regions()`에 상한 전용 분기를 넣어야 한다 —
> 지금 계획에는 없는, 나중에 필요해지면 추가할 확장 지점이다.

> **확인 필요**: 로드맵 원문에 "빌라"→연립다세대, "원룸"→오피스텔 같은 별칭 매핑이 있는 것
> 같은데(인코딩이 깨져서 완전히 확실치 않다), 실제 데이터의 `건물용도`엔 `단독다가구·아파트·
> 연립다세대·오피스텔` 네 가지만 있다(직접 확인함). 프론트엔드 드롭다운이 "빌라"·"원룸" 같은
> 다른 이름을 쓴다면, `ask_claude()`가 그 이름을 그대로 뽑아내지 않고 위 네 가지 중 하나로
> 바꿔서 뽑도록 프롬프트에 별칭 표를 넣어줘야 한다. 프론트엔드의 실제 드롭다운 값을 먼저
> 확인할 것.

## 설명문에 시세 붙이기

```python
# pipeline/explain.py (원본) — SYSTEM_PROMPT 중
3. 데이터에 없는 것을 물으면 없다고 답하세요.
   없는 것: 집값, 전월세, 교육비, 물가, 생활비, 통학 시간, 지하철 노선명, 학교 이름, 구체적인 시설 이름, 유동인구, 소음 수치
```

```python
# pipeline/explain.py (수정) — SYSTEM_PROMPT 중
3. 데이터에 없는 것을 물으면 없다고 답하세요.
   없는 것: 교육비, 물가, 생활비, 통학 시간, 지하철 노선명, 학교 이름, 유동인구, 소음 수치
   시세(매매가·보증금·월세)는 아래 "참고 시세"에 준 값만 쓰세요. 이 값은 동네 전체의
   중앙값이지 실제 매물 가격이 아니라는 점을 밝히세요.
```

`region_explain.py`의 "없는 것" 목록에서도 "집값, 전월세"를 똑같이 빼야 한다.

`build_context()`엔 사용자가 고른 조건의 시세를 넣는다. `아파트+매매`라면 이미 있는
`행정동별_시세_LLM요약.csv`를 그대로 갖다 쓰면 되고, 그 외 조합(전세·월세·다른 건물유형)은
그 파일에 없으니 `master_dataset_v3`의 칼럼 값을 직접 문장으로 만든다.

```python
# pipeline/explain.py (수정) — build_context()
def build_context(query, weights, detailed, cases, housing=None):
    ...
    if housing:
        from pipeline.housing import DEAL_COLUMNS, housing_fit_score
        cols = DEAL_COLUMNS.get((housing["건물유형"], housing["거래유형"]))
        lines.append("")
        lines.append("## 참고 시세 (동네 전체 중앙값, 실제 매물가 아님)")
        for d in detailed:
            gu, dong = d["name"].split(" ", 1)
            rows = region_densities(list(cols.values()))   # 매번 다시 읽는 대신 get_ready() 캐싱 권장
            row = next((r for r in rows if r["구"] == gu and r["행정동명"] == dong), None)
            if row is None:
                lines.append(f"{d['name']}: 시세 데이터 없음")
                continue

            fit = housing_fit_score(row, cols, housing["targets"])
            # 월세면 두 금액을 같이 보여준다 — 월세가 더 중요하니 앞에 쓴다
            parts = [f"{field} {row[col]:,.0f}만원" for field, col in cols.items()]
            lines.append(f"{d['name']}: {housing['건물유형']} {housing['거래유형']} " +
                         " / ".join(parts) + f" (조건 일치도 {fit}점)")
    ...
```

(TOP 5 다섯 곳만 조회하면 되므로 매번 427개 행을 다 읽어와도 성능엔 문제없지만, 신경 쓰인다면
`get_ready()`에서 `region_densities()` 결과를 미리 캐싱해두고 `d["name"]`으로 바로 찾는 식으로
바꿔도 된다 — `load_regions()`가 이미 하고 있는 패턴과 같다.)

## 주의 — 목록에서 빼는 것과 데이터를 넣는 것은 같이 해야 한다

"없는 것" 목록에서 항목만 지우고 `build_context()`에 실제 값을 안 넣으면, Claude가 "모른다"고
답하거나 숫자를 지어낼 위험이 생긴다. 반드시 같은 작업 안에서 같이 고쳐야 한다.

---

# 4. 작업 순서

로드맵 6번 섹션과 같은 뼈대인데, 실제 파일/함수 이름으로 구체화했다.

1. **DB 재생성** — 아래 "DB 재생성 순서" 참고. `python -m pipeline.schema`로 새 86칸
   `master_dataset_v3`를 반영한다.
2. **`app/core/db.py`** — `to_percentile()`에 `invert` 인자 추가 ([1]).
3. **`pipeline/recommend.py`** — 자체 `to_percentile()`에도 `invert` 추가, `INDICATOR_INVERT`
   추가 (접근 A를 참고 점수로 쓸 경우).
4. **`pipeline/housing.py`** 신설 — `DEAL_COLUMNS`, `price_fit_score()`, `housing_fit_score()`,
   `matching_regions()` ([2]).
5. **`app/features/pipeline_api.py`** — `recommend_by_weights()`, `search()`에 `housing` 인자
   추가, Claude 응답을 `targets` 모양으로 바꾸는 부분 포함 ([3]).
6. **`pipeline/weights.py`** — `ask_claude()` 응답 스키마에 건물유형·거래유형·예산·보증금 추가
   ([3]).
7. **`pipeline/explain.py`, `app/features/region_explain.py`** — "없는 것" 목록 수정 + 시세
   컨텍스트 추가, 동시에 진행 ([3]).
8. **검증**
   - "아파트 전세 4억" 검색 → 결과 5곳이 전부 `아파트_전세_보증금`이 4억의 ±30%(2.8억~5.2억)
     안에 드는지 확인. 4억보다 한참 싼 동(예: 1억)이 무조건 1등으로 올라오지 않는지도 같이
     확인 — "낮을수록 좋다"로 잘못 짜였을 때 나는 대표적인 증상이다.
   - "아파트 전세 1000만원"처럼 시세와 동떨어진 극단값 → fallback(목표가에 가장 가까운
     20곳)이 작동하는지 확인
   - "아파트 월세 70에 보증금 5천" 검색 → 월세가 목표(70)에 가깝지만 보증금은 목표(5천)와
     크게 다른 동과, 반대로 보증금만 가까운 동을 비교해서 **월세가 가까운 쪽이 더 높은
     `housing_fit_score`를 받는지** 확인 — `FIELD_WEIGHT`가 실제로 반영됐는지 보는 것이다.
   - 예산 조건 없는 검색("조용한 동네") → 기존과 똑같이 427개 동 전체를 대상으로 하는지 확인
   - `region_explain.py` 단일 동네 설명에도 시세가 자연스럽게 들어가는지 확인

---

## DB 재생성 순서

`master_dataset_v3.csv`가 62→86칸으로 바뀌었으니 `life.db`를 통째로 다시 만들어야 한다. 순서가
중요하다 — `schema.py`가 기존 `life.db` 파일을 **통째로 지우고 새로 만들기** 때문에, 이미
임베딩해둔 `kb_chunk`/`member_chunk` 표도 같이 사라진다. 그래서 스키마 재생성 → 재임베딩 순서를
지켜야 한다.

1. **`data/*.csv``master_dataset_v3.csv` 같은 걸 열어둔
   상태면 `~$master_dataset_v3.csv` 같은 잠금 임시 파일이 `data/`에 같이 생긴다. 이 파일은
   이진 쓰레기값(null 문자 포함)이라 `schema.py`가 CSV인 줄 알고 읽다가
   `sqlite3.ProgrammingError: the query contains a null character`로 죽는다(직접 겪음,
   2026-08-31). `EXCLUDE_PREFIX`에 `"~$"`를 추가해서 이제는 자동으로 걸러지지만, 애초에 CSV를
   엑셀로 열어두지 않는 게 제일 깔끔하다 — 열려있다면 저장하지 말고 닫을 것.
2. **`python -m pipeline.schema`** — CSV들을 통째로 다시 읽어 `life.db`를 새로 만든다.
   `life.db가 이미 존재합니다! 다시 만들까요?`라고 물으면 `y`. 끝나면 표 개수만큼
   `✅ ... 표 생성` / `✅ ... 줄 적재`가 쭉 나온다. `⚠️`가 하나라도 보이면(CSV 행수와 적재
   행수가 다른 경우) 그 표는 뭔가 잘못 읽힌 것이니 원인을 먼저 찾을 것.
3. **`python -m pipeline.embed_kb`** — 1번에서 지워진 `kb_chunk` 표를 다시 만들고, `kb_chunk.csv`
   (22,500개, `data/`에 이미 있음)를 다시 임베딩한다. 약 5분.
4. **`python -m pipeline.embed_member`** — 마찬가지로 `member_chunk` 표를 다시 만들고,
   `nemotron.csv`에서 회원 100명을 다시 임베딩한다. 약 30초. (`data/nemotron.csv`가 로컬에
   없으면 `FileNotFoundError` — `CLAUDE.md`의 "Data directory" 절 참고.)
5. **확인** — `python -c "import app.core.config"`로 설정 파일 자체가 안 깨졌는지 먼저 보고,
   아래로 새 칼럼과 새 표가 다 들어갔는지 확인한다.

   ```python
   import sqlite3
   con = sqlite3.connect("data/life.db")
   cols = [r[1] for r in con.execute("PRAGMA table_info(master_dataset_v3)").fetchall()]
   print(len(cols))  # 86 이어야 한다
   tables = [r[0] for r in con.execute(
       "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
   print("시세_지역별_전처리" in tables, "시세_면적구간별_전처리" in tables,
         "행정동별_시세_LLM요약" in tables)  # 셋 다 True 여야 한다
   ```
6. **`python -m app.features.pipeline_api`** — `search("얘들 학원 보내기 좋은 곳")`을 돌려서
   TOP 5와 설명문이 정상 출력되는지 마지막으로 확인한다. 여기까지 되면 [4]의 검증 목록(8번)을
   이어서 진행한다.

---

# 5. `MANUAL_FKS` (선택 — 지금 당장 필요치 않음)

`시세_지역별_전처리.csv`, `시세_면적구간별_전처리.csv`를 굳이 DB에 표로 넣어서
`master_dataset_v3`와 정식으로 엮고 싶다면(예: 나중에 면적구간별 정밀 필터를 만들 때),
`행정동ID_8자리`로 연결할 수 있다.

```python
# pipeline/schema.py (수정) — MANUAL_FKS
MANUAL_FKS = {
    "customers": [
        (["city", "city_dong"], "master_dataset_v3", ["구", "행정동명"]),
    ],
    "시세_지역별_전처리": [
        (["행정동ID_8자리"], "master_dataset_v3", ["행정동ID_8자리"]),
    ],
    "시세_면적구간별_전처리": [
        (["행정동ID_8자리"], "master_dataset_v3", ["행정동ID_8자리"]),
    ],
}
```

지금 계획(접근 B)은 `master_dataset_v3` 하나만 보고도 끝나므로 이 표들을 안 써도 된다 — 나중에
"59㎡짜리만 정확히" 같은 면적구간 단위 정밀도가 필요해지면 그때 꺼내 쓸 자리로 남겨둔다.

---

# 6. `chat.py` — 후속 질문에도 시세·생활여건을 반영한다

`explain.py`, `region_explain.py`는 고쳤는데 **`chat.py`(추천 뒤 이어지는 후속 질문 답변)는
아직 하나도 안 건드렸다.** 실제로 써보니 이 증상이 그대로 나왔다:

- "주변 시세가 궁금해" → "저희 서비스에서 제공 안 해요" (시세 데이터를 아예 안 넘겨주고 있음)
- "중계1동 평균 월세는 얼마야?" → "월세 정보가 없어요" (마찬가지)
- "가장 조용한 동네가 어디야?" → "'조용함' 지표가 없어서 말씀드리기 어려워요"

앞의 둘은 예상한 원인(시세를 안 넘김)이지만, **세 번째는 다르다** — `db.py`의 `region_extras()`
에 소음 정보(`소음_주간_구`, `소음_야간_구`)가 원래부터 있었는데, `chat.py`가 그 함수를 아예
안 부르고 있어서 "없다"고 답한 것이다. 즉 데이터가 없는 게 아니라 **연결이 안 돼 있던 것**이다.

## 왜 `explain.py`와 다르게 고쳐야 하나

`explain.py`/`region_explain.py`는 "어떤 조건을 원하는지"(`housing`)를 이미 알고 물어본다.
그런데 `chat.py`는 다르다 — 사용자가 애초에 가격 필터를 안 걸고 검색했을 수도 있고, 나중에
"월세는 얼마야?" 처럼 즉흥적으로 물어볼 수도 있다. **어떤 건물유형·거래유형을 물어볼지 미리
알 수 없다.** 그래서 [2]의 `DEAL_COLUMNS`처럼 조건 하나만 골라 조회하는 방식이 아니라,
**동네 하나의 시세 전부(건물유형 4종 × 거래유형 3종)를 한 번에 문장으로 만들어 컨텍스트에
넣어두고, 그중 뭘 답할지는 Claude가 질문을 보고 고르게** 한다.

## `pipeline/housing.py`에 함수 하나 추가

```python
# pipeline/housing.py (추가)
def region_price_lines(gu, dong):
    """동네 하나의 시세 전부를 건물유형별 한 줄씩 문장으로 만든다.

    housing_fit_score() 와 다르게 목표가와 비교하지 않는다 — chat.py 처럼 사용자가 어떤
    조건("월세 얼마야?")을 물어볼지 미리 모르는 곳에서, 있는 그대로의 값을 전부 보여주고
    Claude 가 질문에 맞는 걸 골라 답하게 하려는 용도다.
    """
    all_cols = sorted({col for cols in DEAL_COLUMNS.values() for col in cols.values()})
    rows = region_densities(all_cols)
    row = next((r for r in rows if r["구"] == gu and r["행정동명"] == dong), None)
    if row is None:
        return []

    lines = []
    for 건물유형 in ("단독다가구", "아파트", "연립다세대", "오피스텔"):
        parts = []
        for 거래유형 in ("매매", "전세", "월세"):
            cols = DEAL_COLUMNS.get((건물유형, 거래유형))
            if not cols:
                continue
            for field, col in cols.items():
                value = row.get(col)
                if value is None:
                    continue
                # "예산" 필드는 그 거래유형 자체를 라벨로 쓴다 (매매가→매매, 보증금→전세, 월세→월세)
                label = 거래유형 if field == "예산" else field
                parts.append(f"{label} {value:,.0f}만원")
        if parts:
            lines.append(f"{건물유형}: " + " · ".join(parts))
    return lines
```

`DEAL_COLUMNS`를 [2]에서 만든 그대로 재사용한다 — 새 매핑을 또 만들 필요가 없다. 결과는 이런
문장이 된다: `아파트: 매매 95,250만원 · 전세 65,000만원 · 월세 88만원 · 보증금 7,415만원`.

## `chat.py` 수정

```python
# app/features/chat.py (원본)
from app.core.db import facilities, facility_counts, facility_categories
from app.core.llm import get_llm
```

```python
# app/features/chat.py (수정)
from app.core.db import facilities, facility_counts, facility_categories, region_extras
from app.core.llm import get_llm
from pipeline.housing import region_price_lines
```

프롬프트의 "없는 것" 목록에서도 시세를 빼야 한다 — `explain.py`에서 했던 것과 같은 이유다.

```python
# app/features/chat.py (원본) — SYSTEM_PROMPT 중
3. 데이터에 없는 것을 물으면 없다고 답하세요.
   없는 것: 집값, 전월세, 관리비, 교육비, 통학 시간, 지하철 노선명,
   학군 배정, 시설의 품질이나 평판, 주민 성향
   지역에 대한 통념(강남은 비싸다 등)도 쓰지 마세요.
```

```python
# app/features/chat.py (수정) — SYSTEM_PROMPT 중
3. 데이터에 없는 것을 물으면 없다고 답하세요.
   없는 것: 관리비, 교육비, 통학 시간, 지하철 노선명, 학군 배정, 시설의 품질이나 평판, 주민 성향
   지역에 대한 통념(강남은 비싸다 등)도 쓰지 마세요.

   시세(매매가·보증금·월세)는 아래 "시세" 항목에 준 값만 쓰세요 — 동네 전체 중앙값이지
   실제 매물 가격이 아니라는 점을 밝히세요. 사용자가 특정 조건(예: "월세")을 물으면 그 항목만
   골라 답하세요.

   소음처럼 "생활여건" 항목은 구(자치구) 단위 평균입니다. 그 동네만의 값인 것처럼 말하지 말고
   반드시 "OO구 평균으로는"이라고 밝히세요.
```

`build_context()`에 동네별로 두 블록을 추가한다 — 시세(전부)와 생활여건(구 단위).

```python
# app/features/chat.py (수정) — build_context() 의 for r in regions or [] 루프 안,
# facility_categories 를 채우는 부분 바로 다음에 추가
        parts = name.split(" ", 1)
        if len(parts) == 2:
            gu, dong = parts
            # (기존 facility_counts / facility_categories 코드는 그대로)

            price_lines = region_price_lines(gu, dong)
            if price_lines:
                lines.append("     시세 (동네 전체 중앙값, 실제 매물가 아님):")
                for pl in price_lines:
                    lines.append(f"       {pl}")

            extras = region_extras(gu, dong)
            noise = extras.get("소음_주간_구"), extras.get("소음_야간_구")
            if any(v is not None for v in noise):
                lines.append(
                    f"     생활여건({gu} 구 단위 평균): 소음 주간 {noise[0]} · 야간 {noise[1]}"
                    + (f" · 거주안정성 {extras['거주안정성_점수']}점"
                       if extras.get("거주안정성_점수") is not None else "")
                )
```

## 주의할 점

- **`region_extras()`는 `db.py`에 이미 있던 함수를 그대로 갖다 쓴 것이다.** 새로 만들지 않았다
  — `region_explain.py`도 아직 이 함수를 안 쓰고 있으니, "조용한 동네"류 질문은 거기서도 같은
  방식으로 고칠 수 있다(이번엔 범위 밖이라 안 건드렸다).
- **`region_price_lines()`는 동네 하나당 매번 `region_densities(16개 칼럼)`을 새로 부른다.**
  TOP 5 동네만 다루므로 지금 규모엔 문제없지만, 호출이 잦아지면 [4]의 `region_densities()`
  캐싱 권장 사항과 같은 방식으로 최적화할 수 있다.
- **`SYSTEM_PROMPT`의 5번 규칙("답은 3~4문장으로 짧게")은 그대로 둔다.** 시세·생활여건까지
  들어가면 컨텍스트가 길어지지만, 답변 길이 제한은 그대로 유지해야 한다 — 안 그러면 질문
  하나에 모든 정보를 다 쏟아내는 답이 나온다.

---

# 7. 주의할 점

- **시세는 동네 전체의 중앙값이지, 특정 매물 가격이 아니다.** 화면·설명문 어디서든 "이 동네
  아파트 전세는 3억 8천이에요"가 아니라 "중앙값이 3억 8천이에요"로 표현해야 한다. 실제 매물은
  이보다 훨씬 위아래로 퍼져 있다(원본 `시세_지역별.csv`의 `매매가_25`/`매매가_75`를 보면 편차가
  꽤 크다).
- **`신뢰등급`·`출처` 정보는 `master_dataset_v3`엔 안 남아있다.** 원본 `시세_지역별.csv`에는
  `신뢰등급`(높음/보통), `출처`(자치구/법정동/해당지역 등 — 거래가 적어 더 넓은 단위 평균을
  대신 쓴 경우도 있다는 뜻)가 있었는데, `master_dataset_v3`로 합쳐지면서 이 정보가 빠졌다.
  그러니 "이 값이 표본이 적어 부정확할 수 있다"는 걸 지금 구조로는 구분할 수 없다 — 필요하면
  `시세_지역별_전처리.csv`를 따로 조회해서 보충해야 한다.
- **월세는 "보증금"과 "월세" 두 금액을 같이 본다.** `아파트_월세_보증금`과 `아파트_월세_월세`는
  다른 칼럼이다. "월세가 보증금보다 중요한 지표"라는 걸 `FIELD_WEIGHT = {"예산": 0.7, "보증금":
  0.3}`로 반영했다 — 이 0.7/0.3 비율도 `tolerance`처럼 감으로 잡은 값이라, 실제로 써보면서
  조정이 필요할 수 있다. 사용자가 보증금을 안 주면(월세만 입력) `targets`에 `"보증금"` 키가
  아예 없으니 `housing_fit_score()`가 자동으로 월세 하나만 보고 계산한다.
- **`건물유형` 별칭은 반드시 프론트엔드 코드로 재확인할 것.** "빌라"·"원룸" 같은 표시용 이름이
  실제로 쓰이고 있다면, `ask_claude()` 프롬프트와 `DEAL_COLUMNS`의 키를 원본 데이터 값
  (단독다가구/아파트/연립다세대/오피스텔) 네 가지로 반드시 정규화해야 한다.
- **`행정동별_시세_LLM요약.csv`는 아파트+매매 조합만 있다.** 전세·월세나 다른 건물유형을
  설명할 땐 이 파일이 아니라 `master_dataset_v3`의 칼럼 값을 그때그때 문장으로 만들어야 한다
  ([3]의 예시 코드가 그렇게 하고 있다).
- **`tolerance=0.3`(±30%)은 감으로 잡은 값이다.** 너무 좁으면(예: ±10%) 후보가 자주 5개
  미만이 돼서 fallback만 계속 타게 되고, 너무 넓으면(예: ±50%) 필터를 건 의미가 없어진다.
  실제 시세 분포(동네·건물유형마다 편차가 다르다)를 보고 조정이 필요할 수 있다.
