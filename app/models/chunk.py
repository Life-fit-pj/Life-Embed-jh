"""청크 표. 회원 페르소나와 지식베이스를 한 표에 담는다.

  chunks        source 로 둘을 구분한다               9,900줄
                  member  회원 100명 × 9칸  =   900
                  kb      지식베이스        = 9,000

옛 member_chunk · kb_chunk 두 표는 5단계에서 chunks 로 합쳤고,
골든이 통과한 뒤 표와 모델을 함께 지웠다(5-9절).

embedding 은 숫자 1,536개를 JSON 문자열로 담은 것이다.
읽을 때는 json.loads(embedding) 으로 되돌린다.

SQLite 에 숫자 배열 타입이 없어서 글자로 눌러 담는다.
나중에 PostgreSQL(pgvector)로 가면 이 한 줄만 Vector(1536) 으로 바꾼다
"""

from sqlalchemy import Column, Integer, String, Text

from app.db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True)
    source = Column(String)        # "member" 또는 "kb"
    source_id = Column(String)     # member 면 customer_id, kb 면 uuid
    district = Column(String)      # kb 만 있다. member 는 None
    category = Column(String)      # persona, sports_persona … config.py 의 CHUNK_COLUMNS
    text = Column(Text)
    embedding = Column(Text)       # json.dumps 로 담은 숫자 1,536개

