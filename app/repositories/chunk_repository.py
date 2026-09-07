"""청크 표 둘을 다룬다. member_chunk 와 kb_chunk.

돌려주는 것은 전부 딕셔너리·튜플이다 — ORM 객체를 내보내면
세션이 닫힌 뒤 쓸 수 없다(DetachedInstanceError).
옛 app/tables/chunks.py 와 반환 모양을 똑같이 맞춘다.
"""

from sqlalchemy import Integer, cast, func

from app.models.chunk import KbChunk, MemberChunk

# 옛 SQL 이 SELECT 하던 칸 그대로다. 순서까지 맞춘다 —
# 부르는 쪽이 딕셔너리 키로 쓰므로 하나라도 빠지면 KeyError 가 난다
MEMBER_FIELDS = ("customer_id", "category", "text", "vector")
KB_FIELDS = ("chunk_id", "uuid", "district", "category", "text", "vector")


def _rows(db, model, fields):
    """고른 칸만 딕셔너리 목록으로 꺼낸다.

    db.query(모델) 이 아니라 db.query(칸, 칸, …) 을 쓴다.
    벡터가 붙어 있는 표라 안 쓰는 칸까지 실어 오면 무겁다.
    """
    columns = [getattr(model, name) for name in fields]
    return [dict(zip(fields, row)) for row in db.query(*columns).all()]


def member_chunks(db):
    """회원 청크와 벡터를 전부 꺼낸다."""
    return _rows(db, MemberChunk, MEMBER_FIELDS)


def kb_chunks(db):
    """지식베이스 청크와 벡터를 전부 꺼낸다."""
    return _rows(db, KbChunk, KB_FIELDS)


# ── 집계 (관리자 대시보드가 쓴다) ──────────────────────

def member_chunk_count(db):
    """회원 청크가 몇 개 쌓여 있나."""
    return db.query(func.count()).select_from(MemberChunk).scalar()


def persona_lengths(db):
    """페르소나 칸별 평균 글자 수. (칸이름, 평균길이) 목록.

    옛 SQL 의 CAST(AVG(LENGTH(text)) AS INT) 를 그대로 옮긴 것이다.
    ORDER BY 2 DESC 는 "두 번째 칸으로 정렬" 인데 ORM 에는 번호가 없으므로,
    그 식에 이름을 붙여 두고(avg_length) 그걸로 정렬한다.
    """
    avg_length = cast(func.avg(func.length(MemberChunk.text)), Integer)

    return [
        tuple(row)
        for row in db.query(MemberChunk.category, avg_length)
        .group_by(MemberChunk.category)
        .order_by(avg_length.desc())
        .all()
    ]


# ── 재임베딩 쓰기 (app/engine/resync.py 가 쓴다) ────────
# 지우기와 넣기는 항상 짝으로 돈다. 따로 두면 하나만 부르는 사고가 나므로
# 한 함수로 묶고 이름을 replace_ 로 짓는다

def replace_kb_chunks(db, uuid, rows):
    """kb 페르소나 한 명의 청크를 통째로 갈아 끼운다.

    rows 는 (uuid, district, category, text, vector) 튜플 목록이다.
    """
    db.query(KbChunk).filter(KbChunk.uuid == uuid).delete(synchronize_session=False)
    db.add_all([
        KbChunk(uuid=u, district=d, category=c, text=t, vector=v)
        for u, d, c, t, v in rows
    ])
    db.commit()


def replace_member_chunks(db, customer_id, rows):
    """회원 한 명의 청크를 통째로 갈아 끼운다.

    rows 는 (customer_id, category, text, vector) 튜플 목록이다.
    """
    db.query(MemberChunk).filter(
        MemberChunk.customer_id == customer_id
    ).delete(synchronize_session=False)
    db.add_all([
        MemberChunk(customer_id=cid, category=c, text=t, vector=v)
        for cid, c, t, v in rows
    ])
    db.commit()
