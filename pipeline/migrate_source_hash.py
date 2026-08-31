
import sqlite3
from app.core.config import DB_PATH

def migrate(table, con):
    cur = con.cursor()
    cur.execute(f"ALTER TABLE {table} ADD COLUMN source_hash BLOB")

    cur.execute(f"ALTER TABLE {table} ADD COLUMN source_hash TEXT")
    rows = cur.execute(f"SELECT chunk_id, text FROM {table}").fetchall()
    for chunk_id, text in rows:
        cur.execute(f"UPDATE {table} SET source_hash = ? WHERE chunk_id = ?",
                    (fingerprint(text), chunk_id))
        
    con.commit()
    print(f"✅ {table}: {len(rows):,}줄 변환 완료")

if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    migrate("kb_chunk", con)
    migrate("member_chunk", con)
    con.close()