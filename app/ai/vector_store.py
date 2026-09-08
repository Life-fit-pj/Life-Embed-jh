# Last updated: 2026-09-08
"""벡터를 담고, 꺼내고, 견주는 곳. chunks 의 embedding 칸을 다루는 유일한 파일이다.

SQLite 와 pgvector 의 차이를 여기 가둔다 — 지금은 JSON 글자로 담지만
나중에 Column(Vector(1536)) 으로 바꿔도 고칠 파일이 하나로 끝난다.

캐시를 여기 두는 이유 —
9,900개를 JSON 에서 숫자로 되돌리는 데 시간이 걸린다. 요청마다 하면 매번 기다린다.
처음 한 번만 올려 두고, 청크가 바뀌면 invalidate() 로 버린다(이론 10).

수업의 app/ai/vector_store.py 와 같은 자리다. 다른 점은 두 가지 —
  ① 우리는 source("member"/"kb") 로 갈래가 나뉜다
  ② 세션을 받지 않는다. app/tables/chunks.py 다리가 열고 닫아 준다(3-A)
"""

import json

import numpy as np

from app.repositories.chunks import kb_chunks, member_chunks

# source -> (행 목록, 벡터 배열). 처음 부를 때 채워진다
_cache = {}

_LOADERS = {"member": member_chunks, "kb": kb_chunks}

# repository 가 옛 이름으로 돌려주기 때문이다(5-7절).
# 8단계에서 반환 키를 source_id 로 통일하면 이 표는 사라진다
_ID_KEY = {"member": "customer_id", "kb": "uuid"}


def to_text(vector):
    """벡터를 DB 에 담을 글자로. pgvector 로 가면 이 함수만 바뀐다."""
    return json.dumps(vector)


def from_text(text):
    """DB 에서 꺼낸 글자를 숫자 목록으로."""
    return json.loads(text)


def load(source):
    """그 갈래의 (행 목록, 벡터 배열). 처음 한 번만 DB 를 읽는다."""
    if source not in _cache:
        rows = _LOADERS[source]()
        vectors = np.array([from_text(r["embedding"]) for r in rows], dtype="float32")
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
