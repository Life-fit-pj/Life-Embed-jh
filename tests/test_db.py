"""app/db.py 가 실제 DB 에 제대로 붙었나. 2단계 확인용.

실행: py -m pytest tests/test_db.py -v
"""

import threading

from sqlalchemy import func

from app.core.config import DB_PATH
from app.db import SessionLocal, engine
from app.models.customer import Customer


def test_engine_이_그_life_db_를_본다():
    """DATABASE_URL 을 잘못 만들면 sqlite 가 빈 파일을 새로 만들어 버린다.

    그러면 표가 하나도 없는 DB 로 조용히 돌아가므로, 경로를 직접 대조한다.
    """
    assert engine.url.database.replace("\\", "/") == DB_PATH.as_posix()


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
    """app/core/db.py 가 threading.local() 로 손수 풀던 문제다. (이론 4)

    check_same_thread=False 를 빠뜨리면 여기서 ProgrammingError 가 난다.
    """
    results = [None] * 4
    threads = [threading.Thread(target=count_customers, args=(results, i)) for i in range(4)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == [100, 100, 100, 100]
