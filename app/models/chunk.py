"""청크 표. 회원 페르소나와 지식베이스를 한 표에 담는다.

  chunks        source 로 둘을 구분한다               9,900줄
                  member  회원 100명 × 9칸  =   900
                  kb      지식베이스        = 9,000

옛 member_chunk · kb_chunk 두 표는 5단계에서 chunks 로 합쳤다.
아래 두 클래스는 벡터를 옮기고 대조하는 동안만 남겨 둔 것이고,
골든이 통과하면 표째 지운다(5-9절).

vector 는 JSON 문자열이 아니라 float32 를 이어 붙인 BLOB 이다. 384개짜리.
읽을 때는 np.frombuffer(vector, dtype=np.float32) 로 되돌린다.
6단계에서 embedding = Column(Text) 로 바뀐다
"""

from sqlalchemy import Column, Integer, LargeBinary, String, Text

from app.db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True)
    source = Column(String)        # "member" 또는 "kb"
    source_id = Column(String)     # member 면 customer_id, kb 면 uuid
    district = Column(String)      # kb 만 있다. member 는 None
    category = Column(String)      # persona, sports_persona … config.py 의 CHUNK_COLUMNS
    text = Column(Text)
    vector = Column(LargeBinary)   # float32 x 384 = 1536 바이트


class MemberChunk(Base):
    __tablename__ = "member_chunk"

    chunk_id = Column(Integer, primary_key=True)
    customer_id = Column(String)
    category = Column(String)      # persona, sports_persona … config.py 의 CHUNK_COLUMNS
    text = Column(Text)
    vector = Column(LargeBinary)   # float32 x 384 = 1536 바이트


class KbChunk(Base):
    __tablename__ = "kb_chunk"

    chunk_id = Column(Integer, primary_key=True)
    uuid = Column(String)          # 지식베이스 안의 사람 한 명
    district = Column(String)      # 그 사람이 사는 구
    category = Column(String)
    text = Column(Text)
    vector = Column(LargeBinary)
