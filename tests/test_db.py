"""app/db.py 가 실제 DB 에 제대로 붙었나. 2단계 확인용.

실행: py -m pytest tests/test_db.py -v
"""

import threading

from sqlalchemy import func

from app.core.config import DATABASE_URL
from app.db import SessionLocal, engine
from app.models.customer import Customer


def test_engine_이_설정한_DB_를_본다():
    """DATABASE_URL 을 잘못 적으면 엉뚱한 DB 에 붙는다.

    옛 판은 "파일 경로가 life.db 인가" 를 봤다. DB 가 파일이 아니게 되면서
    그 질문이 성립하지 않는다 — 방언이 postgresql 인지로 바꾼다
    """
    assert engine.dialect.name == "postgresql"
    assert engine.url.render_as_string(hide_password=True).startswith("postgresql")
    

def test_세션은_부를_때마다_새것이다():
    """SessionLocal 은 세션이 아니라 세션을 찍어내는 틀이다. (이론 4)"""
    a = SessionLocal()
    b = SessionLocal()
    try:
        assert a is not b
    finally:
        a.close()
        b.close()


def count_customers(results, index):
    db = SessionLocal()
    try:
        results[index] = db.query(func.count()).select_from(Customer).scalar()
    finally:
        db.close()


def test_여러_스레드가_동시에_읽어도_안_죽는다():
    """engine 은 연결을 풀에 넣고 여러 스레드가 돌려쓴다. (이론 4)

    FastAPI 가 요청마다 다른 스레드에서 처리하므로 실제로 그렇게 된다.
    옛날에는 app/core/db.py 가 threading.local() 로 이걸 손수 풀었고,
    SQLite 라서 check_same_thread=False 도 필요했다 — 둘 다 없앴다.
    이 시험은 그 뒤에도 여전히 안 죽는지를 본다
    """
    results = [None] * 4
    threads = [threading.Thread(target=count_customers, args=(results, i)) for i in range(4)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == [100, 100, 100, 100]
