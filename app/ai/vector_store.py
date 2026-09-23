# Last updated: 2026-09-08
"""벡터를 견주는 창구. 비교 자체는 DB(pgvector 의 <=>)가 한다.

2026-09-23 전에는 여기서 9,900개 벡터를 메모리에 올려 numpy 내적으로 비교했다.
그 "올리기"가 한 번에 60~200MB 라 Supabase 무료 egress(월 5GB)를 넘겼고,
쿼리가 2분 제한에 걸려 검색이 아예 안 됐다(2026-09-22 실측: 9,000줄에 4분).
지금은 질문 벡터 하나를 보내고 가까운 몇 줄만 받는다. 캐시도, 무효화도 없다.

실제 쿼리는 app/repositories/chunk_repository.py 의 nearest_* 에 있다.
이 파일이 남아 있는 이유 — 벡터를 다루는 방식이 또 바뀌어도 부르는 쪽
(app/rag/retriever.py)은 이 두 함수 이름만 알면 되게 하려고.
"""

from app.repositories.chunks import nearest_chunks, nearest_people


def search(source, query_vector, top_k=5):
    """질문 벡터와 가까운 청크 top_k. [(행, 점수)]"""
    return nearest_chunks(source,query_vector, top_k)


def search_people(source, query_vector, top_k=5):
    """사람 단위로 top_k. [(id, 점수, 행)]"""
    return nearest_people(source,query_vector, top_k)
