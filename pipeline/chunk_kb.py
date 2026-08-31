"""
할 일 : 청킹   
"""

from app.core.config import DATA_DIR, CHUNK_COLUMNS, MIN_LENGTH
from app.core.io import read_csv, save_csv
from pipeline.chunking import split_long_text

OUTPUT = DATA_DIR / "kb_chunk.csv"


def make_chunks(rows):
    """페르소나 한 명을 칸별 청크 여러 개로 쪼갠다.

    칸 하나(예: persona)가 너무 길면(대략 350자, 500토큰 언저리)
    split_long_text() 가 한 번 더 쪼갠다. 그래서 원래는
    "칸 하나 = 청크 하나"였는데, 이제는 "칸 하나 = 청크 1개 이상"이 될 수 있다.
    """
    chunks = []

    for row in rows :
        for column in CHUNK_COLUMNS:
            text = (row.get(column) or "").strip()

            if len(text) < MIN_LENGTH:
                continue

            for piece in split_long_text(text):
                if len(piece) < MIN_LENGTH:
                    continue

                chunks.append({
                    "uuid" : row["uuid"],
                    "district" : row["district"],
                    "category" : column,        # 어느 칸에서 나왔는지
                    "text" : piece,
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









