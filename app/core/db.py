"""날 SQL 을 실행하는 곳. 연결은 app/db.py 의 engine 하나뿐이다.

ORM 으로 안 옮긴 표(master_dataset_v3 칸 86개 · user_login)를 여기로 읽는다.
SQL 은 그대로 두고 자리표시자만 :이름 으로 적는다 — 드라이버가 바뀌어도
SQLAlchemy 가 번역해 주므로 이 파일도 부르는 쪽도 안 고치게 된다.

옛 sqlite3 + threading.local() 은 없앴다. 연결이 둘이면 DATABASE_URL 을
바꿨을 때 한쪽만 따라가고, 그때 regions 는 조용히 옛 데이터를 읽는다(4A-1)
"""

from sqlalchemy import text

from app.db import engine


def query(sql, params=None):
    """여러 줄을 튜플 목록으로 돌려준다."""
    with engine.connect() as con:
        return con.execute(text(sql), params or {}).fetchall()


def one(sql, params=None):
    """한 줄만 돌려준다. 없으면 None."""
    with engine.connect() as con:
        return con.execute(text(sql), params or {}).fetchone()


def dicts(sql, params=None):
    """칸 이름이 붙은 딕셔너리 목록으로 돌려준다.

    query 는 ('종로구', '청운효자동', 0.5) 처럼 튜플이라
    r[0], r[1] 처럼 위치로 꺼내야 한다.
    칸 순서가 바뀌면 조용히 잘못된 값을 읽게 된다.

    dicts 는 r["행정동명"] 처럼 이름으로 꺼낼 수 있다.
    특히 Claude 에게 데이터를 넘길 때는 칸 이름이 있어야
    LLM 이 무엇을 보고 있는지 알 수 있다.
    """
    with engine.connect() as con:
        return [dict(row) for row in con.execute(text(sql), params or {}).mappings()]


def run(sql, params=None):
    """쓰기(UPDATE·INSERT). 커밋까지 한다. 옛 get_con().execute(...)+commit() 자리다."""
    with engine.begin() as con:
        con.execute(text(sql), params or {})
