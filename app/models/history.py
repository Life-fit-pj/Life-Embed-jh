"""기록용 표 다섯. 전부 "언제 무엇을 했나"를 쌓기만 한다.

칸이 3~5개로 작고 성격이 같아서 한 파일에 모은다.
전부 익명 id(anon_id)로 남긴다 — 로그인 없이도 기록이 쌓이게 하려는 것이다.
"""

from sqlalchemy import Column, Integer, String, Text

from app.db import Base


class Like(Base):
    __tablename__ = "likes"

    # 실제 DB 에 PK 가 없다. 한 줄을 가리키려면 셋이 다 필요하므로 셋 다 PK 로 적는다.
    anon_id = Column(String, primary_key=True)
    구 = Column(String, primary_key=True)
    행정동명 = Column(String, primary_key=True)
    created_at = Column(String)


class SearchHistory(Base):
    __tablename__ = "search_history"

    anon_id = Column(String, primary_key=True)
    query = Column(Text, primary_key=True)
    created_at = Column(String, primary_key=True)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    anon_id = Column(String, primary_key=True)
    question = Column(Text, primary_key=True)
    answer = Column(Text)
    created_at = Column(String, primary_key=True)


class AnalysisChat(Base):
    __tablename__ = "analysis_chat"

    chat_id = Column(Integer, primary_key=True)
    question = Column(Text)
    answer = Column(Text)
    facts = Column(Text)       # 답을 만들 때 근거로 쓴 집계값. JSON 문자열
    created_at = Column(String)


class AdminLog(Base):
    __tablename__ = "admin_log"

    log_id = Column(Integer, primary_key=True)
    target = Column(String)        # "member" 또는 "region"
    target_id = Column(String)
    patch = Column(Text)           # 무엇을 무엇으로 고쳤나. JSON 문자열
    changed_at = Column(String)
