import json
import sqlite3
import numpy as np
from app.core.config import DB_PATH

def migrate(table, con):
    cur = con.cursor()
    cur.execute(f"ALTER TABLE {table} ADD COLUMN vector_blob BLOB")

    rows = cur.execute(f"SELECT chunk_id, vector FROM {table}").fetchall()
    for chunk_id, vector_json in rows:
        vec = np.array(json.loads(vector_json), dtype="float32")   # 반드시 float32
        cur.execute(
            f"UPDATE {table} SET vector_blob = ? WHERE chunk_id = ?",
            (vec.tobytes(), chunk_id),
        )
    con.commit()
    print(f"✅ {table}: {len(rows):,}줄 변환 완료")

if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    migrate("kb_chunk", con)
    migrate("member_chunk", con)
    con.close()