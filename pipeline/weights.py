"""
할 일 : 검색어를 가중치 7개로 바꾼다

[B] Claude 가 검색어를 읽고 초안을 만든다
[A] 비슷한 회원을 찾아 그들의 실제 가중치로 보정한다
"""

import json
import numpy as np

from core.config import INDICATORS
from core.db import member_chunks, member_weights
from core.llm import get_llm, get_embedder, to_query


SYSTEM_PROMPT = """당신은 주거지 추천 서비스의 분석 도구입니다.
사용자의 검색어를 읽고 두 가지를 만드세요.

(1) 7개 지표의 중요도 (1~5점)
(2) 그런 조건을 원하는 사람이 어떤 사람인지 묘사하는 한 문장

지표 설명:
- 녹지: 공원, 산책로, 자연환경
- 안전: 치안, CCTV, 경찰서
- 교통: 지하철, 버스 접근성
- 상권: 마트, 식당, 카페, 시장
- 의료: 병원, 의원, 약국
- 교육: 학교, 학원
- 문화: 도서관, 공연장, 전시관

규칙:
1. 핵심 요구를 파악해서 그 지표에만 5점을 주세요.
   검색어에서 부수적으로 딸려오는 것(학원→안전 같은 연상)은 3점을 넘기지 마세요.
   사용자가 직접 말하지 않은 지표는 전부 3점입니다.
   좋은 예) "애들 학원 보내기 좋은 곳" -> 교육 5, 나머지 전부 3
   나쁜 예) 교육 5, 안전 4, 교통 4  (안전·교통은 사용자가 말한 적 없음)
2. 부정 표현을 주의하세요. "번화가는 싫어요" 는 상권을 낮게(1~2) 주어야 합니다.
3. persona_query 는 장소가 아니라 **사람**을 묘사해야 합니다.
   지역·동네·"좋은 곳" 같은 장소 표현을 쓰지 마세요.
   예) "애들 학원 보내기 좋은 곳"
       -> "초등학생 자녀를 키우며 교육에 관심이 많은 사람"
   예) "번화가는 싫어요"
       -> "조용한 주택가에서 한적하게 지내는 것을 좋아하는 사람"
4. 반드시 아래 JSON 형식으로만 답하세요. 설명이나 인사말을 붙이지 마세요.

{"녹지": 3, "안전": 3, "교통": 3, "상권": 3, "의료": 3, "교육": 3, "문화": 3,
 "persona_query": "..."}"""

# Claude 초안과 회원 평균을 몇 대 몇으로 섞을지.
# 0.7 이면 Claude 70%, 회원 30%
CLAUDE_RATIO = 0.7


# 함수들
def load_member_vectors():
    """회원 청크 벡터를 전부 꺼낸다. numpy 배열로 만든다."""
    rows = member_chunks()
    vectors = np.array([json.loads(r["vector"]) for r in rows], dtype="float32")
    return rows, vectors


def find_similar_members(query, rows, vectors, top_k=5) :
    """검색어와 비슷한 회원을 찾는다.

    청크 단위로 검색하면 한 사람이 여러 번 걸릴 수 있다.
    그래서 사람별 최고 점수만 남기고 상위 top_k 명을 고른다.
    """
    q = np.array(get_embedder().embed_query(to_query(query)), dtype="float32")
    scores = vectors @ q
    
    best = {}
    for row, score in zip(rows, scores):
        cid = row["customer_id"]
        if cid not in best or score > best[cid][0]:
            best[cid] = (float(score), row["category"], row["text"])
    
    ranked = sorted(best.items(), key=lambda x: x[1][0], reverse=True)
    return ranked[:top_k]


def ask_claude(query):
    """Claude 에게 가중치 초안과 검색용 문장을 받는다.

    돌려주는 것: (가중치 딕셔너리, 검색용 문장)

    검색용 문장이 왜 필요한가 —
    사용자 검색어는 "좋은 곳" 처럼 장소를 찾는 문장이다.
    그런데 member_chunk 에 담긴 건 사람을 묘사한 문장이다.
    성격이 다른 두 문장을 벡터로 비교하면 엉뚱한 게 걸린다.
    (실제로 "애들 학원 보내기 좋은 곳" 으로 검색하니
     교육 1점짜리 회원들이 뽑혔다. z = -0.94)
    그래서 검색 전에 사람 묘사로 바꿔서 성격을 맞춘다.
    """
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", query),
    ]        
    text = get_llm(max_tokens=300).invoke(messages).content.strip()
    
        # 혹시 ```json 같은 게 붙어 나오면 떼어낸다
    text = text.replace("```json", "").replace("```","").strip()
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"[경고] JSON 파싱 실패: {text[:80]}")
        return {k: 3 for k in INDICATORS}, query       # 실패하면 전부 보통값
    
    # 7개가 다 있는지, 1~5 범위인지 검사한다
    weights = {}
    for key in INDICATORS:
        value = data.get(key, 3)
        weights[key] = max(1, min(5, int(value)))
    
    # 문장이 없거나 비었으면 원래 검색어로 대체한다
    persona_query = (data.get("persona_query") or "").strip() or query
    
    return weights, persona_query


# 합치기
# Claude 초안과 회원 평균을 몇 대 몇으로 섞을지: 위에 적어둠

def blend(draft, members):
    """Claude 초안을 회원들의 실제 가중치로 보정한다."""
    if not members:
        return draft        # 비슷한 회원이 없으면 초안 그대로
    
    final = {}
    for key in INDICATORS:
        # 비슷한 회원들의 평균
        values = [m[key] for m in members]
        member_avg = sum(values) / len(values)
        
        mixed = draft[key] * CLAUDE_RATIO + member_avg * (1 - CLAUDE_RATIO)
        final[key] = round(mixed, 1)
    
    return final


if __name__ == "__main__":
    rows, vectors = load_member_vectors()
    print(f"✅ 회원 청크 {len(rows)}개")

    for q in ["애들 학원 보내기 좋은 곳",
              "병원이 가깝고 할머니를 모시고 살기 좋은 곳",
              "멀지 않은 거리에 백화점이 있는 곳"]:
        print(f"검색어: {q}")

        draft, persona_query = ask_claude(q)
        print(f"   [B] Claude 초안 : {draft}")
        print(f"   [→] 검색용 문장 : {persona_query}")
        
        # 원래 검색어가 아니라 번역된 문장으로 검색한다
        similar = find_similar_members(persona_query, rows, vectors)
        ids = [cid for cid, _ in similar]
        members = member_weights(ids)
        print(f"   [A] 유사 회원   : {ids}")

        final = blend(draft, members)
        print(f"   [최종] {final}")
        print()





