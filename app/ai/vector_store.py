# Last updated: 2026-09-08
"""벡터를 담고, 꺼내고, 견주는 곳. chunks 의 embedding 칸을 다루는 유일한 파일이다.

벡터 형식의 차이를 여기 가둔다 — 지금은 pgvector 의 Column(Vector(1536)) 이라
드라이버가 숫자 배열을 그대로 건네준다. 형식이 또 바뀌어도 고칠 파일은 여기 하나다.

캐시를 여기 두는 이유 —
9,900개를 DB 에서 받아 배열로 쌓는 데 시간이 걸린다. 요청마다 하면 매번 기다린다.
처음 한 번만 올려 두고, 청크가 바뀌면 invalidate() 로 버린다(이론 10).

★ 검색은 여전히 여기서 한다 — Vector 칸으로 바꾼 것은 "담는 방식"뿐이고,
  DB 의 <=> 연산자로 옮기지 않았다. 9,900개는 메모리 내적이 왕복보다 빠르다.

수업의 app/ai/vector_store.py 와 같은 자리다. 다른 점은 두 가지 —
  ① 우리는 source("member"/"kb") 로 갈래가 나뉜다
  ② 세션을 받지 않는다. app/repositories/chunks.py 다리가 열고 닫아 준다(3-A)
"""

import numpy as np

from app.core.config import EMBED_DIMENSION
from app.repositories.chunks import kb_chunks, member_chunks

# source -> (행 목록, 벡터 배열). 처음 부를 때 채워진다
_cache = {}

_LOADERS = {"member": member_chunks, "kb": kb_chunks}

# repository 가 옛 이름으로 돌려주기 때문이다(5-7절).
# 8단계에서 반환 키를 source_id 로 통일하면 이 표는 사라진다
_ID_KEY = {"member": "customer_id", "kb": "uuid"}


def load(source):
    """그 갈래의 (행 목록, 벡터 배열). 처음 한 번만 DB 를 읽는다."""
    if source not in _cache:
        rows = _LOADERS[source]()
        vectors = np.array([r["embedding"] for r in rows], dtype="float32")
        for r in rows:
            r["embedding"] = None   # 배열에 이미 옮겨 실었다 — 원본 float 리스트를 계속 들고 있으면 메모리가 두 배로 든다
        _cache[source] = (rows, vectors)

    return _cache[source]


def invalidate(source=None):
    """캐시를 버린다. 청크를 고쳤으면 반드시 부른다(7-8절).

    source 를 안 주면 전부 버린다
    """
    if source is None:
        _cache.clear()
    else:
        _cache.pop(source, None)


def search(source, query_vector, top_k=5):
    """질문 벡터와 가까운 청크 top_k. [(행, 점수)] 를 돌려준다.

    저장할 때 길이를 1 로 맞춰 뒀으므로 곱하기만으로 코사인 유사도가 나온다
    """
    rows, vectors = load(source)
    scores = vectors @ np.asarray(query_vector, dtype="float32")

    top = scores.argsort()[::-1][:top_k]
    return [(rows[i], float(scores[i])) for i in top]


def search_people(source, query_vector, top_k=5):
    """사람 단위로 top_k. [(id, 점수, 행)] 를 돌려준다.

    한 사람의 청크가 여럿 걸려도 최고 점수 하나만 센다 —
    청크 단위로 뽑으면 말 많은 한 사람이 자리를 다 차지한다
    """
    rows, vectors = load(source)
    scores = vectors @ np.asarray(query_vector, dtype="float32")
    key_name = _ID_KEY[source]

    best = {}
    for row, score in zip(rows, scores):
        key = row[key_name]
        if key not in best or score > best[key][0]:
            best[key] = (float(score), row)

    ranked = sorted(best.items(), key=lambda item: item[1][0], reverse=True)
    return [(key, score, row) for key, (score, row) in ranked[:top_k]]
