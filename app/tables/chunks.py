"""옛 이름을 지키는 다리. 실제 내용은 app/repositories/chunk_repository.py 에 있다.

부르는 쪽이 이 이름으로 import 하고 있어서 아직 못 지운다 —
  app/ai/vector_store.py        member_chunks · kb_chunks (캐시에 올릴 때 한 번)
  app/engine/resync.py          replace_kb_chunks · replace_member_chunks
  app/services/admin_service.py member_chunk_count · persona_lengths
  tests/make_golden.py          네 함수 모두 (골든 사진)

8단계에서 부르는 쪽을 repositories 로 바꾸면서 이 파일을 지운다.
"""

from app.db import SessionLocal
from app.repositories import chunk_repository as repo


def _run(fn, *args):
    """세션을 열고 fn(db, *args) 를 부른 뒤 반드시 닫는다.

    옛 함수들은 db 를 인자로 안 받았다. 그 모양을 지켜야 부르는 쪽을
    안 고칠 수 있으므로, 세션을 여기서 열고 닫는다.
    """
    db = SessionLocal()
    try:
        return fn(db, *args)
    finally:
        db.close()


def member_chunks():
    return _run(repo.member_chunks)


def kb_chunks():
    return _run(repo.kb_chunks)


# ── 집계 (관리자 대시보드가 쓴다) ──────────────────────

def member_chunk_count():
    return _run(repo.member_chunk_count)


def persona_lengths():
    return _run(repo.persona_lengths)


# ── 재임베딩 쓰기 (app/engine/resync.py 가 쓴다) ────────

def replace_kb_chunks(uuid, rows):
    return _run(repo.replace_kb_chunks, uuid, rows)


def replace_member_chunks(customer_id, rows):
    return _run(repo.replace_member_chunks, customer_id, rows)
