"""CSV 를 읽어 잘라서 chunks 표에 넣는다. 벡터는 여기서 안 만든다.

실행: py -m pipeline.chunk

자르는 규칙은 app/ai/chunker.py 에 있다 — 관리자 수정(resync)도 같은 함수를 쓴다.
여러 번 돌려도 된다. 매번 chunks 를 비우고 다시 채운다.

옛 파일 셋이 하던 일을 여기 모았다 —
  chunk_kb.py      kb_persona.csv -> kb_chunk.csv   (중간 파일을 없앴다)
  embed_kb.py      kb_chunk.csv -> kb_chunk 표      (임베딩은 pipeline/embed.py 로)
  embed_member.py  nemotron.csv -> member_chunk 표  (청킹만 여기 남았다)
"""

from app.ai.chunker import KB_KEYS, MEMBER_KEYS, make_chunks
from app.core.config import DATA_DIR
from app.db import SessionLocal, engine
from app.models.chunk import Chunk
from pipeline.io import read_csv

MEMBER_COUNT = 100
MEMBER_SOURCE = DATA_DIR / "nemotron.csv"
KB_SOURCE = DATA_DIR / "kb_persona.csv"


def load_members(path, count=MEMBER_COUNT):
    """nemotron.csv 앞 count 명을 읽고 customer_id 를 붙인다.

    원본 CSV 에는 customer_id 칸이 없다. customers.csv 의 C001~C100 과
    순서로 맞추는 것이 조장님이 잡아둔 규칙이라 여기서도 같은 방식으로 만든다
    """
    _, rows = read_csv(path, limit=count)

    # zfill(3) 은 앞을 0 으로 채워 자릿수를 맞춘다: 1 -> '001'
    for i, row in enumerate(rows, start=1):
        row["customer_id"] = f"C{str(i).zfill(3)}"

    return rows


def to_chunks(rows, source, id_key):
    """청크 딕셔너리를 Chunk 객체로 바꾼다.

    district 는 kb 에만 있다. member 는 None 이 들어간다
    """
    return [
        Chunk(
            source=source,
            source_id=row[id_key],
            district=row.get("district"),
            category=row["category"],
            text=row["text"],
        )
        for row in rows
    ]


def main():
    Chunk.__table__.create(engine, checkfirst=True)

    members = load_members(MEMBER_SOURCE)
    _, kb_people = read_csv(KB_SOURCE)

    member_rows = make_chunks(members, MEMBER_KEYS)
    kb_rows = make_chunks(kb_people, KB_KEYS)

    db = SessionLocal()
    db.query(Chunk).delete()
    db.add_all(to_chunks(member_rows, "member", "customer_id"))
    db.add_all(to_chunks(kb_rows, "kb", "uuid"))
    db.commit()

    print(f"member {len(member_rows):,}개 · kb {len(kb_rows):,}개 "
          f"· 표에 든 줄 {db.query(Chunk).count():,}")
    db.close()


if __name__ == "__main__":
    main()
