"""회원 한 명 또는 kb 페르소나 한 명의 벡터만 다시 만든다.

관리자가 방금 이 사람 정보를 고쳤다는 게 확실한 상태에서 불리는 함수라서,
"뭐가 바뀌었나" 확인하는 절차 없이 그냥 그 사람 청크를 지우고 새로 만든다.
"""

import numpy as np

from app.adapters.llm import get_embedder, to_passage
from pipeline.prep.chunking import make_chunks, KB_KEYS, MEMBER_KEYS


# 임베딩해서 저장하는, 두 함수가 공통으로 하는 부분만 뽑은 것
def _embed(chunks):
    docs = [to_passage(c["text"]) for c in chunks]
    vectors = get_embedder().embed_documents(docs)
    return [np.asarray(v, dtype="float32").tobytes() for v in vectors]


def resync_kb_person(con, uuid, row):
    """kb 페르소나 한 명을 다시 임베딩한다.

    row 는 kb_persona.csv 한 줄과 같은 모양이어야 한다
    (uuid, district, 그리고 config.CHUNK_COLUMNS 에 있는 칸들을 전부 갖고 있어야 함).
    """
    chunks = make_chunks([row], KB_KEYS)
    vectors = _embed(chunks)

    cur = con.cursor()
    cur.execute("DELETE FROM kb_chunk WHERE uuid = ?", (uuid,))
    cur.executemany(
        "INSERT INTO kb_chunk (uuid, district, category, text, vector) "
        "VALUES (?, ?, ?, ?, ?)",
        [(c["uuid"], c["district"], c["category"], c["text"], vec)
         for c, vec in zip(chunks, vectors)],
    )
    con.commit()


def resync_member(con, customer_id, row):
    """회원 한 명을 다시 임베딩한다.

    row 는 nemotron.csv 한 줄 + customer_id 가 들어간 모양이어야 한다.
    """
    chunks = make_chunks([row], MEMBER_KEYS)
    vectors = _embed(chunks)

    cur = con.cursor()
    cur.execute("DELETE FROM member_chunk WHERE customer_id = ?", (customer_id,))
    cur.executemany(
        "INSERT INTO member_chunk (customer_id, category, text, vector) "
        "VALUES (?, ?, ?, ?)",
        [(c["customer_id"], c["category"], c["text"], vec)
         for c, vec in zip(chunks, vectors)],
    )
    con.commit()