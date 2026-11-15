"""chunk_repository.py 를 세션 없이 부르는 창구.

chunk_repository 의 함수는 db 세션을 첫 인자로 받는다. 서비스·엔진 층은 세션을 몰라도
되도록, 여기서 _run() 이 세션을 열고 닫아 준다.
"""

from app.db import SessionLocal
from app.repositories import chunk_repository as repo


def _run(fn, *args):
    """세션을 열고 fn(db, *args) 를 부른 뒤 반드시 닫는다."""
    db = SessionLocal()
    try:
        return fn(db, *args)
    finally:
        db.close()


def member_chunks():
    return _run(repo.member_chunks)


def kb_chunks():
    return _run(repo.kb_chunks)


# ── 벡터 검색 (app/ai/vector_store.py 가 쓴다) ────────

def nearest_chunks(source, query_vector, top_k=5):
    return _run(repo.nearest_chunks,source, query_vector, top_k)

def nearest_people(source, query_vector, top_k=5):
    return _run(repo.nearest_people,source, query_vector, top_k)


# ── 집계 (관리자 대시보드가 쓴다) ──────────────────────

def member_chunk_stats():
    return _run(repo.member_chunk_stats)


def persona_lengths():
    return _run(repo.persona_lengths)


# ── 재임베딩 쓰기 (app/engine/resync.py 가 쓴다) ────────

def replace_member_chunks(customer_id, rows, categories=None):
    return _run(repo.replace_member_chunks, customer_id, rows, categories)
