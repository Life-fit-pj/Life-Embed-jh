"""
검색어 하나로 전체 파이프라인을 돌리는 통합 창구.

이 파일에는 로직이 없다. weights → recommend → explain 을
순서대로 부르기만 한다. 서버(find-home 의 core.py)는
이 파일의 search() 하나만 알면 된다.

무거운 준비물(벡터·점수)은 처음 부를 때 한 번만 만든다.
서버는 요청마다 함수를 부르므로, 매번 만들면 요청 하나에 몇 초씩 걸린다.
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.explain import explain, find_cases, load_kb_vectors, with_scores
from pipeline.recommend import load_regions, build_scores, build_relative, recommend
from pipeline.weights import load_member_vectors, ask_claude, blend, find_similar_members
from pipeline.housing import matching_regions

from app.core.db import member_weights
from app.core.llm import get_embedder

# ── 준비물 보관함 ──────────────────────────────
_ready = None


def get_ready():
    """벡터·점수 등 무거운 준비물. 처음 한 번만 만든다."""
    global _ready
    if _ready is None :
        print("⏳ 파이프라인 준비 중...")
        
        get_embedder()   # [E] 임베딩 모델도 여기서 한 번 올려둔다 — 첫 검색자만 로딩 비용을 떠안지 않도록
                
        member_rows, member_vectors = load_member_vectors()
        kb_rows, kb_vectors = load_kb_vectors()          # [A] 지식베이스 벡터도 여기서 한 번만
        names, values = load_regions()
        scores = build_scores(values)
        relative = build_relative(scores)
        
        _ready = {
            "member_rows": member_rows,
            "member_vectors": member_vectors,
            "kb_rows": kb_rows,
            "kb_vectors": kb_vectors,
            "names": names,
            "scores": scores,
            "relative": relative,
        }
        print(f"✅ 준비 완료 · 회원 청크 {len(member_rows)}개 · "
              f"지식베이스 청크 {len(kb_rows)}개 · 행정동 {len(names)}개")
    return _ready


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


def search(query, top_k=5):
    """검색어 → 가중치 + TOP 5 + 설명문. 서버가 부르는 메인 창구."""
    r = get_ready()

    # 1) 검색어 → 가중치
    draft, persona_query = ask_claude(query)
    similar = find_similar_members(persona_query, r["member_rows"], r["member_vectors"])
    ids = [cid for cid, _ in similar]
    weights = blend(draft, member_weights(ids))

    # 1-1) 검색어 → 가격 조건. 건물유형·거래유형·예산 셋 다 있어야 필터를 켠다
    housing = None
    if draft.get("건물유형") and draft.get("거래유형") and draft.get("예산"):
        targets = {"예산": draft["예산"]}
        if draft["거래유형"] == "월세" and draft.get("보증금"):
            targets["보증금"] = draft["보증금"]
        housing = {"건물유형": draft["건물유형"], "거래유형": draft["거래유형"], "targets": targets}

    # 2) 가중치 → TOP 5 (가격 조건이 있으면 그 조건에 맞는 동으로 먼저 추린다)
    detailed = recommend_by_weights(weights, top_k=top_k, housing=housing)

    # 3) 설명문
    cases = find_cases(persona_query, r["kb_rows"], r["kb_vectors"])   # 캐시된 걸 넘겨준다
    text = explain(query, weights, detailed, cases, housing=housing)

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
