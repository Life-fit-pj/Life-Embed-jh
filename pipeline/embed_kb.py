"""
할 일 : 청크를 벡터로 바꿔 DB 에 저장
"""

import sqlite3
import time
import numpy as np

from app.core.config import DATA_DIR, DB_PATH, EMBED_MODEL
from app.core.io import read_csv
from app.core.llm import get_embedder, to_passage

BATCH_SIZE = 32

SOURCE = DATA_DIR / "kb_chunk.csv"

    
def create_table(cur) :
    """청크와 벡터를 담을 표를 만든다.

    IF NOT EXISTS 를 쓰는 이유 —
    01_schema.py 는 DB 를 통째로 지우고 다시 만들지만,
    이 파일은 기존 DB 에 표 하나만 덧붙인다.
    임베딩은 20~40분 걸리므로 실수로 날리면 안 된다.
    """
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kb_chunk (
            chunk_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid        TEXT,
            district    TEXT,
            category    TEXT,
            text        TEXT,
            vector      BLOB
        )
    """)
    # SQLite에 숫자 배열 타입이 없어서 TEXT 사용
    # json.dumps로 글자로 눌러 담고, 꺼낼 때 json.loads로 되돌림


def embed_and_store(cur, con, rows):
    total = len(rows)
    started = time.time()

    for start in range(0, total, BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        docs = [to_passage(r["text"]) for r in batch]

        vectors = get_embedder().embed_documents(docs)

        values = [
            (r["uuid"], r["district"], r["category"], r["text"],
            np.asarray(vec, dtype="float32").tobytes())
            for r, vec in zip(batch, vectors)
        ]


        cur.executemany(
            "INSERT INTO kb_chunk (uuid, district, category, text, vector) VALUES (?, ?, ?, ?, ?)",
            values,
        )
        con.commit()   # 배치 하나가 끝날 때마다 저장 — 여기서 죽어도 이전 배치는 남는다

        done = min(start + BATCH_SIZE, total)
        elapsed = time.time() - started
        print(f"⏳ {done:,}/{total:,}개 처리 중... ({elapsed:.0f}초 경과)")

    print(f"✅ 완료 ({time.time() - started:.0f}초)")


# 실행함수

if __name__ == "__main__" :
    _, rows = read_csv(SOURCE)      # , limit=100) : 100개로 한정해서 돌린 결과 정상.지우고 다시 읽음
    print(f"✅ 청크 {len(rows):,}개 읽음")
    
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    create_table(cur)
    
    # 이미 넣어둔 게 있으면 물어본다. 20~40분짜리 작업이라 실수로 날리면 안 된다
    done = cur.execute("SELECT COUNT(*) FROM kb_chunk").fetchone()[0]
    if done > 0 :
        answer = input(f"kb_chunk 에 이미 {done:,} 줄이 있어요! 지우고 처음부터 다시할까요? (y/n) ")
        if answer.lower() == "y" :
            cur.execute("DELETE FROM kb_chunk")
            con.commit()
            done = 0
        # 'n' 이면 done 그대로 두고 이어서 진행

    embed_and_store(cur, con, rows[done:])
    con.commit()

    
    # 확인
    n = cur.execute("SELECT COUNT(*) FROM kb_chunk").fetchone()[0]
    sample = cur.execute("SELECT vector FROM kb_chunk LIMIT 1").fetchone()[0]
    print(f"   벡터 길이: {len(np.frombuffer(sample, dtype='float32'))}개 숫자")
    print(f"✅ 저장된 줄: {n:,}")

    con.close()









