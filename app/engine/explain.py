"""
할 일 : TOP 5 추천 결과를 사용자에게 보여줄 설명문으로 만든다

07번이 가중치를, 08번이 TOP 5 를 만들었다.
여기서는 그 결과에 근거 수치와 유사 사례를 붙여 Claude 에게 넘기고,
사람이 읽을 설명을 받는다.

Claude 가 숫자를 지어내지 못하도록 프롬프트에서 강하게 제한한다.
"""

import numpy as np

from app.engine.housing import (DEAL_COLUMNS, housing_fit_score,
                                region_price_note, price_gap_text, format_won)
from app.engine.recommend import load_regions, build_scores, build_relative, recommend
from app.tables.chunks import kb_chunks
from app.tables.regions import region_densities
from app.ai.embedder import embed_query, to_query
from app.ai.llm import ask


SYSTEM_PROMPT = """당신은 주거지 추천 서비스 LIFE,FIT 의 설명 도우미입니다.
계산이 끝난 추천 결과를 사용자에게 설명하는 역할입니다.

## 반드시 지킬 것

1. 주어진 데이터에 있는 숫자만 쓰세요.
   "공원이 많아요" 처럼 데이터에 없는 표현을 지어내지 마세요.
   점수를 인용할 때는 "교육 98점" 처럼 실제 값을 그대로 쓰세요.

2. 점수는 서울 427개 행정동 중 백분위입니다.
   98점 = 상위 2%, 50점 = 중간 이라는 뜻입니다.
   "많다/적다" 가 아니라 "다른 동네와 비교해 어느 위치인지" 로 설명하세요.

3. 데이터에 없는 것을 물으면 없다고 답하세요.
   없는 것: 교육비, 물가, 생활비, 통학 시간, 지하철 노선명, 학교 이름, 구체적인 시설 이름, 유동인구, 소음 수치

   시세(매매가·보증금·월세)는 아래 "참고 시세"에 준 값만 쓰세요. 이 값은 동네 전체의
   중앙값이지 실제 매물 가격이 아니라는 점을 밝히세요.
   괄호로 신뢰등급·거래건수·분포가 붙어 있으면 참고하세요 — 거래건수가 적거나 신뢰등급이
   낮으면(예: "낮음") 그 시세는 표본이 적어 참고용이라고 밝히세요. 분포(예: "2억 8,000만원~
   4억 2,000만원")는 실제 매물 가격이 그 폭 안에 퍼져 있다는 뜻으로 설명하세요.
   지역에 대한 통념(강남은 비싸다, 노원은 학원가다 등)도 쓰지 마세요.
   데이터에 없는 것은 알고 있어도 말하지 않습니다.   
   
   "조건 일치도"는 사용자가 말한 가격과 얼마나 가까운지를 0~100으로 나타낸 값입니다
   (100 = 목표가와 일치). 방향은 함께 주어지는 "목표보다 N% 높음/낮음"으로 판단해
   다음처럼 쓰세요.
   - 목표와 비슷하면: "원하시는 가격대에 가깝습니다"
   - 높으면: "원하시는 가격대보다 조금 높은 편입니다"
   - 낮으면: "원하시는 가격대보다 저렴한 편입니다"
   퍼센트 수치("23% 높음")를 그대로 옮겨 쓰지 마세요. 그건 판단 재료이지 사용자에게
   보여 줄 문구가 아닙니다.
   "비싸다/싸다"를 절대적인 평가로 쓰지 마세요. 반드시 사용자가 말한 금액을 기준으로만
   말합니다.


   "시세" 점수는 다른 지표와 방향이 반대입니다 — 값이 클수록 그 동네 시세가
   서울에서 낮은(저렴한) 편이라는 뜻입니다. "시세 85점"은 "저렴한 쪽 상위 15%"이지
   "비싸다"가 아닙니다.

   금액을 말할지 말지는 "## 사용자가 원한 가격" 절이 있는지로 판단하세요.
   - 그 절이 있으면: 주어진 금액을 준 그대로 쓰세요. 단위를 바꾸거나 다시 계산하지
     마세요 ("8억원"을 "8,000만원"으로 바꾸는 실수가 실제로 있었습니다).
   - 그 절이 없고 시세 점수만 있으면: 구체적인 금액은 쓰지 말고
     "가격대는 서울에서 저렴한 편입니다" 처럼 한 문장만 덧붙이세요.
   - 둘 다 없으면: 가격 이야기를 아예 꺼내지 마세요.

   있는 것: 7개 지표(녹지·안전·교통·상권·의료·교육·문화)의 백분위 점수,
           그리고 가격 조건이 없는 검색일 때는 시세 백분위

4. 참고 사례는 가상 인물 데이터에서 뽑은 것입니다.
   "이 동네 사람들은" 같은 일반화를 하지 마세요.
   "비슷한 성향의 사례를 보면" 정도로만 쓰고, 필요하면 표본임을 밝히세요.

5. 답변은 다음 형식으로:
   - 1위 동네를 2~3문장으로 설명 (왜 이 조건에 맞는지, 근거 점수 포함)
   - 2~5위는 한 줄씩
   - 마지막에 참고 사항이나 아쉬운 점 한 문장

존댓말로, 전체 8문장 이내로 짧게 쓰세요."""


