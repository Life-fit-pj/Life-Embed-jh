"""회원이 채팅에서 말한 거주 선호(장기 메모리). 회원 한 명에 한 줄이다.

채팅 질문마다 Claude 가 선호를 뽑아(app/engine/memory.py) 여기에 합쳐 둔다.
다음 대화에서 답을 만들 때 짧게 실어 준다. 회원이 마이페이지에서 보고 지울 수 있다.
목록 칸(priorities·avoid)은 JSON 글자로 담는다 — AnalysisChat.facts 와 같은 방식이다.
"""

from sqlalchemy import Column, Integer, String, Text

from app.db import Base
from app.models.history import NOW


class UserMemory(Base):
    __tablename__ = "user_memory"

    customer_id = Column(String, primary_key=True)
    budget_manwon = Column(Integer)     # 예산. 만원 단위 (3억 = 30000)
    deal_type = Column(String)          # 매매 · 전세 · 월세
    commute = Column(String)            # 통근·통학 목적지
    priorities = Column(Text)           # 중요하다고 말한 지표. JSON 목록 ["교육", "안전"]
    avoid = Column(Text)                # 피하고 싶다고 말한 것. JSON 목록 ["언덕", "유흥가"]
    updated_at = Column(String, server_default=NOW)
