"""
할 일 : 청킹   
"""

from app.core.config import DATA_DIR
from pipeline.io import read_csv, save_csv
from pipeline.prep.chunking import make_chunks, KB_KEYS

OUTPUT = DATA_DIR / "kb_chunk.csv"


if __name__ == "__main__":
    columns, rows = read_csv(DATA_DIR / "kb_persona.csv")
    chunks = make_chunks(rows, KB_KEYS)

    print(f"✅ {len(rows):,}명 → 청크 {len(chunks):,}개")
    print(f"   평균 {len(chunks)/len(rows):.1f}개/명")
    print()
    for c in chunks[:3]:
        print(f"   💬 [{c['category']}] {c['text'][:60]}...")
    print()
    
    save_csv(chunks, OUTPUT)









