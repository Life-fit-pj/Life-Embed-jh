"""청크 표 둘을 다룬다. member_chunk 와 kb_chunk.

돌려주는 것은 전부 딕셔너리·튜플이다 — ORM 객체를 내보내면
세션이 닫힌 뒤 쓸 수 없다(DetachedInstanceError).
옛 app/tables/chunks.py 와 반환 모양을 똑같이 맞춘다.
"""

from sqlalchemy import Integer, cast, func

from app.models.chunk import Chunk

# 부르는 쪽이 쓰는 딕셔너리 키다. 표를 합친 뒤에도 이 이름은 안 바꾼다 —
# source_id 하나를 member 에서는 customer_id, kb 에서는 uuid 로 돌려준다.
# 3-A 에서 _초기 를 뗀 키로 돌려주던 것과 같은 손놀림이다
MEMBER_FIELDS = ("customer_id", "category", "text", "vector")
KB_FIELDS = ("chunk_id", "uuid", "district", "category", "text", "vector")


def _rows(db, source, fields, columns):
    """한 source 의 줄만 딕셔너리 목록으로 꺼낸다.

    db.query(Chunk) 가 아니라 db.query(칸, 칸, …) 을 쓴다.
    벡터가 붙어 있는 표라 안 쓰는 칸까지 실어 오면 무겁다.
    """
    return [
        dict(zip(fields, row))
        for row in db.query(*columns).filter(Chunk.source == source).all()
    ]


def member_chunks(db):
    """회원 청크와 벡터를 전부 꺼낸다. 키는 옛 이름 그대로 customer_id 다."""
    columns = (Chunk.source_id, Chunk.category, Chunk.text, Chunk.vector)
    return _rows(db, "member", MEMBER_FIELDS, columns)


def kb_chunks(db):
    """지식베이스 청크와 벡터를 전부 꺼낸다. 키는 옛 이름 그대로 uuid 다."""
    columns = (
        Chunk.chunk_id, Chunk.source_id, Chunk.district,
        Chunk.category, Chunk.text, Chunk.vector,
    )
    return _rows(db, "kb", KB_FIELDS, columns)


# ── 집계 (관리자 대시보드가 쓴다) ──────────────────────

def member_chunk_count(db):
    """회원 청크가 몇 개 쌓여 있나."""
    return (
        db.query(func.count())
        .select_from(Chunk)
        .filter(Chunk.source == "member")
        .scalar()
    )


def persona_lengths(db):
    """페르소나 칸별 평균 글자 수. (칸이름, 평균길이) 목록."""
    avg_length = cast(func.avg(func.length(Chunk.text)), Integer)

    return [
        tuple(row)
        for row in db.query(Chunk.category, avg_length)
        .filter(Chunk.source == "member")
        .group_by(Chunk.category)
        .order_by(avg_length.desc())
        .all()
    ]


# ── 재임베딩 쓰기 (app/engine/resync.py 가 쓴다) ────────
# 지우기와 넣기는 항상 짝으로 돈다. 따로 두면 하나만 부르는 사고가 나므로
# 한 함수로 묶고 이름을 replace_ 로 짓는다

def replace_kb_chunks(db, uuid, rows):
    """kb 페르소나 한 명의 청크를 통째로 갈아 끼운다.

    rows 는 (uuid, district, category, text, vector) 튜플 목록이다 — 옛 모양 그대로.
    """
    db.query(Chunk).filter(
        Chunk.source == "kb", Chunk.source_id == uuid
    ).delete(synchronize_session=False)
    db.add_all([
        Chunk(source="kb", source_id=u, district=d, category=c, text=t, vector=v)
        for u, d, c, t, v in rows
    ])
    db.commit()


def replace_member_chunks(db, customer_id, rows):
    """회원 한 명의 청크를 통째로 갈아 끼운다.

    rows 는 (customer_id, category, text, vector) 튜플 목록이다.
    """
    db.query(Chunk).filter(
        Chunk.source == "member", Chunk.source_id == customer_id
    ).delete(synchronize_session=False)
    db.add_all([
        Chunk(source="member", source_id=cid, category=c, text=t, vector=v)
        for cid, c, t, v in rows
    ])
    db.commit()
