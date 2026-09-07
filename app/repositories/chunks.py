"""임베딩 청크 표를 다루는 SQL. 회원 청크와 지식베이스 청크."""

from app.core.db import dicts, get_con, one, query      # 실행기는 core 에서 가져온다


def member_chunks():
    """회원 청크와 벡터를 전부 꺼낸다. (07번에서 쓰던 것)"""
    return dicts(
        "SELECT customer_id, category, text, vector FROM member_chunk"
    )


def kb_chunks():
    """지식베이스 청크와 벡터를 전부 꺼낸다. (09번에서 쓸 것)"""
    return dicts(
        "SELECT chunk_id, uuid, district, category, text, vector FROM kb_chunk"
    )


# ── 집계 (관리자 대시보드가 쓴다) ──────────────────────

def member_chunk_count():
    """회원 청크가 몇 개 쌓여 있나."""
    return one("SELECT COUNT(*) FROM member_chunk")[0]


def persona_lengths():
    """페르소나 칸별 평균 글자 수. (칸이름, 평균길이) 목록."""
    return query(
        "SELECT category, CAST(AVG(LENGTH(text)) AS INT) FROM member_chunk "
        "GROUP BY 1 ORDER BY 2 DESC"
    )


# ── 재임베딩 쓰기 (app/engine/resync.py 가 쓴다) ────────
# 지우기와 넣기는 항상 짝으로 돈다. 따로 두면 하나만 부르는 사고가 나므로
# 한 함수로 묶고 이름을 replace_ 로 짓는다

def replace_kb_chunks(uuid, rows):
    """kb 페르소나 한 명의 청크를 통째로 갈아 끼운다.

    rows 는 (uuid, district, category, text, vector) 튜플 목록이다.
    """
    con = get_con()
    con.execute("DELETE FROM kb_chunk WHERE uuid = ?", (uuid,))
    con.executemany(
        "INSERT INTO kb_chunk (uuid, district, category, text, vector) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()


def replace_member_chunks(customer_id, rows):
    """회원 한 명의 청크를 통째로 갈아 끼운다.

    rows 는 (customer_id, category, text, vector) 튜플 목록이다.
    """
    con = get_con()
    con.execute("DELETE FROM member_chunk WHERE customer_id = ?", (customer_id,))
    con.executemany(
        "INSERT INTO member_chunk (customer_id, category, text, vector) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()