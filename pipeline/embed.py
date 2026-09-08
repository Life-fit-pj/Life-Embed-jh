"""벡터가 없는 청크만 골라 채운다.

실행: py -m pipeline.embed

옛 embed_kb.py 는 input() 으로 "지우고 다시 할까요?" 를 묻고 rows[done:] 로
손수 이어 붙였다(85~92행). 여기서는 vector IS NULL 인 것을 찾으므로
중간에 끊겨도 그냥 다시 돌리면 남은 것부터 이어서 한다.
"""

import time

import numpy as np

from app.ai.embedder import embed_documents, to_passage
from app.db import SessionLocal
from app.models.chunk import Chunk

# 한 번에 보낼 청크 수. 하나씩 보내면 9,900번을 불러야 해서 매우 느리다
BATCH_SIZE = 32


def find_chunks_to_embed(db):
    """아직 벡터가 없는 청크. 이 한 줄이 '이어 하기' 를 공짜로 만든다."""
    return db.query(Chunk).filter(Chunk.vector.is_(None)).all()


def main():
    db = SessionLocal()

    todo = find_chunks_to_embed(db)
    total = db.query(Chunk).count()

    if not todo:
        print(f"이미 전부 임베딩되어 있다. ({total:,}개)")
        db.close()
        return

    print(f"전체 {total:,}개 중 {len(todo):,}개를 임베딩한다. 한 번에 {BATCH_SIZE}개씩")
    started = time.time()

    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        vectors = embed_documents([to_passage(chunk.text) for chunk in batch])

        for chunk, vector in zip(batch, vectors):
            chunk.vector = np.asarray(vector, dtype="float32").tobytes()

        db.commit()   # 배치마다 저장 — 여기서 죽어도 앞 배치는 남는다

        done = min(start + BATCH_SIZE, len(todo))
        print(f"\r  {done:,}/{len(todo):,}  ({time.time() - started:.0f}초)", end="")

    print(f"\n완료 ({time.time() - started:.0f}초)")
    db.close()


if __name__ == "__main__":
    main()
