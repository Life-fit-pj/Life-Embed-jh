"""
할 일 : 청크를 벡터로 바꿔 DB 에 저장
"""

import json
import sqlite3
import sys
import time

from core.config import DATA_DIR, DB_PATH, EMBED_MODEL
from core.io import read_csv
from core.llm import get_embedder

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
            vector      TEXT
        )
    """)
    # SQLite에 숫자 배열 타입이 없어서 TEXT 사용
    # json.dumps로 글자로 눌러 담고, 꺼낼 때 json.loads로 되돌림


def to_passage(text):
    """저장용 문서에 e5 모델이 요구하는 접두사를 붙인다."""
    return f"passage: {text}"


def embed_and_store(cur, rows) :
    """청크를 벡터로 바꿔 DB 에 넣는다."""
    
    # e5 규칙: 저장할 문서에는 passage: 를 붙인다
    docs = [to_passage(r["text"]) for r in rows]
    
    print(f"⏳ {len(docs):,}개 청크를 벡터로 바꾸는 중... (2만2천 개 기준 약 5분)")
    started = time.time()
    
    vectors = get_embedder().embed_documents(docs)
    
    print(f"✅ 완료 ({time.time() - started:.0f}초)")
    
    # 표에 넣을 값 만들기.
    # json.dumps 로 숫자 384개를 글자 하나로 눌러 담는다
    # vec.tolist() : numpy 숫자 묶음을 파이썬 목록으로 바꾸는 것. json.dumps가 처리할 수 있음.
    values = [
        (r["uuid"], r["district"], r["category"], r["text"],
         json.dumps(vec))
        for r, vec in zip(rows, vectors)
    ]
    
    cur.executemany(
        "INSERT INTO kb_chunk (uuid, district, category, text, vector) "
        "VALUES (?, ?, ?, ?, ?)",
        values,
    )


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
        answer = input(f"kb_chunk 에 이미 {done:,} 줄이 있어요! 지우고 다시할까요? (y/n) ")
        if answer.lower() != "y" :
            print("중단합니다!")
            con.close()
            sys.exit(0)
        cur.execute("DELETE FROM kb_chunk")
    
    embed_and_store(cur, rows)
    
    con.commit()
    
    # 확인
    n = cur.execute("SELECT COUNT(*) FROM kb_chunk").fetchone()[0]
    sample = cur.execute("SELECT vector FROM kb_chunk LIMIT 1").fetchone()[0]
    print(f"✅ 저장된 줄: {n:,}")
    print(f"   벡터 길이: {len(json.loads(sample))}개 숫자")

    con.close()









