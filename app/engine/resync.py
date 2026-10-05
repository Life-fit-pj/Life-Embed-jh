# Last updated: 2026-09-08
"""회원 한 명의 벡터만 다시 만든다.

관리자가 방금 이 사람 정보를 고쳤다는 게 확실한 상태에서 불리는 함수라서,
"뭐가 바뀌었나" 확인하는 절차 없이 그냥 그 사람 청크를 지우고 새로 만든다.
"""

from app.ai.embedder import embed_documents
from app.repositories.chunks import replace_member_chunks
from app.ai.chunker import make_chunks, MEMBER_KEYS


def _embed(chunks):
    return embed_documents([c["text"] for c in chunks])


def resync_member(customer_id, row, categories=None):
    """회원 한 명을 다시 임베딩한다.

    row 는 nemotron.csv 한 줄 + customer_id 가 들어간 모양이어야 한다.
    categories 를 주면 그 칸만 다시 만든다 — row 에는 그 칸들만 있으면 된다. 관리자가 한 칸을 고쳤을 때
    나머지 칸까지 지우고 다시 임베딩하지 않는다. 안 주면 회원의 청크를 통째로 다시 만든다
    """
    chunks = make_chunks([row], MEMBER_KEYS)
    vectors = _embed(chunks) if chunks else []      # 칸을 비우기만 했으면 임베딩할 글이 없다 — 빈 목록은 OpenAI 가 400 으로 거절한다

    replace_member_chunks(customer_id, [
        (c["customer_id"], c["category"], c["text"], vec)
        for c, vec in zip(chunks, vectors)
    ], categories)
