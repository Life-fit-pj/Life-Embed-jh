"""
할 일 : 동네 하나가 이 사용자에게 왜 맞는지 설명한다

explain.py 는 TOP 5 전체를 한 번에 설명한다.
이 파일은 지도 핀을 눌렀을 때 그 동네만 설명한다.

차이는 재료다. 여기서는 실제 시설 이름을 쓸 수 있다.
"교육 98점" 이 아니라 "학원 261곳, 그중 입시·보습이 많다" 처럼
근거를 댈 수 있는 것이 이 파일의 존재 이유다.
"""

from collections import Counter

from app.engine.housing import (DEAL_COLUMNS, housing_fit_score,
                                region_price_note, price_gap_text, format_won)
from app.repositories.regions import facilities, facility_counts, region_densities
from app.llm import get_llm

SYSTEM_PROMPT = """당신은 주거지 추천 서비스 LIFE,FIT 의 설명 도우미입니다.
사용자가 지도에서 특정 동네를 눌렀습니다. 그 동네가 왜 이 사람에게 맞는지
2~3문장으로 짧게 설명하세요.

## 반드시 지킬 것

1. 주어진 데이터에 있는 숫자와 시설 이름만 쓰세요.
   지어내지 마세요. 시설 이름은 준 것을 그대로 쓰세요.

2. 점수는 서울 427개 행정동 중 백분위입니다.
   98점 = 상위 2% 라는 뜻입니다.

3. 사용자가 중요하게 본 항목을 중심으로 설명하세요.
   중요도가 낮은 항목은 굳이 언급하지 마세요.

4. 데이터에 없는 것은 알고 있어도 말하지 마세요.
   없는 것: 교육비, 물가, 통학 시간, 지하철 노선명,
   학군 배정, 시설의 품질이나 평판
   지역에 대한 통념(강남은 비싸다 등)도 쓰지 마세요.

   "참고 시세"가 있으면 그 값(중앙값)만 쓰고 실제 매물 가격이 아니라는 점을 밝히세요.
   괄호로 신뢰등급·거래건수·분포가 붙어 있으면 참고하세요 — 거래건수가 적거나 신뢰등급이
   낮으면 표본이 적어 참고용이라고 밝히세요.
   
   "조건 일치도"는 사용자가 말한 가격과 얼마나 가까운지를 0~100으로 나타낸 값입니다
   (100 = 목표가와 일치). 방향은 함께 주어지는 "목표보다 N% 높음/낮음"으로 판단해
   다음처럼 쓰세요.
   - 목표와 비슷하면: "원하시는 가격대에 가깝습니다"
   - 높으면: "원하시는 가격대보다 조금 높은 편입니다"
   - 낮으면: "원하시는 가격대보다 저렴한 편입니다"
   퍼센트 수치("23% 높음")를 그대로 옮겨 쓰지 마세요. 그건 판단 재료이지 사용자에게
   보여 줄 문구가 아닙니다.

   "시세" 점수는 다른 지표와 방향이 반대입니다 — 값이 클수록 그 동네 시세가
   서울에서 낮은(저렴한) 편이라는 뜻입니다. "시세 85점"은 "저렴한 쪽 상위 15%"이지
   "비싸다"가 아닙니다.

   금액을 말할지 말지는 "## 사용자가 원한 가격" 절이 있는지로 판단하세요.
   - 그 절이 있으면: 주어진 금액을 준 그대로 쓰세요. 단위를 바꾸거나 다시 계산하지
     마세요 ("8억원"을 "8,000만원"으로 바꾸는 실수가 실제로 있었습니다).
   - 그 절이 없고 시세 점수만 있으면: 구체적인 금액은 쓰지 말고
     "가격대는 서울에서 저렴한 편입니다" 처럼 한 문장만 덧붙이세요.
   - 둘 다 없으면: 가격 이야기를 아예 꺼내지 마세요.

5. 약점이 있으면 솔직히 덧붙이세요. 장점만 나열하지 마세요.

6. 시설 분류는 "많은 순서" 만 주어집니다. "입시 학원 23곳" 처럼 쓰지 마세요. "입시·보습 계열이 많다" 로 쓰세요.

존댓말로, 3문장을 넘기지 마세요."""


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
        lines.append("")
        # 사용자가 말한 금액을 먼저 밝힌다 — 이게 없으면 Claude 는 "비싸다/싸다"를
        # 무엇과 비교해서 말해야 하는지 모른다
        target_text = " / ".join(f"{field} {format_won(value)}"
                                 for field, value in housing["targets"].items())
        lines.append(f"## 사용자가 원한 가격\n{housing['건물유형']} {housing['거래유형']} {target_text}")
        lines.append("")
        lines.append("## 참고 시세 (동네 전체 중앙값, 실제 매물가 아님)")

        rows = region_densities(list(cols.values())) if cols else []
        row = next((r for r in rows if r["구"] == gu and r["행정동명"] == dong), None)

        if row is None:
            lines.append("시세 데이터 없음")
        else:
            fit = housing_fit_score(row, cols, housing["targets"])
            gap = price_gap_text(row, cols, housing["targets"])
            # 월세면 두 금액을 같이 보여준다 — 월세가 더 중요하니 앞에 쓴다
            parts = [f"{field} {format_won(row[col])}" for field, col in cols.items()]
            note = region_price_note(gu, dong, housing["건물유형"], housing["거래유형"])
            lines.append(
                f"{housing['건물유형']} {housing['거래유형']} " + " / ".join(parts) +
                f" (조건 일치도 {fit}점 · {gap}){note}"
            )


    return "\n".join(lines)


def region_explain(gu, dong, query="", weights=None, scores=None, housing=None):
    """동네 하나에 대한 설명문을 만든다."""
    context = build_context(gu, dong, query, weights, scores, housing)

    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", context),
    ]
    return get_llm(max_tokens=400).invoke(messages).content.strip()


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

