"""벡터 검색이 DB(pgvector)에서 제대로 도나.

실행: py -m pytest tests/test_vector_search.py -v
청크 하나의 벡터를 그대로 질문으로 쓰면 자기 자신이 1등(점수 ≈ 1)으로 나와야 한다.
OpenAI 는 안 부른다.
"""

from app.ai import vector_store
from app.db import SessionLocal
from app.models.chunk import Chunk


def _one(source):
    with SessionLocal() as db:
        return db.query(Chunk.chunk_id, Chunk.source_id, Chunk.embedding).filter(
            Chunk.source == source, Chunk.embedding.isnot(None)
        ).first()


def test_자기_벡터로_찾으면_자기가_1등():
    chunk_id, _, vector = _one("kb")
    results = vector_store.search("kb", vector, top_k=3)

    assert results[0][0]["chunk_id"] == chunk_id
    assert abs(results[0][1] - 1) < 1e-3
    assert [s for _, s in results] == sorted((s for _, s in results), reverse=True)


def test_사람_단위는_한_사람이_한_번만():
    _, customer_id, vector = _one("member")
    people = vector_store.search_people("member", vector, top_k=5)

    ids = [key for key, _, _ in people]
    assert ids[0] == customer_id
    assert len(ids) == len(set(ids)) == 5
