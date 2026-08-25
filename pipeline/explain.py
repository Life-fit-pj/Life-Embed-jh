"""
할 일 : TOP 5 추천 결과를 사용자에게 보여줄 설명문으로 만든다

07번이 가중치를, 08번이 TOP 5 를 만들었다.
여기서는 그 결과에 근거 수치와 유사 사례를 붙여 Claude 에게 넘기고,
사람이 읽을 설명을 받는다.

Claude 가 숫자를 지어내지 못하도록 프롬프트에서 강하게 제한한다.
"""

import json
import numpy as np

from core.config import INDICATORS
from core.db import kb_chunks
from core.llm import get_llm, get_embedder, to_query


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
   없는 것: 집값, 전월세, 교육비, 물가, 생활비, 통학 시간, 지하철 노선명, 학교 이름, 구체적인 시설 이름, 유동인구, 소음 수치
   
   지역에 대한 통념(강남은 비싸다, 노원은 학원가다 등)도 쓰지 마세요.
   데이터에 없는 것은 알고 있어도 말하지 않습니다.
   
   있는 것: 7개 지표(녹지·안전·교통·상권·의료·교육·문화)의 백분위 점수

4. 참고 사례는 가상 인물 데이터에서 뽑은 것입니다.
   "이 동네 사람들은" 같은 일반화를 하지 마세요.
   "비슷한 성향의 사례를 보면" 정도로만 쓰고, 필요하면 표본임을 밝히세요.

5. 답변은 다음 형식으로:
   - 1위 동네를 2~3문장으로 설명 (왜 이 조건에 맞는지, 근거 점수 포함)
   - 2~5위는 한 줄씩
   - 마지막에 참고 사항이나 아쉬운 점 한 문장

존댓말로, 전체 8문장 이내로 짧게 쓰세요."""



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
            "scores": {k: round(float(scores[k][i])) for k in INDICATORS},
        })
    
    return detailed


# 지식베이스에서 사례찾기
def find_cases(persona_query, top_k=3):
    """검색 문장과 비슷한 지식베이스 청크를 찾는다.

    회원 100명이 아니라 지식베이스 2,500명에서 찾는다.
    가중치를 얻으려는 게 아니라, 답변에 쓸 사례를 얻으려는 것이다
    """
    rows = kb_chunks()
    vectors = np.array([json.loads(r["vector"]) for r in rows], dtype="float32")
    
    q = np.array(get_embedder().embed_query(to_query(persona_query)), dtype="float32")
    scores = vectors @ q
    
    top = scores.argsort()[::-1][:top_k]
    
    return [
        {
            "district": rows[i]["district"].replace("서울-",""),
            "category": rows[i]["category"],
            "text": rows[i]["text"][:200],
            "score": float(scores[i]),
        }
        for i in top
    ]


# 프롬프트에 넣을 데이터 만들기
def build_context(query, weights, detailed, cases):
    """Claude 에게 넘길 데이터를 글로 정리한다."""
    
    # 사용자가 중시한 지표 (가중치 3.5 이상)
    high = [k for k, w in weights.items() if w >= 3.5]
    
    lines = [f"## 사용자 검색어\n{query}", ""]
    lines.append(f"## 분석된 관심사\n{", ".join(high) if high else '뚜렷한 관심사 없음'}")
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

    return "\n".join(lines)


# 호출
def explain(query,weights,detailed,cases):
    """추천 결과를 설명문으로 만든다."""
    context = build_context(query, weights, detailed, cases)
    
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", context),
    ]
    return get_llm(max_tokens=800).invoke(messages).content.strip()
    

# 실행부
if __name__ == "__main__" :
    
    # 07번에서 나왔던 실제 값
    query = "애들 학원 보내기 좋은 곳"
    persona_query = "초등학생 자녀를 키우며 교육 환경과 학원 접근성을 중시하는 학부모"
    weights = {"녹지": 3.2, "안전": 3.3, "교통": 2.7, "상권": 3.2,
               "의료": 2.9, "교육": 4.6, "문화": 2.6}
    
    from pipeline.recommend import load_regions, build_scores, build_relative, recommend

    names, values = load_regions()
    scores = build_scores(values)
    relative = build_relative(scores)
    result = recommend(names, scores, relative, weights)
    
    detailed = with_scores(result, names, scores)
    cases = find_cases(persona_query)
    
    print(f"⏳ 설명 생성 중...\n")
    print(explain(query, weights, detailed, cases))