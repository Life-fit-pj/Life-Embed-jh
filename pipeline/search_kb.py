"""
할 일 : 저장한 벡터로 검색
"""

import json
import time

import numpy as np

from core.llm import get_embedder, to_query
from core.db import kb_chunks


#벡터 불러오기
def load_vectors():
    """DB 에 저장한 벡터를 전부 꺼내 numpy 배열로 만든다."""
    rows = kb_chunks()
    
    # json.loads 로 글자를 다시 숫자 목록으로 되돌린다
    vectors = np.array([json.loads(r["vector"]) for r in rows], dtype = "float32")
    
    return rows, vectors


# 검색
def search(query, rows, vectors, top_k=5):
    """검색어와 비슷한 청크 top_k 개를 찾는다."""

    # e5 규칙: 질문에는 query: 를 붙인다 (저장할 때는 passage: 였다)
    q = np.array(get_embedder().embed_query(to_query(query)), dtype="float32")
    
    # 저장할 때 길이를 1로 맞춰뒀으므로, 곱하기만으로 유사도가 나온다
    scores = vectors @ q
    
    # argsort 는 작은 것부터의 순서를 준다. [::-1] 로 뒤집어 큰 것부터로
    top = scores.argsort()[::-1][:top_k]
    
    return [(rows[i], float(scores[i])) for i in top]


# 실행

if __name__ == "__main__" :
    print("⏳ 벡터 불러오는 중...")
    rows, vectors = load_vectors()
    print(f"✅ 청크 {len(rows):,}개 · 벡터 {vectors.shape}")
    
    while True:
        query = input("검색어> ").strip()
        if not query:
            break
        
        started = time.time()
        found = search(query, rows, vectors)
        elapsed = time.time() - started
        
        print(f"   ({elapsed:.2f}초)")
        for row, score in found:
            gu = row["district"].replace("서울-", "")
            print(f"   💬 {score:.3f} [{gu} · {row['category']}] {row['text'][:60]}...")
        print()


