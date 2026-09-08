"""옛 두 표의 벡터를 chunks 로 옮긴다. 5단계에서 한 번만 쓴다.

왜 다시 계산하지 않나 — 5-0절.
요약하면, 같은 모델이라도 배치 크기가 다르면 소수점 끝자리가 달라질 수 있고
그러면 "구조를 잘못 바꾼 건지 계산이 흔들린 건지" 를 못 가린다.
벡터는 6단계에서 어차피 전부 새로 만든다.

실행: py -m pipeline.migrate_vectors
"""

from app.db import SessionLocal
from app.models.chunk import Chunk, KbChunk, MemberChunk


def main():
    db = SessionLocal()

    # (source, source_id, category, text) -> vector
    old = {}
    for row in db.query(MemberChunk).all():
        old[("member", row.customer_id, row.category, row.text)] = row.vector
    for row in db.query(KbChunk).all():
        old[("kb", row.uuid, row.category, row.text)] = row.vector

    moved = missing = 0
    for chunk in db.query(Chunk).all():
        vector = old.get((chunk.source, chunk.source_id, chunk.category, chunk.text))
        if vector is None:
            missing += 1
            continue
        chunk.vector = vector
        moved += 1

    db.commit()
    print(f"옮김 {moved:,} · 짝이 없음 {missing:,}")
    db.close()


if __name__ == "__main__":
    main()

