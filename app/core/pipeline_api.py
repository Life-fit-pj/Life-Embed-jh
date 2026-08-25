"""
검색어 하나로 전체 파이프라인을 돌리는 통합 창구.

이 파일에는 로직이 없다. weights → recommend → explain 을
순서대로 부르기만 한다. 서버(find-home 의 core.py)는
이 파일의 search() 하나만 알면 된다.

무거운 준비물(벡터·점수)은 처음 부를 때 한 번만 만든다.
서버는 요청마다 함수를 부르므로, 매번 만들면 요청 하나에 몇 초씩 걸린다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.explain import explain, find_cases, with_scores
from pipeline.recommend import load_regions, build_scores, build_relative, recommend
from pipeline.weights import load_member_vectors, ask_claude, blend, find_similar_members

from core.db import member_weights

# ── 준비물 보관함 ──────────────────────────────
_ready = None


def get_ready():
    """벡터·점수 등 무거운 준비물. 처음 한 번만 만든다."""
    global _ready
    if _ready is None :
        print("⏳ 파이프라인 준비 중...")
        
        member_rows, member_vectors = load_member_vectors()
        names, values = load_regions()
        scores = build_scores(values)
        relative = build_relative(scores)
        
        _ready = {
            "member_rows": member_rows,
            "member_vectors": member_vectors,
            "names": names,
            "scores": scores,
            "relative": relative,
        }
        print(f"✅ 준비 완료 · 회원 청크 {len(member_rows)}개 · 행정동 {len(names)}개")
    return _ready


def recommend_by_weights(weights, top_k=5):
    """가중치 → TOP 5. 슬라이더로 바로 올 때 쓴다 (검색어 없음)."""
    r = get_ready()
    result = recommend(r["names"], r["scores"], r["relative"], weights, top_k=top_k)
    return with_scores(result, r["names"], r["scores"])


def search(query, top_k=5):
    """검색어 → 가중치 + TOP 5 + 설명문. 서버가 부르는 메인 창구."""
    r = get_ready()
    
    # 1) 검색어 → 가중치
    draft, persona_query = ask_claude(query)
    similar = find_similar_members(persona_query, r["member_rows"], r["member_vectors"])
    ids = [cid for cid, _ in similar]
    weights = blend(draft, member_weights(ids))
    
    # 2) 가중치 → TOP 5
    detailed = recommend_by_weights(weights, top_k=top_k)

    # 3) 설명문
    cases = find_cases(persona_query)
    text = explain(query, weights, detailed, cases)
    
    return{
        "query": query,
        "persona_query": persona_query,
        "weights": weights,
        "regions": detailed,
        "explanation": text,
    }

if __name__ == "__main__" :
    import json
    
    result = search("얘들 학원 보내기 좋은 곳")
    
    print()
    print(f"가중치: {result['weights']}")
    print()
    for i, region in enumerate(result["regions"], start=1):
        print(f"{i}위 {region['name']} ({region['total']}점)")
    print()
    print(result["explanation"])
