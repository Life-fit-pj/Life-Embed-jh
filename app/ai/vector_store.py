# Last updated: 2026-09-27
"""질문 벡터와 가까운 청크를 찾는 곳. 부르는 쪽(app/rag/retriever.py)의 창구다.

견주기는 DB(pgvector)가 한다 — 예전에는 9,900개를 처음 한 번 메모리에 올려
내적했는데, 서버를 켤 때마다·회원이 바뀔 때마다 임베딩 전부가 다시 실려 와
Supabase egress 5GB 를 넘겼다. 이제 요청마다 top_k 줄만 온다.
그래서 캐시도, 청크가 바뀌면 캐시를 버리던 invalidate() 도 없다.

수업의 app/ai/vector_store.py 와 같은 자리다. 다른 점은 두 가지 —
  ① 우리는 source("member"/"kb") 로 갈래가 나뉜다
  ② 세션을 받지 않는다. app/repositories/chunks.py 다리가 열고 닫아 준다(3-A)
"""

from app.repositories.chunks import nearest_chunks, nearest_people

# repository 가 옛 이름으로 돌려주기 때문이다(5-7절).
# 8단계에서 반환 키를 source_id 로 통일하면 이 표는 사라진다
_ID_KEY = {"member": "customer_id", "kb": "uuid"}


def search(source, query_vector, top_k=5):
    """질문 벡터와 가까운 청크 top_k. [(행, 점수)] 를 돌려준다.

    저장할 때 길이를 1 로 맞춰 뒀으므로 내적이 곧 코사인 유사도다
    """
    return nearest_chunks(source, list(query_vector), top_k)


def search_people(source, query_vector, top_k=5):
    """사람 단위로 top_k. [(id, 점수, 행)] 를 돌려준다.

    한 사람의 청크가 여럿 걸려도 최고 점수 하나만 센다 —
    청크 단위로 뽑으면 말 많은 한 사람이 자리를 다 차지한다
    """
    key_name = _ID_KEY[source]
    return [
        (row[key_name], score, row)
        for row, score in nearest_people(source, list(query_vector), top_k)
    ]
