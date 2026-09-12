"""청크 표. 회원 페르소나와 지식베이스를 한 표에 담는다.

  chunks        source 로 둘을 구분한다               9,900줄
                  member  회원 100명 × 9칸  =   900
                  kb      지식베이스        = 9,000

옛 member_chunk · kb_chunk 두 표는 5단계에서 chunks 로 합쳤고,
골든이 통과한 뒤 표와 모델을 함께 지웠다(5-9절).

embedding 은 숫자 1,536개다. pgvector 의 Vector 칸이라 되돌리는 절차가 없다 —
읽으면 숫자 배열이 그대로 나온다(쌓는 곳은 app/ai/vector_store.py).

SQLite 시절에는 숫자 배열 타입이 없어 JSON 글자로 눌러 담았고, 그 자리가
이 한 줄이었다. Postgres + pgvector 로 오면서 Vector(1536) 이 됐다 —
그때 to_text/from_text 도 같이 사라졌다
"""

from sqlalchemy import Column, Integer, String, Text
from pgvector.sqlalchemy import Vector

from app.db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True)
    source = Column(String)        # "member" 또는 "kb"
    source_id = Column(String)     # member 면 customer_id, kb 면 uuid
    district = Column(String)      # kb 만 있다. member 는 None
    category = Column(String)      # persona, sports_persona … config.py 의 CHUNK_COLUMNS
    text = Column(Text)
    embedding = Column(Vector(1536))    # 숫자 1,536개

