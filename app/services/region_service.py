"""
할 일 : 동네 하나가 이 사용자에게 왜 맞는지 설명한다

explain.py 는 TOP 5 전체를 한 번에 설명한다.
이 파일은 지도 핀을 눌렀을 때 그 동네만 설명한다.

차이는 재료다. 여기서는 실제 시설 이름을 쓸 수 있다.
"교육 98점" 이 아니라 "학원 261곳, 그중 입시·보습이 많다" 처럼
근거를 댈 수 있는 것이 이 파일의 존재 이유다.
"""

from collections import Counter

from app.engine.housing import DEAL_COLUMNS, price_fit_line, price_head_lines, region_price_note
from app.repositories.regions import facilities, facility_counts, region_densities, region_extras
from app.ai.llm import ask
from app.prompts.search import REGION_PROMPT


def build_context(gu, dong, query, weights, scores, housing=None):
    """Claude 에게 넘길 재료를 글로 정리한다."""
    lines = [f"## 동네\n서울 {gu} {dong}"]
    
    if query:
        lines.append(f"## 사용자 검색어\n{query}")
        lines.append("")
    
    # 사용자가 중요하게 본 항목 (가중치 3.5 이상)
    high = [k for k, w in (weights or {}).items() if w >= 3.5]
    high_text = ", ".join(high) if high else "뚜렷한 편중 없음"
    lines.append(f"## 사용자가 중시한 항목\n{high_text}")
    lines.append("")
    
    lines.append("## 지표 점수 (서울 427개 동 중 백분위)")
    for k, v in (scores or {}).items():
        lines.append(f"  {k} {round(v)}점")
    lines.append("")
    
    counts = facility_counts(gu, dong)
    if counts:
        lines.append("## 이 동네의 시설 개수")
        for label, n in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"    {label} {n:,}곳")
        lines.append("")
    
    items = facilities(gu, dong, limit=30)
    if items:
        lines.append("## 실제 시설 (일부)")
        for label, rows in items.items():
            names = ", ".join(r["name"] for r in rows[:5])
            lines.append(f"   {label}: {names}")
            
            # 분류가 몰려 있으면 그것도 근거가 된다.
            # "학원 261곳" 보다 "그중 입시·보습이 가장 많다" 가 유용하다
            cats = Counter(r["category"] for r in rows if r["category"])
            if cats:
                # 표본 30개 중의 비율이므로 개수를 그대로 쓰면 오해가 생긴다.
                # "많은 순서" 로만 알려 준다
                top = ", ".join(c for c, _ in cats.most_common(3))
                lines.append(f"    많은 분류 순: {top}")
    
    if housing:
        cols = DEAL_COLUMNS.get((housing["건물유형"], housing["거래유형"]))
        lines.extend(price_head_lines(housing))

        rows = region_densities(list(cols.values())) if cols else []
        row = next((r for r in rows if r["구"] == gu and r["행정동명"] == dong), None)

        if row is None:
            lines.append("시세 데이터 없음")
        else:
            note = region_price_note(gu, dong, housing["건물유형"], housing["거래유형"])
            lines.append(price_fit_line(row, cols, housing, note))

    return "\n".join(lines)


def region_explain(gu, dong, query="", weights=None, scores=None, housing=None):
    """동네 하나에 대한 설명문을 만든다."""
    context = build_context(gu, dong, query, weights, scores, housing)

    messages = [
        ("system", REGION_PROMPT),
        ("human", context),
    ]
    return ask(messages, max_tokens=400).strip()


def get_facilities(gu, dong, limit=5):
    """행정동 하나의 시설 정보. 지도 핀을 눌렀을 때 쓴다."""
    return {
        "counts": facility_counts(gu, dong),
        "items": facilities(gu, dong, limit=limit),
        "extras": region_extras(gu, dong),
    }


# 같은 동네·같은 검색어면 설명이 같으므로 만들어 둔 것을 다시 쓴다.
# 핀을 누를 때마다 Claude 를 부르면 3~5초씩 걸리고 비용도 그만큼 든다.
# 서버가 꺼지면 사라지는 단순한 사전이다 — 지금 규모에는 이걸로 충분하다
_cache = {}


def _housing_key(housing):
    """housing 딕셔너리를 캐시 키에 쓸 수 있는 (해시 가능한) 형태로 바꾼다."""
    if not housing:
        return None
    targets = tuple(sorted(housing["targets"].items()))
    return (housing["건물유형"], housing["거래유형"], targets)


def region_explain_cached(gu, dong, query="", weights=None, scores=None, housing=None):
    """설명을 만들되, 같은 요청이면 저장해 둔 것을 돌려준다."""
    # housing 이 다르면 같은 동네·검색어라도 설명(특히 참고 시세)이 달라지므로 키에 포함한다
    key = (gu, dong, query, _housing_key(housing))

    if key not in _cache:
        _cache[key] = region_explain(gu, dong, query, weights, scores, housing)

    return _cache[key]


#테스트
if __name__ == "__main__":
    weights = {"녹지": 3.3, "안전": 3.3, "교통": 2.6, "상권": 3.2,
               "의료": 3.0, "교육": 4.6, "문화": 2.6}
    scores = {"녹지": 88, "안전": 84, "교통": 48, "상권": 68,
              "의료": 70, "교육": 98, "문화": 25}

    print(region_explain("노원구", "중계1동",
                         query="애들 학원 보내기 좋은 곳",
                         weights=weights, scores=scores))

