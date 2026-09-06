"""쌓이는 기록 표를 다루는 SQL. 좋아요 · 검색기록 · 채팅기록 · 로그인 · 관리자로그."""

import json
from datetime import datetime

from app.core.db import dicts, get_con, one, query      # 실행기는 core 에서 가져온다


_like_ready = False

# => 좋아요

def ensure_likes():
    """likes 테이블이 없으면 만든다."""
    global _like_ready
    if _like_ready: return

    get_con().execute("""
        CREATE TABLE IF NOT EXISTS likes (
            anon_id TEXT NOT NULL,
            구 TEXT NOT NULL,
            행정동명 TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (anon_id, 구, 행정동명)
        )
    """)
    get_con().commit()
    _like_ready = True


def add_like(anon_id, gu, dong):
    """좋아요 추가. 이미 있을 경우 무시"""
    ensure_likes()
    get_con().execute("""
        INSERT OR IGNORE INTO likes (anon_id, 구, 행정동명) VALUES (?, ?, ?)
    """,(anon_id,gu,dong),)
    get_con().commit()


def remove_like(anon_id, gu, dong):
    """좋아요 취소."""
    ensure_likes()
    get_con().execute("""
        DELETE FROM likes WHERE anon_id = ? AND 구 = ? AND 행정동명 =?
    """, (anon_id, gu, dong),)
    get_con().commit()


def list_likes(anon_id):
    """이 사람이 좋아요 누른 동네 목록. 최근 순."""
    ensure_likes()
    return dicts("""
        SELECT 구, 행정동명, created_at FROM likes
        WHERE anon_id = ? ORDER BY created_at DESC
    """, (anon_id,))


# => 검색

_search_history_ready = False

def ensure_search_history():
    """search_history 테이블이 없으면 만든다."""
    global _search_history_ready
    if _search_history_ready: return

    get_con().execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            anon_id TEXT NOT NULL,
            query TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    get_con().commit()
    _search_history_ready = True


def add_search_history(anon_id, query):
    """검색어 기록 추가. 같은 검색어라도 매번 새 줄로 남긴다(likes와 달리 유니크 제약 없음)"""
    ensure_search_history()
    get_con().execute("""
        INSERT INTO search_history (anon_id, query) VALUES (?, ?)
    """, (anon_id, query),)
    get_con().commit()


def list_search_history(anon_id, limit=20):
    """최근 검색어부터 반환."""
    ensure_search_history()
    return dicts("""
        SELECT query, created_at FROM search_history
        WHERE anon_id = ? ORDER BY created_at DESC LIMIT ?
    """, (anon_id, limit))


# => 채팅

_chat_history_ready = False

def ensure_chat_history():
    """chat_history 테이블이 없으면 만든다."""
    global _chat_history_ready
    if _chat_history_ready: return

    get_con().execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            anon_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    get_con().commit()
    _chat_history_ready = True


def add_chat_history(anon_id, question, answer):
    """채팅 질문/답변 기록 추가."""
    ensure_chat_history()
    get_con().execute("""
        INSERT INTO chat_history (anon_id, question, answer) VALUES (?, ?, ?)
    """, (anon_id, question, answer),)
    get_con().commit()


def list_chat_history(anon_id, limit=20):
    """최근 대화부터 반환."""
    ensure_chat_history()
    return dicts("""
        SELECT question, answer, created_at FROM chat_history
        WHERE anon_id = ? ORDER BY created_at DESC LIMIT ?
    """, (anon_id, limit))


def ensure_admin_log() -> None:
    """관리자 수정 이력 표. 없으면 만든다 (있으면 아무 일도 안 한다)."""
    get_con().execute("""
        CREATE TABLE IF NOT EXISTS admin_log (
            log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            target     TEXT,      -- 'member' 또는 'region'
            target_id  TEXT,      -- 'C001' 또는 '강남구 역삼1동'
            patch      TEXT,      -- 보낸 값 그대로 (JSON 문자열)
            changed_at TEXT       -- 언제
        )
    """)
    get_con().commit()


def write_admin_log(target: str, target_id: str, patch: dict) -> None:
    """수정 한 건을 남긴다."""
    ensure_admin_log()
    get_con().execute(
        "INSERT INTO admin_log (target, target_id, patch, changed_at) VALUES (?, ?, ?, ?)",
        (target, target_id, json.dumps(patch, ensure_ascii=False),
         datetime.now().isoformat(timespec="seconds")),
    )
    get_con().commit()


# => 로그인

_user_login_ready = False

def ensure_user_login():
    """user_login 테이블이 없으면 만든다. login_id 가 기본키다 — 계정 풀이
    소진되면 같은 customer_id 에 로그인이 여러 개 붙을 수 있어야 해서
    (빈 계정을 새로 만드는 대신 기존 회원을 재사용하는 정책), customer_id는
    더 이상 유일하지 않다.

    예전 스키마(customer_id가 기본키)로 이미 만들어진 DB라면 데이터를
    보존한 채 새 스키마로 옮긴다.
    """
    global _user_login_ready
    if _user_login_ready: return

    con = get_con()
    pk_cols = [r[1] for r in con.execute("PRAGMA table_info(user_login)").fetchall() if r[5] == 1]
    if pk_cols == ["customer_id"]:
        con.execute("ALTER TABLE user_login RENAME TO user_login_old")
        con.execute("""
            CREATE TABLE user_login (
                login_id    TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                password    TEXT NOT NULL,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            INSERT INTO user_login (login_id, customer_id, password, created_at)
            SELECT login_id, customer_id, password, created_at FROM user_login_old
        """)
        con.execute("DROP TABLE user_login_old")
    else:
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_login (
                login_id    TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                password    TEXT NOT NULL,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    con.commit()
    _user_login_ready = True


def pick_customer_for_login():
    """새 아이디를 붙일 customer_id 를 고른다. 로그인이 아직 없는 회원을
    우선하고, 전부 배정됐으면 로그인이 가장 적게 붙은 회원을 다시 쓴다 —
    빈 계정은 절대 새로 만들지 않고 항상 기존 회원 정보에 붙인다."""
    ensure_user_login()
    row = one("""
        SELECT c.customer_id FROM customers c
        LEFT JOIN user_login u ON u.customer_id = c.customer_id
        GROUP BY c.customer_id
        ORDER BY COUNT(u.customer_id) ASC, c.customer_id ASC
        LIMIT 1
    """)
    return row[0] if row else None


def create_login(customer_id, login_id, password):
    """로그인 계정 발급."""
    ensure_user_login()
    get_con().execute(
        "INSERT INTO user_login (customer_id, login_id, password) VALUES (?, ?, ?)",
        (customer_id, login_id, password),
    )
    get_con().commit()


def get_login_row(login_id):
    """login_id 하나의 계정 정보. 없으면 None. 로그인 시 "아이디가 아예 없는지"와
    "비번이 틀렸는지"를 구분해야 즉석 발급이 가능해서 find_login 대신 이걸 쓴다."""
    ensure_user_login()
    row = one(
        "SELECT customer_id, password FROM user_login WHERE login_id = ?",
        (login_id,),
    )
    return {"customer_id": row[0], "password": row[1]} if row else None