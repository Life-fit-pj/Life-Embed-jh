"""청크 표 둘. 회원 페르소나와 지식베이스.

칸 구성이 거의 같아서 한 파일에 둔다.
  member_chunk  회원 100명의 페르소나를 9칸으로 쪼갠 것        900줄
  kb_chunk      지식베이스 페르소나                          9,000줄

vector 는 JSON 문자열이 아니라 float32 를 이어 붙인 BLOB 이다. 384개짜리.
읽을 때는 np.frombuffer(vector, dtype=np.float32) 로 되돌린다.
"""

from sqlalchemy import Column, Integer, LargeBinary, String, Text

from app.db import Base


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
