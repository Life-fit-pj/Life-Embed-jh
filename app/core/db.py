""" SQLite 조회 기능을 여기 모아둔다.

    pipeline/ 은 DB 를 만들고 채우는 역할,
    이 파일은 이미 만들어진 표에서 데이터를 꺼내는 역할만 한다.

    나중에 다른 DB 로 바꾸더라도 이 파일만 고치면 되도록 분리해 둔다.
"""

import sqlite3
import threading

from app.core.config import DB_PATH
# 연결을 스레드마다 따로 만든다.
#
# SQLite 연결 하나를 여러 스레드가 동시에 쓰면 내부 상태가 엉켜
# "bad parameter or other API misuse" 가 난다.
# FastAPI 는 요청마다 다른 스레드에서 처리하므로 이 문제가 드러난다.
# threading.local() 은 스레드별로 따로 보관되는 저장소다
_local = threading.local()


def get_con():
    """이 스레드 전용 연결을 돌려준다. 없으면 만든다."""
    if not hasattr(_local, "con"):
        _local.con = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _local.con


def query(sql, params=()):
    """여러 줄을 튜플 목록으로 돌려준다."""
    return get_con().execute(sql, params).fetchall()


def one(sql, params=()):
    """한 줄만 돌려준다. 없으면 None."""
    return get_con().execute(sql, params).fetchone()


def dicts(sql, params=()):
    """칸 이름이 붙은 딕셔너리 목록으로 돌려준다.

    query 는 ('종로구', '청운효자동', 0.5) 처럼 튜플이라
    r[0], r[1] 처럼 위치로 꺼내야 한다.
    칸 순서가 바뀌면 조용히 잘못된 값을 읽게 된다.

    dicts 는 r["행정동명"] 처럼 이름으로 꺼낼 수 있다.
    특히 Claude 에게 데이터를 넘길 때는 칸 이름이 있어야
    LLM 이 무엇을 보고 있는지 알 수 있다.
    """
    cur = get_con().execute(sql, params)
    columns = [c[0] for c in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def table_columns(table):
    """표에 실제로 있는 칸 이름들. 없는 표면 빈 집합.

    "이 칸이 진짜 있나"를 묻는 용도다 — SQLite 는 큰따옴표로 감싼 이름이 칸으로
    안 잡히면 에러를 내지 않고 그걸 **문자열 리터럴**로 해석한다.
    `SELECT "녹지_초기"` 가 글자 '녹지_초기' 를 100줄 돌려주는 식이라,
    화면까지 조용히 흘러가 NaN 으로 나타난다. 그러니 `_초기` 처럼 CSV 에 없고
    적재 때 파생시키는 칸을 읽기 전에는 여기서 먼저 확인한다
    """
    return {row[1] for row in query(f'PRAGMA table_info("{table}")')}

