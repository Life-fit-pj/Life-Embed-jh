"""청크 표 하나를 다룬다. chunks — source 로 member 와 kb 를 가른다.

돌려주는 것은 전부 딕셔너리·튜플이다 — ORM 객체를 내보내면
세션이 닫힌 뒤 쓸 수 없다(DetachedInstanceError).
옛 app/tables/chunks.py 와 반환 모양을 똑같이 맞춘다.
"""

from sqlalchemy import Integer, cast, func

from app.models.chunk import Chunk

# 부르는 쪽이 쓰는 딕셔너리 키다. 표를 합친 뒤에도 이 이름은 안 바꾼다 —
# source_id 하나를 member 에서는 customer_id, kb 에서는 uuid 로 돌려준다.
# 3-A 에서 _초기 를 뗀 키로 돌려주던 것과 같은 손놀림이다
MEMBER_FIELDS = ("customer_id", "category", "text")
KB_FIELDS = ("chunk_id", "uuid", "district", "category", "text")

# embedding 은 어느 목록에도 없다 — 비교는 DB 가 하므로 벡터를 실어 올 일이 없다.
# 9,900줄 × 1,536개를 내려받던 것이 Supabase 2분 제한과 egress 초과의 원인이었다(2026-09-22 실측)
_COLUMNS = {
    "member": (Chunk.source_id, Chunk.category,Chunk.text),
    "kb": (Chunk.chunk_id, Chunk.source_id, Chunk.district, Chunk.category, Chunk.text),
}
_FIELDS = {"member": MEMBER_FIELDS, "kb": KB_FIELDS}

# 사람을 가리키는 키. member 는 customer_id, kb 는 uuid
ID_KEY = {"member": "customer_id", "kb": "uuid"}


def _rows(db, source):
    """한 source 의 줄 전부를 딕셔너리 목록으로. 벡터는 안 싣는다 — 골든 사진(지문)용이다."""
    return [
        dict(zip(_FIELDS[source], row))
        for row in db.query(*_COLUMNS[source]).filter(Chunk.source == source).all()
    ]


def member_chunks(db):
    """회원 청크 텍스트 전부 꺼낸다. 키는 옛 이름 그대로 customer_id 다."""
    return _rows(db, "member")


def kb_chunks(db):
    """지식베이스 청크 텍스트 전부. 키는 옛 이름 그대로 uuid 다."""
    return _rows(db, "kb")


# ── 벡터 검색 — 비교를 DB 가 한다 ──────────────────────

def nearest_chunks(db,source, query_vector, top_k=5):
    """질문 벡터와 가까운 청크 top_k. [(행, 점수)] — 점수는 클수록 가깝다.

    cosine_distance 가 pgvector 의 <=> 다(0 = 같음). 저장할 때 길이를 1 로 맞춰 뒀으므로
    1 - 거리 = 코사인 유사도 = 옛 numpy 내적과 같은 값이다.
    ⚠ 필터(source)는 order_by·limit 보다 먼저 건다 — 5개를 뽑은 뒤 거르면 빈손이 된다
    """
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    found = (
        db.query(*_COLUMNS[source], distance)
        .filter(Chunk.source == source)
        .order_by(distance)
        .limit(top_k)
        .all()
    )
    return [(dict(zip(_FIELDS[source], row[:-1])), 1.0 - row[-1]) for row in found]


def nearest_people(db, source, query_vector, top_k=5):
    """사람 단위로 top_k. [(id, 점수, 행)] — 한 사람은 가장 가까운 청크 하나로만 센다.

    후보를 top_k 의 10배 받아 사람별 첫 줄만 남긴다. 한 사람의 청크는 많아야
    9개(config.CHUNK_COLUMNS 의 개수)라, 50개 안에는 반드시 5명 이상이 들어 있다
    """
    
    key = ID_KEY[source]
    people = {}
    for row, score in nearest_chunks(db, source, query_vector, top_k * 10):
        people.setdefault(row[key], (score,row))
    return [(pid, score, row) for pid, (score, row) in list(people.items())[:top_k]]

    
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

    rows 는 (uuid, district, category, text, embedding) 튜플 목록이다 — 옛 모양 그대로.
    embedding 은 6단계부터 float 리스트를 json.dumps 한 문자열이다(resync.py 가 만든다).
    """
    db.query(Chunk).filter(
        Chunk.source == "kb", Chunk.source_id == uuid
    ).delete(synchronize_session=False)
    db.add_all([
        Chunk(source="kb", source_id=u, district=d, category=c, text=t, embedding=v)
        for u, d, c, t, v in rows
    ])
    db.commit()


def replace_member_chunks(db, customer_id, rows):
    """회원 한 명의 청크를 통째로 갈아 끼운다.

    rows 는 (customer_id, category, text, embedding) 튜플 목록이다.
    """
    db.query(Chunk).filter(
        Chunk.source == "member", Chunk.source_id == customer_id
    ).delete(synchronize_session=False)
    db.add_all([
        Chunk(source="member", source_id=cid, category=c, text=t, embedding=v)
        for cid, c, t, v in rows
    ])
    db.commit()