# 지식베이스에서 사례 찾기
# load_member_vectors() 와 동일한 패턴으로 분리
def load_kb_vectors():
    """지식베이스 청크 벡터를 전부 꺼낸다. numpy 배열로 만든다."""
    rows = kb_chunks()
    vectors = np.array(
        [np.frombuffer(r["vector"], dtype="float32") for r in rows]
    )
    return rows, vectors


def find_cases(persona_query, rows, vectors, top_k=3):
    """검색 문장과 비슷한 지식베이스 청크를 찾는다.

    rows, vectors 는 get_ready() 가 미리 만들어 캐시해둔 것을 받는다.
    이 함수 안에서 다시 불러오지 않는다 — 그게 느려지는 원인이었다.
    """
    q = np.array(embed_query(to_query(persona_query)), dtype="float32")
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

# 추천 결과에 지표 수치 붙이기
def with_scores(result, names, scores):
    """TOP 5 에 각 동네의 지표 점수를 붙인다.

    08번은 (이름, 총점) 만 준다.
    "교육 98점" 같은 근거를 대려면 지표별 점수가 있어야 한다
    """
    detailed = []
    
    for name, total in result:
        i = names.index(name)
        detailed.append({
            "name": name,
            "total": round(total, 1),
            # INDICATORS 로 고정하지 않고 scores 에 실제로 있는 지표를 전부 싣는다 —
            # 가격 조건이 없는 검색에서는 pipeline_api 가 "시세"를 8번째로 넣는데,
            # 7개로 잘라내면 가중치만 남고 근거 점수가 사라져 Claude 가 지어내게 된다
            "scores": {k: round(float(v[i])) for k, v in scores.items()},
        })
    
    return detailed


# 프롬프트에 넣을 데이터 만들기
def build_context(query, weights, detailed, cases, housing=None):
    """Claude 에게 넘길 데이터를 글로 정리한다."""
    
    # 사용자가 중시한 지표 (가중치 3.5 이상)
    high = [k for k, w in weights.items() if w >= 3.5]
    
    lines = [f"## 사용자 검색어\n{query}", ""]
    lines.append(f"## 분석된 관심사\n{', '.join(high) if high else '뚜렷한 관심사 없음'}")
    lines.append(f"가중치: " + ", ".join(f"{k} {w}" for k, w in weights.items()))
    lines.append("")
    lines.append("## 추천 결과 (점수는 서울 427개 동 중 백분위)")
    
    for rank, d in enumerate(detailed, start=1):
        score_text = " / ".join(f"{k} {v}" for k, v in d["scores"].items())
        lines.append(f"{rank}위 {d['name']} (종합 {d['total']})")
        lines.append(f"     {score_text}")
    
    lines.append("")
    lines.append("## 참고 사례 (가상 인물 데이터, 서울 2,500명 표본에서 검색)")
    for c in cases:
        lines.append(f"[{c['district']} · {c['category']}] {c['text']}")

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

        # 427행 조회는 루프 밖에서 한 번만 — 예전엔 TOP 5 마다 다시 읽었다
        rows = region_densities(list(cols.values()))
        by_name = {(r["구"], r["행정동명"]): r for r in rows}

        for d in detailed:
            gu, dong = d["name"].split(" ", 1)
            row = by_name.get((gu, dong))
            if row is None:
                lines.append(f"{d['name']}: 시세 데이터 없음")
                continue

            fit = housing_fit_score(row, cols, housing["targets"])
            gap = price_gap_text(row, cols, housing["targets"])
            # 월세면 두 금액을 같이 보여준다 — 월세가 더 중요하니 앞에 쓴다
            parts = [f"{field} {format_won(row[col])}" for field, col in cols.items()]
            # 신뢰등급·거래건수·분포 — master_dataset_v3엔 없고 시세_지역별_전처리에만 있다
            note = region_price_note(gu, dong, housing["건물유형"], housing["거래유형"])
            lines.append(f"{d['name']}: {housing['건물유형']} {housing['거래유형']} " +
                         " / ".join(parts) + f" (조건 일치도 {fit}점 · {gap}){note}")

    return "\n".join(lines)


# 호출
def explain(query, weights, detailed, cases, housing=None):
    """추천 결과를 설명문으로 만든다."""
    context = build_context(query, weights, detailed, cases, housing)
    
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", context),
    ]
    return ask(messages, max_tokens=800).strip()
    

# 실행부
if __name__ == "__main__" :
    
    # 07번에서 나왔던 실제 값
    query = "애들 학원 보내기 좋은 곳"
    persona_query = "초등학생 자녀를 키우며 교육 환경과 학원 접근성을 중시하는 학부모"
    weights = {"녹지": 3.2, "안전": 3.3, "교통": 2.7, "상권": 3.2,
               "의료": 2.9, "교육": 4.6, "문화": 2.6}
    
    names, values = load_regions()
    scores = build_scores(values)
    relative = build_relative(scores)
    result = recommend(names, scores, relative, weights)
    
    detailed = with_scores(result, names, scores)
    kb_rows, kb_vectors = load_kb_vectors()
    cases = find_cases(persona_query, kb_rows, kb_vectors)
    
    print(f"⏳ 설명 생성 중...\n")
    print(explain(query, weights, detailed, cases))