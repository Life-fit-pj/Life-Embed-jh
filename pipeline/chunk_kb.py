"""
할 일 : 청킹   
"""

from core.config import DATA_DIR, CHUNK_COLUMNS, MIN_LENGTH
from core.io import read_csv, save_csv

OUTPUT = DATA_DIR / "kb_chunk.csv"


def make_chunks(rows):
    """페르소나 한 명을 칸별 청크 여러 개로 쪼갠다."""
    chunks = []
    
    for row in rows :
        for column in CHUNK_COLUMNS:
            text = (row.get(column) or "").strip()
            
            if len(text) < MIN_LENGTH:
                continue
            
            chunks.append({
                "uuid" : row["uuid"],
                "district" : row["district"],
                "category" : column,        # 어느 칸에서 나왔는지
                "text" : text,
            })
    
    return chunks


if __name__ == "__main__":
    columns, rows = read_csv(DATA_DIR / "kb_persona.csv")
    chunks = make_chunks(rows)

    print(f"✅ {len(rows):,}명 → 청크 {len(chunks):,}개")
    print(f"   평균 {len(chunks)/len(rows):.1f}개/명")
    print()
    for c in chunks[:3]:
        print(f"   💬 [{c['category']}] {c['text'][:60]}...")
    print()
    
    save_csv(chunks, OUTPUT)









