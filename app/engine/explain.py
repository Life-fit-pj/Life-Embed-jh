# Last updated: 2026-09-08
"""
할 일 : TOP 5 추천 결과를 사용자에게 보여줄 설명문으로 만든다

07번이 가중치를, 08번이 TOP 5 를 만들었다.
여기서는 그 결과에 근거 수치와 유사 사례를 붙여 Claude 에게 넘기고,
사람이 읽을 설명을 받는다.

Claude 가 숫자를 지어내지 못하도록 프롬프트에서 강하게 제한한다.
"""

from app.engine.housing import DEAL_COLUMNS, price_fit_line, price_head_lines, price_notes
from app.engine.recommend import (load_regions, build_column_scores, build_scores, build_relative, recommend,
                                  focus_label)
from app.repositories.regions import region_densities
from app.ai.llm import ask
from app.rag.retriever import retrieve
from app.core.config import SIMILARITY_FLOOR
from app.prompts.search import EXPLAIN_PROMPT


def find_cases(persona_query, top_k=3):
    """검색 문장과 비슷한 지식베이스 사례를 찾는다.

    벡터를 들고 있는 것은 app/ai/vector_store.py 다.
    여기서는 화면에 실을 모양으로 가공만 한다 — "서울-" 떼기와 200자 자르기
    """
    return [
        {
            "district": row["district"].replace("서울-", ""),
            "category": row["category"],
            "text": row["text"][:200],
            "score": score,
        }
        for row, score in retrieve("kb", persona_query, top_k)
        if score >= SIMILARITY_FLOOR   # 억지로 3건을 채우지 않는다. 없으면 없다고 설명문에 알린다(아래 build_context)
    ]


# 추천 결과에 지표 수치 붙이기
def with_scores(result, names, scores, counts=None):
    """TOP 5 에 각 동네의 지표 점수와 원본 개수를 붙인다.

    scores 는 백분위(0~100)라 "이 동네가 몇 등인가" 는 알려주지만
    "공원이 몇 개인가" 는 못 알려준다. 화면이 근거로 보여줄 실제 개수가 counts 다.

    counts 를 안 주면 그 칸은 빈 딕셔너리다 — 부르는 쪽을 한꺼번에 안 고쳐도 되게
    """
    counts = counts or {}
    detailed = []

    for name, total in result:
        i = names.index(name)
        detailed.append({
            "name": name,
            "total": round(total, 1),
            # INDICATORS 로 고정하지 않고 scores 에 실제로 있는 지표를 전부 싣는다 —
            # 가격 조건이 없는 검색에서는 "시세"가 8번째로 들어오는데,
            # 7개로 잘라내면 가중치만 남고 근거 점수가 사라져 Claude 가 지어내게 된다
            "scores": {k: round(float(v[i])) for k, v in scores.items()},
            "counts": counts.get(name, {}),
        })

    return detailed


# 프롬프트에 넣을 데이터 만들기
def build_context(query, weights, detailed, cases, housing=None, focus=None):
    """Claude 에게 넘길 데이터를 글로 정리한다."""
    
    # 사용자가 중시한 지표 (가중치 3.5 이상)
    high = [k for k, w in weights.items() if w >= 3.5]
    
    lines = [f"## 사용자 검색어\n{query}", ""]
    lines.append(f"## 분석된 관심사\n{', '.join(high) if high else '뚜렷한 관심사 없음'}")
    lines.append(f"가중치: " + ", ".join(f"{k} {w}" for k, w in weights.items()))
    lines.append("")
    lines.append("## 추천 결과 (점수는 서울 427개 동 중 백분위)")
    # 세부가 걸린 검색은 순위를 그 한 가지로만 보고 매겼다. 지표 점수(전체)와 세부 점수가 둘 다 실려 있으므로
    # 무엇이 무엇인지 적어 준다 — 안 적으면 "교통 60" 인 동네가 왜 1위인지 설명하지 못한다
    for indicator, sub in (focus or {}).items():
        lines.append(f"※ 이번 순위는 {indicator} 지표를 '{sub}' 한 가지로만 보고 매겼다. "
                     f"그 점수 = '{focus_label(indicator, sub)}' / 지표 전체의 점수 = '{indicator}'")

    for rank, d in enumerate(detailed, start=1):
        score_text = " / ".join(f"{k} {v}" for k, v in d["scores"].items())
        lines.append(f"{rank}위 {d['name']} (종합 {d['total']})")
        lines.append(f"     {score_text}")
    
    lines.append("")
    lines.append("## 참고 사례 (가상 인물 데이터, 서울 2,500명 표본에서 검색)")
    for c in cases:
        lines.append(f"[{c['district']} · {c['category']}] {c['text']}")
    if not cases:
        lines.append("(비슷한 사례 없음 - 사례를 지어내지 말고 위 지표 점수만으로 설명한다)")

    if housing:
        cols = DEAL_COLUMNS.get((housing["건물유형"], housing["거래유형"]))
        lines.extend(price_head_lines(housing))

        # 427행 조회는 루프 밖에서 한 번만 — 예전엔 TOP 5 마다 다시 읽었다.
        # 모르는 (건물유형, 거래유형) 조합이면 cols 가 None — 빈 목록으로 두어 아래가 전부 "시세 데이터 없음"이 되게(region_service 와 같은 처리)
        rows = region_densities(list(cols.values())) if cols else []
        by_name = {(r["구"], r["행정동명"]): r for r in rows}
        # 신뢰등급·거래건수·분포도 한 번에 읽는다 — master_dataset_v3엔 없고 시세_지역별_전처리에만 있다
        notes = price_notes([d["name"] for d in detailed], housing["건물유형"], housing["거래유형"]) if cols else {}

        for d in detailed:
            gu, dong = d["name"].split(" ", 1)
            row = by_name.get((gu, dong))
            if row is None:
                lines.append(f"{d['name']}: 시세 데이터 없음")
                continue

            lines.append(f"{d['name']}: " + price_fit_line(row, cols, housing, notes[d["name"]]))

    return "\n".join(lines)


# 호출
def explain(query, weights, detailed, cases, housing=None, focus=None):
    """추천 결과를 설명문으로 만든다. focus 는 검색어에서 뽑힌 세부({"교통": "버스"}) — 재료에 그 뜻을 한 줄 적는다"""
    context = build_context(query, weights, detailed, cases, housing, focus)
    
    messages = [
        ("system", EXPLAIN_PROMPT),
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
    
    names, values, _ = load_regions()
    scores = build_scores(build_column_scores(values))
    relative = build_relative(scores)
    result = recommend(names, scores, relative, weights)
    
    detailed = with_scores(result, names, scores)
    cases = find_cases(persona_query)
    
    print(f"⏳ 설명 생성 중...\n")
    print(explain(query, weights, detailed, cases))