"""
할 일 : 회원 100명의 페르소나를 벡터로 만들어 저장

kb_chunk(지식베이스 2,500명)와 별개다.
회원은 user_preferences(가중치 7개)를 갖고 있어서,
검색어와 비슷한 회원을 찾으면 그 사람의 가중치를 가져올 수 있다.
"""

import json
import sqlite3
import time

from core.config import DATA_DIR, DB_PATH, CHUNK_COLUMNS, MIN_LENGTH
from core.io import read_csv
from core.llm import get_embedder

MEMBER_COUNT = 100

SOURCE = DATA_DIR / "nemotron.csv"


# 회원 읽고 customer_id 붙이기

def load_members(path, count=MEMBER_COUNT) :
    """nemotron.csv 앞 count 명을 읽고 customer_id 를 붙인다.

    원본 CSV 에는 customer_id 칸이 없다.
    customers.csv 의 C001~C100 과 순서로 맞추는 것이 조장님이 잡아둔 규칙이라
    여기서도 같은 방식으로 만든다.
    """
    _, rows = read_csv(path, limit=count)
    
    # zfill(3) 은 앞을 0 으로 채워 자릿수를 맞춘다: 1 -> '001'
    for i, row in enumerate(rows, start=1) :
        row["customer_id"] = f"C{str(i).zfill(3)}"
    
    print(f"✅ 회원 {len(rows)}명 읽음 (C001 ~ C{str(len(rows)).zfill(3)})")
    return rows


def make_chunks(rows):
    """회원 한 명을 칸별 청크로 쪼갠다. 03번과 같은 방식."""
    chunks = []
    
    for row in rows :
        for column in CHUNK_COLUMNS:
            text = (row.get(column) or "").strip()
            
            if len(text) < MIN_LENGTH:
                continue
            
            chunks.append({
                "customer_id" : row["customer_id"],
                "category" : column,        # 어느 칸에서 나왔는지
                "text" : text,
            })
    
    return chunks

def create_table(cur) :
    """회원 청크와 벡터를 담을 표"""
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS member_chunk (
            chunk_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            category    TEXT,
            text        TEXT,
            vector      TEXT
        )
    """)


def to_passage(text):
    return f"passage: {text}"


def embed_and_store(cur, chunks) :
    """청크를 벡터로 바꿔 DB 에 넣는다. 4번과 같음"""

    docs = [to_passage(c["text"]) for c in chunks]
    
    print(f"⏳ {len(docs):,}개 청크를 벡터로 바꾸는 중...")
    started = time.time()

    vectors = get_embedder().embed_documents(docs)
    
    print(f"✅ 완료 ({time.time() - started:.0f}초)")
    
    values = [
        (c["customer_id"], c["category"], c["text"],
         json.dumps(vec))
        for c, vec in zip(chunks, vectors)
    ]
    
    cur.executemany(
        "INSERT INTO member_chunk (customer_id, category, text, vector) "
        "VALUES (?, ?, ?, ?)",
        values,
    )


# 실행부

if __name__ == "__main__":
    members = load_members(SOURCE)
    chunks = make_chunks(members)
    print(f"✅ 청크 {len(chunks)}개")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    create_table(cur)

    done = cur.execute("SELECT COUNT(*) FROM member_chunk").fetchone()[0]
    if done > 0:
        cur.execute("DELETE FROM member_chunk")
        print(f"   기존 {done}줄 지움")

    embed_and_store(cur, chunks)

    con.commit()

    n = cur.execute("SELECT COUNT(*) FROM member_chunk").fetchone()[0]
    print(f"✅ 저장된 줄: {n}")

    con.close()